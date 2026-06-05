from __future__ import annotations

import os
from typing import Iterable, List
from opinion_trading.core.openclaw_adapter import OpenClawClient


class AISentimentAnalyzer:
    """Pluggable AI sentiment analyzer.

    - If `transformers` is available, uses a local `sentiment-analysis` pipeline.
    - Otherwise falls back to keyword-based heuristic.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name
        self._pipeline = None
        # OpenClaw client (optional external AI service)
        try:
            self.openclaw = OpenClawClient()
        except Exception:
            self.openclaw = None
        # By default do not auto-download a model. To enable local transformers pipeline,
        # set environment variable ENABLE_TRANSFORMERS_PIPELINE=1. This avoids large model
        # downloads during normal runs.
        enable = str(os.environ.get("ENABLE_TRANSFORMERS_PIPELINE", "0")) in (
            "1",
            "true",
            "True",
        )
        if enable:
            try:
                from transformers import pipeline  # type: ignore

                env_model = os.environ.get("AI_MODEL_NAME")
                model = (
                    model_name
                    or env_model
                    or "distilbert-base-uncased-finetuned-sst-2-english"
                )
                self._pipeline = pipeline("sentiment-analysis", model=model)
            except Exception:
                self._pipeline = None
        else:
            self._pipeline = None

        # simple fallback word lists
        self._pos = ["上涨", "利好", "突破", "增长", "看多", "反弹", "盈利", "强势", "买入", "乐观"]
        self._neg = ["下跌", "利空", "风险", "暴跌", "看空", "回撤", "亏损", "弱势", "卖出", "悲观"]

    def score_texts(self, texts: Iterable[str]) -> List[float]:
        texts_list = [str(t or "") for t in texts]
        if not texts_list:
            return []

        batch_size = max(1, int(os.environ.get("OPENCLAW_BATCH_SIZE", "4")))
        if getattr(self, "openclaw", None) and self.openclaw.is_configured():
            try:
                if len(texts_list) <= batch_size:
                    oc_scores = self.openclaw.score_texts(texts_list)
                    if oc_scores and len(oc_scores) == len(texts_list):
                        return oc_scores
                else:
                    merged: List[float] = []
                    for start in range(0, len(texts_list), batch_size):
                        chunk = texts_list[start : start + batch_size]
                        oc_scores = self.openclaw.score_texts(chunk)
                        if not oc_scores or len(oc_scores) != len(chunk):
                            merged.extend(self._fallback_scores(chunk))
                        else:
                            merged.extend(float(s) for s in oc_scores)
                    if merged:
                        return merged
            except Exception:
                pass

        if self._pipeline:
            try:
                results = self._pipeline(texts_list)
                scores: List[float] = []
                for r in results:
                    label = str(r.get("label", ""))
                    score = float(r.get("score", 0.0))
                    if (
                        label.upper().startswith("POS")
                        or label.upper().startswith("1")
                        or label.upper().startswith("2")
                    ):
                        mapped = min(1.0, max(-1.0, (score)))
                    else:
                        mapped = -min(1.0, max(0.0, score))
                    scores.append(mapped)
                return scores
            except Exception:
                pass

        return self._fallback_scores(texts_list)

    def _fallback_scores(self, texts: Iterable[str]) -> List[float]:
        out: List[float] = []
        for txt in texts:
            t = str(txt or "")
            pos = sum(t.count(w) for w in self._pos)
            neg = sum(t.count(w) for w in self._neg)
            raw = (pos - neg) / (pos + neg + 5)
            out.append(max(-1.0, min(1.0, float(raw))))
        return out
