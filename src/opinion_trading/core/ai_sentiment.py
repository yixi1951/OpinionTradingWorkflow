from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Literal, Optional, Sequence

from opinion_trading.core.log_utils import get_logger
from opinion_trading.core.openclaw_adapter import OpenClawClient

logger = get_logger(__name__)

SentimentSource = Literal["openclaw", "transformers", "keyword"]


@dataclass(frozen=True)
class SentimentResult:
    """Single-text sentiment output with explainable provenance."""

    score: float
    source: SentimentSource
    confidence: float
    pos_hits: int = 0
    neg_hits: int = 0

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "source": self.source,
            "confidence": self.confidence,
            "pos_hits": self.pos_hits,
            "neg_hits": self.neg_hits,
        }


def clamp_score(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def sentiment_intensity_label(score: float, lang: str = "zh") -> str:
    """Human-readable strength bucket for UI badges."""
    s = float(score)
    if lang == "zh":
        if s >= 0.35:
            return "强势看多"
        if s >= 0.15:
            return "偏多"
        if s <= -0.35:
            return "强势看空"
        if s <= -0.15:
            return "偏空"
        return "中性"
    if s >= 0.35:
        return "Strong bullish"
    if s >= 0.15:
        return "Bullish"
    if s <= -0.35:
        return "Strong bearish"
    if s <= -0.15:
        return "Bearish"
    return "Neutral"


class AISentimentAnalyzer:
    """Pluggable AI sentiment analyzer for A-share social text.

    Priority: OpenClaw (DeepSeek gateway) → local transformers → keyword heuristic.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name
        self._pipeline = None
        try:
            self.openclaw: Optional[OpenClawClient] = OpenClawClient()
        except Exception:
            self.openclaw = None

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

        self._pos = [
            "上涨",
            "利好",
            "突破",
            "增长",
            "看多",
            "反弹",
            "盈利",
            "强势",
            "买入",
            "乐观",
            "加仓",
            "龙头",
            "主升浪",
            "低估",
            "景气",
            "超预期",
            "放量",
            "金叉",
            "底部",
            "牛",
        ]
        self._neg = [
            "下跌",
            "利空",
            "风险",
            "暴跌",
            "看空",
            "回撤",
            "亏损",
            "弱势",
            "卖出",
            "悲观",
            "减仓",
            "套牢",
            "崩盘",
            "高估",
            "减持",
            "破位",
            "死叉",
            "见顶",
            "熊",
            "踩雷",
        ]

    def is_openclaw_ready(self) -> bool:
        return bool(self.openclaw and self.openclaw.is_configured())

    def score_texts(self, texts: Iterable[str]) -> List[float]:
        return [r.score for r in self.analyze_texts(texts)]

    def analyze_texts(self, texts: Iterable[str]) -> List[SentimentResult]:
        texts_list = [str(t or "") for t in texts]
        if not texts_list:
            return []

        oc = self._try_openclaw(texts_list)
        if oc is not None:
            return oc

        if self._pipeline:
            tf = self._try_transformers(texts_list)
            if tf is not None:
                return tf

        return [self._keyword_result(t) for t in texts_list]

    def _try_openclaw(self, texts_list: Sequence[str]) -> Optional[List[SentimentResult]]:
        try:
            if not self.openclaw or not self.openclaw.is_configured():
                return None
            oc_scores = self.openclaw.score_texts(texts_list)
            if not oc_scores or len(oc_scores) != len(texts_list):
                logger.warning(
                    "OpenClaw returned %d scores for %d texts — falling back",
                    len(oc_scores) if oc_scores else 0,
                    len(texts_list),
                )
                return None
            out: List[SentimentResult] = []
            for raw in oc_scores:
                score = clamp_score(float(raw))
                conf = min(0.99, 0.55 + abs(score) * 0.4)
                out.append(
                    SentimentResult(
                        score=score,
                        source="openclaw",
                        confidence=conf,
                    )
                )
            return out
        except Exception as exc:
            logger.warning("OpenClaw API call failed: %s — falling back to keyword", exc)
            return None

    def _try_transformers(
        self, texts_list: Sequence[str]
    ) -> Optional[List[SentimentResult]]:
        try:
            results = self._pipeline(texts_list)
            out: List[SentimentResult] = []
            for r in results:
                label = str(r.get("label", ""))
                prob = float(r.get("score", 0.0))
                if (
                    label.upper().startswith("POS")
                    or label.upper().startswith("1")
                    or label.upper().startswith("2")
                ):
                    mapped = min(1.0, max(-1.0, prob))
                else:
                    mapped = -min(1.0, max(0.0, prob))
                out.append(
                    SentimentResult(
                        score=clamp_score(mapped),
                        source="transformers",
                        confidence=prob,
                    )
                )
            return out
        except Exception:
            return None

    def _keyword_result(self, text: str) -> SentimentResult:
        t = re.sub(r"\s+", " ", str(text or ""))
        pos = sum(t.count(w) for w in self._pos)
        neg = sum(t.count(w) for w in self._neg)
        denom = pos + neg + 5
        raw = (pos - neg) / denom if denom else 0.0
        score = clamp_score(raw)
        hit_total = pos + neg
        confidence = min(0.85, 0.35 + 0.08 * hit_total) if hit_total else 0.25
        return SentimentResult(
            score=score,
            source="keyword",
            confidence=confidence,
            pos_hits=pos,
            neg_hits=neg,
        )