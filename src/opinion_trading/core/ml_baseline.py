"""Offline TF-IDF ML baseline vs keyword/hybrid scoring (research prototype)."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

LABELS = ("bull", "bear", "neutral")
_SCHEMA_COLS = ("id", "platform", "symbol", "trade_date", "text", "label", "notes")


def load_labeled_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in ("text", "label") if c not in df.columns]
    if missing:
        raise ValueError(f"labels CSV must contain columns: {', '.join(missing)}")
    df = df.copy()
    df["text"] = df["text"].astype(str)
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    df = df[df["label"].isin(LABELS)]
    if df.empty:
        raise ValueError("no rows with label in {bull, bear, neutral}")
    return df.reset_index(drop=True)


def _char_ngrams(text: str, n_min: int = 2, n_max: int = 3) -> List[str]:
    t = re.sub(r"\s+", "", str(text or "").lower())
    grams: List[str] = []
    for n in range(n_min, n_max + 1):
        if len(t) < n:
            continue
        grams.extend(t[i : i + n] for i in range(len(t) - n + 1))
    if not grams and t:
        grams.append(t)
    return grams


class TfidfCentroidClassifier:
    """Tiny offline classifier: character n-gram TF-IDF + nearest class centroid."""

    def __init__(self, max_features: int = 4000) -> None:
        self.max_features = max_features
        self.vocab: Dict[str, int] = {}
        self.idf: np.ndarray = np.array([])
        self.centroids: Dict[str, np.ndarray] = {}
        self.labels: List[str] = []

    def fit(self, texts: Sequence[str], y: Sequence[str]) -> "TfidfCentroidClassifier":
        docs = [_char_ngrams(t) for t in texts]
        df_count: Counter[str] = Counter()
        for grams in docs:
            df_count.update(set(grams))
        vocab_items = [
            tok
            for tok, _ in df_count.most_common(self.max_features)
            if tok
        ]
        self.vocab = {tok: i for i, tok in enumerate(vocab_items)}
        n_docs = max(1, len(docs))
        idf = np.zeros(len(self.vocab), dtype=float)
        for tok, idx in self.vocab.items():
            idf[idx] = math.log((1.0 + n_docs) / (1.0 + df_count[tok])) + 1.0
        self.idf = idf
        matrix = self._transform(docs)
        self.labels = sorted(set(str(v) for v in y))
        self.centroids = {}
        y_arr = np.array([str(v) for v in y])
        for lab in self.labels:
            mask = y_arr == lab
            if not mask.any():
                continue
            centroid = matrix[mask].mean(axis=0)
            norm = np.linalg.norm(centroid)
            self.centroids[lab] = centroid / norm if norm > 0 else centroid
        return self

    def _transform(self, docs: Sequence[Sequence[str]]) -> np.ndarray:
        n = len(docs)
        m = len(self.vocab)
        X = np.zeros((n, m), dtype=float)
        if m == 0:
            return X
        for i, grams in enumerate(docs):
            counts = Counter(g for g in grams if g in self.vocab)
            total = sum(counts.values()) or 1
            for tok, c in counts.items():
                X[i, self.vocab[tok]] = (c / total) * self.idf[self.vocab[tok]]
            norm = np.linalg.norm(X[i])
            if norm > 0:
                X[i] /= norm
        return X

    def predict(self, texts: Sequence[str]) -> List[str]:
        if not self.centroids:
            return ["neutral"] * len(texts)
        X = self._transform([_char_ngrams(t) for t in texts])
        names = list(self.centroids.keys())
        C = np.stack([self.centroids[n] for n in names], axis=0)
        sims = X @ C.T
        idx = np.argmax(sims, axis=1)
        return [names[int(i)] for i in idx]


def keyword_labels(texts: Sequence[str]) -> List[str]:
    """Map lexicon scores to bull/bear/neutral (no network / LLM)."""
    from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

    analyzer = AISentimentAnalyzer(enable_fusion=False)
    results = analyzer.analyze_texts(list(texts))
    out: List[str] = []
    for res in results:
        if res.score >= 0.15:
            out.append("bull")
        elif res.score <= -0.15:
            out.append("bear")
        else:
            out.append("neutral")
    return out


def _accuracy(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    if not y_true:
        return 0.0
    hits = sum(1 for a, b in zip(y_true, y_pred) if a == b)
    return hits / len(y_true)


def _per_class_f1(y_true: Sequence[str], y_pred: Sequence[str]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for lab in LABELS:
        tp = sum(1 for a, b in zip(y_true, y_pred) if a == lab and b == lab)
        fp = sum(1 for a, b in zip(y_true, y_pred) if a != lab and b == lab)
        fn = sum(1 for a, b in zip(y_true, y_pred) if a == lab and b != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        scores[lab] = 0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec)
    scores["macro"] = float(np.mean([scores[name] for name in LABELS]))
    return scores


@dataclass
class BaselineComparison:
    n_samples: int
    n_train: int
    n_test: int
    tfidf_accuracy: float
    keyword_accuracy: float
    tfidf_macro_f1: float
    keyword_macro_f1: float
    tfidf_per_class_f1: Dict[str, float]
    keyword_per_class_f1: Dict[str, float]
    note: str

    def to_dict(self) -> Dict:
        return {
            "n_samples": self.n_samples,
            "n_train": self.n_train,
            "n_test": self.n_test,
            "tfidf_accuracy": self.tfidf_accuracy,
            "keyword_accuracy": self.keyword_accuracy,
            "tfidf_macro_f1": self.tfidf_macro_f1,
            "keyword_macro_f1": self.keyword_macro_f1,
            "tfidf_per_class_f1": self.tfidf_per_class_f1,
            "keyword_per_class_f1": self.keyword_per_class_f1,
            "note": self.note,
        }


def compare_tfidf_vs_keyword(
    df: pd.DataFrame,
    *,
    test_size: float = 0.34,
    seed: int = 42,
) -> Tuple[BaselineComparison, TfidfCentroidClassifier]:
    texts = df["text"].astype(str).tolist()
    labels = df["label"].astype(str).tolist()
    n = len(texts)
    rng = np.random.RandomState(seed)
    idx = np.arange(n)
    rng.shuffle(idx)
    n_test = max(1, int(round(n * test_size))) if n > 3 else max(1, n // 3 or 1)
    n_test = min(n_test, n - 1) if n > 1 else n
    test_idx = set(idx[:n_test].tolist())
    train_texts = [texts[i] for i in range(n) if i not in test_idx]
    train_y = [labels[i] for i in range(n) if i not in test_idx]
    test_texts = [texts[i] for i in range(n) if i in test_idx] or texts
    test_y = [labels[i] for i in range(n) if i in test_idx] or labels
    if not train_texts:
        train_texts, train_y = texts, labels

    clf = TfidfCentroidClassifier()
    clf.fit(train_texts, train_y)
    tfidf_pred = clf.predict(test_texts)
    kw_pred = keyword_labels(test_texts)

    tfidf_f1 = _per_class_f1(test_y, tfidf_pred)
    kw_f1 = _per_class_f1(test_y, kw_pred)
    report = BaselineComparison(
        n_samples=n,
        n_train=len(train_texts),
        n_test=len(test_texts),
        tfidf_accuracy=_accuracy(test_y, tfidf_pred),
        keyword_accuracy=_accuracy(test_y, kw_pred),
        tfidf_macro_f1=tfidf_f1["macro"],
        keyword_macro_f1=kw_f1["macro"],
        tfidf_per_class_f1=tfidf_f1,
        keyword_per_class_f1=kw_f1,
        note=(
            "Research prototype only — tiny labeled sample, not a profitability claim. "
            "Keyword/hybrid remains the default scoring path."
        ),
    )
    return report, clf


def write_comparison_report(
    report: BaselineComparison,
    out_md: str | Path,
    out_json: Optional[str | Path] = None,
) -> Dict[str, str]:
    md_path = Path(out_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# ML baseline vs keyword scoring",
        "",
        f"- Generated: {ts}",
        f"- Samples: **{report.n_samples}** (train {report.n_train} / test {report.n_test})",
        f"- TF-IDF centroid accuracy: **{report.tfidf_accuracy:.2%}** (macro F1 {report.tfidf_macro_f1:.3f})",
        f"- Keyword lexicon accuracy: **{report.keyword_accuracy:.2%}** (macro F1 {report.keyword_macro_f1:.3f})",
        "",
        report.note,
        "",
        "| Label | TF-IDF F1 | Keyword F1 |",
        "|---|---:|---:|",
    ]
    for lab in LABELS:
        lines.append(
            f"| {lab} | {report.tfidf_per_class_f1.get(lab, 0):.3f} | "
            f"{report.keyword_per_class_f1.get(lab, 0):.3f} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path = Path(out_json) if out_json else md_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"md": str(md_path), "json": str(json_path)}
