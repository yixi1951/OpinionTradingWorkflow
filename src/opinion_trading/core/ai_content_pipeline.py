"""AI content pipeline: relevance screening + batch LLM sentiment scoring."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)


def _chunk(items: Sequence[Any], size: int) -> List[List[Any]]:
    size = max(1, int(size))
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def _row_text(row: Dict[str, Any], max_len: int = 400) -> str:
    title = str(row.get("title") or "")
    content = str(row.get("content") or row.get("summary") or "")
    blob = f"{title} {content}".strip()
    return blob[:max_len]


def _call_llm_json(prompt: str, texts: List[str]) -> Optional[Dict[str, Any]]:
    """Chat completion returning a JSON object (DeepSeek OpenAI-compatible)."""
    if not texts:
        return {"items": []}

    api_key = (
        os.environ.get("DEEPSEEK_API_KEY", "").strip()
        or os.environ.get("QWEN_API_KEY", "").strip()
        or os.environ.get("DASHSCOPE_API_KEY", "").strip()
    )
    if not api_key:
        return None

    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        key = os.environ["DEEPSEEK_API_KEY"].strip()
    else:
        base = os.environ.get(
            "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ).rstrip("/")
        model = os.environ.get("QWEN_MODEL", "qwen-turbo")
        key = api_key

    try:
        import requests

        resp = requests.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.1,
                "messages": [
                    {"role": "system", "content": "只输出合法 JSON，不要 Markdown。"},
                    {
                        "role": "user",
                        "content": prompt
                        + "\n输入文本数组:\n"
                        + json.dumps(texts, ensure_ascii=False),
                    },
                ],
            },
            timeout=int(os.environ.get("OPENCLAW_TIMEOUT", "120")),
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _extract_json_obj(str(content))
    except Exception as exc:
        logger.warning("LLM JSON chat failed: %s", exc)
        return None


def _extract_json_obj(text: str) -> Optional[Dict[str, Any]]:
    text = str(text or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {"items": obj}
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {"items": obj}
        except json.JSONDecodeError:
            return None
    return None


def screen_relevance(
    rows: List[Dict[str, Any]],
    *,
    batch_size: int = 12,
    enabled: bool = True,
) -> List[Dict[str, Any]]:
    """Mark ai_relevant / drop unrelated & ads. Groups by symbol for better prompts."""
    if not rows:
        return rows
    if not enabled:
        for r in rows:
            r.setdefault("ai_relevant", True)
            r.setdefault("ai_drop_reason", "")
        return rows

    out = [dict(r) for r in rows]
    # index map for in-place updates
    by_symbol: Dict[str, List[int]] = {}
    for i, r in enumerate(out):
        sym = str(r.get("symbol") or "")
        by_symbol.setdefault(sym, []).append(i)

    for symbol, idxs in by_symbol.items():
        for batch_idxs in _chunk(idxs, batch_size):
            texts = [_row_text(out[i]) for i in batch_idxs]
            prompt = (
                f"你是 A 股舆情质检员。标的={symbol}。\n"
                "对每条文本判断：是否与该标的相关、是否广告/水帖/导航噪声。\n"
                '只输出 JSON：{"items":[{"relevant":true/false,"reason":"简短中文"}...]}\n'
                "items 长度必须等于输入条数。"
            )
            parsed = _call_llm_json(prompt, texts)
            items = (parsed or {}).get("items") if parsed else None
            if not isinstance(items, list) or len(items) != len(batch_idxs):
                # heuristic fallback
                for i, t in zip(batch_idxs, texts):
                    code = symbol.split(".")[0]
                    relevant = True
                    reason = ""
                    low = t.lower()
                    if any(
                        x in t
                        for x in ("加微信", "加V", "免费荐股", "稳赚", "扫码进群")
                    ):
                        relevant = False
                        reason = "ad"
                    elif len(t) < 12:
                        relevant = False
                        reason = "too_short"
                    elif code and code not in t and "股" not in t and len(t) < 40:
                        # weak unrelated heuristic only when very short
                        pass
                    out[i]["ai_relevant"] = relevant
                    out[i]["ai_drop_reason"] = reason
                    if not relevant:
                        out[i]["is_noise"] = True
                continue

            for i, item in zip(batch_idxs, items):
                if not isinstance(item, dict):
                    out[i]["ai_relevant"] = True
                    out[i]["ai_drop_reason"] = ""
                    continue
                relevant = bool(item.get("relevant", True))
                reason = str(item.get("reason") or "")
                out[i]["ai_relevant"] = relevant
                out[i]["ai_drop_reason"] = reason
                if not relevant:
                    out[i]["is_noise"] = True
    return out


def score_sentiment(
    rows: List[Dict[str, Any]],
    *,
    batch_size: int = 16,
    only_relevant: bool = True,
    enabled: bool = True,
) -> List[Dict[str, Any]]:
    """Batch LLM sentiment into ai_score; keyword remains fallback only."""
    if not rows or not enabled:
        return rows

    out = [dict(r) for r in rows]
    targets = [
        i
        for i, r in enumerate(out)
        if (not only_relevant or r.get("ai_relevant", True))
        and not (
            str(r.get("capture_status")) == "fallback"
            and "stub" in str(r.get("failure_reason", "")).lower()
        )
        and _row_text(r)
    ]
    if not targets:
        return out

    from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

    # Prefer pure LLM (no hybrid dilution)
    os.environ.setdefault("SCORING_MODE", "ai")
    analyzer = AISentimentAnalyzer(enable_fusion=False)

    for batch_idxs in _chunk(targets, batch_size):
        texts = [_row_text(out[i]) for i in batch_idxs]
        try:
            results = analyzer.analyze_texts(texts)
        except Exception as exc:
            logger.warning("AI sentiment batch failed: %s", exc)
            continue
        if len(results) != len(batch_idxs):
            continue
        for i, res in zip(batch_idxs, results):
            out[i]["ai_score"] = float(res.score)
            src = str(res.source)
            if src in {"openclaw", "transformers", "hybrid"}:
                out[i]["score_source"] = "openclaw" if src != "transformers" else "transformers"
            elif src == "keyword":
                # keep keyword only if LLM truly fell back
                out[i]["score_source"] = "keyword"
            else:
                out[i]["score_source"] = src
    return out


def run_ai_content_pipeline(
    rows: List[Dict[str, Any]],
    *,
    screen_enabled: bool = True,
    score_enabled: bool = True,
    batch_size: int = 12,
) -> Dict[str, Any]:
    """Screen then score. Returns updated rows + stats."""
    screened = screen_relevance(rows, batch_size=batch_size, enabled=screen_enabled)
    scored = score_sentiment(
        screened,
        batch_size=max(batch_size, 8),
        only_relevant=True,
        enabled=score_enabled,
    )
    total = len(scored)
    relevant = sum(1 for r in scored if r.get("ai_relevant", True))
    dropped = total - relevant
    llm_scored = sum(
        1
        for r in scored
        if str(r.get("score_source", "")).lower()
        in {"openclaw", "transformers", "gateway", "hybrid"}
    )
    stats = {
        "total": total,
        "relevant": relevant,
        "dropped": dropped,
        "drop_rate": (dropped / total) if total else 0.0,
        "llm_scored": llm_scored,
        "llm_rate": (llm_scored / total) if total else 0.0,
    }
    logger.info(
        "AI pipeline: total=%d relevant=%d dropped=%d llm_scored=%d",
        total,
        relevant,
        dropped,
        llm_scored,
    )
    return {"rows": scored, "stats": stats}
