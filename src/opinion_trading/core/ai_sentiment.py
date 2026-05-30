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
        enable = str(os.environ.get("ENABLE_TRANSFORMERS_PIPELINE", "0")) in ("1", "true", "True")
        if enable:
            try:
                from transformers import pipeline  # type: ignore

                env_model = os.environ.get("AI_MODEL_NAME")
                model = model_name or env_model or "distilbert-base-uncased-finetuned-sst-2-english"
                self._pipeline = pipeline("sentiment-analysis", model=model)
            except Exception:
                self._pipeline = None
        else:
            self._pipeline = None

        # simple fallback word lists
        self._pos = ["上涨", "利好", "突破", "增长", "看多", "反弹", "盈利", "强势", "买入", "乐观"]
        self._neg = ["下跌", "利空", "风险", "暴跌", "看空", "回撤", "亏损", "弱势", "卖出", "悲观"]

    def score_texts(self, texts: Iterable[str]) -> List[float]:
        texts_list = list(texts)
        # 1) Try OpenClaw if configured
        try:
            if getattr(self, "openclaw", None) and self.openclaw.is_configured():
                oc_scores = self.openclaw.score_texts(texts_list)
                if oc_scores:
                    return oc_scores
        except Exception:
            pass
        if self._pipeline:
            try:
                results = self._pipeline(texts_list)
                scores: List[float] = []
                for r in results:
                    label = str(r.get("label", ""))
                    score = float(r.get("score", 0.0))
                    if label.upper().startswith("POS") or label.upper().startswith("1") or label.upper().startswith("2"):
                        # POSITIVE -> map to (0,1]
                        mapped = min(1.0, max(-1.0, (score)))
                    else:
                        # NEGATIVE -> map to [-1,0)
                        mapped = -min(1.0, max(0.0, score))
                    scores.append(mapped)
                return scores
            except Exception:
                pass

        # fallback heuristic
        out: List[float] = []
        for txt in texts_list:
            t = str(txt or "")
            pos = sum(t.count(w) for w in self._pos)
            neg = sum(t.count(w) for w in self._neg)
            raw = (pos - neg) / (pos + neg + 5)
            out.append(max(-1.0, min(1.0, float(raw))))
        return out
