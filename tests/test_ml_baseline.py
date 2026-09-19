from __future__ import annotations

import importlib.util
from pathlib import Path

from opinion_trading.core.ml_baseline import (
    compare_tfidf_vs_keyword,
    load_labeled_csv,
    write_comparison_report,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _sample_mod():
    path = Path(__file__).resolve().parents[1] / "scripts" / "sample_annotation.py"
    spec = importlib.util.spec_from_file_location("sample_annotation", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sample_annotation_from_raw_csv(tmp_path):
    mod = _sample_mod()
    src = FIXTURES / "raw_posts_smoke_min.csv"
    df = mod.load_source(str(src))
    out = mod.sample_annotation_frame(df, n=5, seed=1)
    assert list(out.columns) == [
        "id",
        "platform",
        "symbol",
        "trade_date",
        "text",
        "label",
        "notes",
    ]
    assert len(out) == 5
    assert (out["label"] == "").all()
    dest = tmp_path / "annotation_sample.csv"
    out.to_csv(dest, index=False)
    assert dest.is_file()


def test_tfidf_vs_keyword_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("SCORING_MODE", "keyword")
    df = load_labeled_csv(FIXTURES / "annotation_sample_labeled.csv")
    assert set(df["label"]).issuperset({"bull", "bear", "neutral"})
    report, clf = compare_tfidf_vs_keyword(df, test_size=0.34, seed=0)
    assert report.n_samples == len(df)
    assert 0.0 <= report.tfidf_accuracy <= 1.0
    assert 0.0 <= report.keyword_accuracy <= 1.0
    preds = clf.predict(["继续看好龙头买入", "暴跌风险建议卖出"])
    assert len(preds) == 2
    assert all(p in {"bull", "bear", "neutral"} for p in preds)
    out = write_comparison_report(report, tmp_path / "ml_baseline_comparison.md")
    assert Path(out["md"]).is_file()
    assert "TF-IDF" in Path(out["md"]).read_text(encoding="utf-8")
    assert Path(out["json"]).is_file()
