from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from typing import Any, Iterable, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    import websockets
except Exception:  # pragma: no cover - optional dependency
    websockets = None


class SentimentRequest(BaseModel):
    texts: List[str]


app = FastAPI(title="OpenClaw WS -> REST Proxy")


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{name} must be an integer") from exc


def _render_template(template: str, *, token: str, request_id: str, texts: List[str]) -> str:
    return (
        template.replace("{{token}}", token)
        .replace("{{id}}", request_id)
        .replace("{{texts_json}}", json.dumps(texts, ensure_ascii=False))
    )


def _extract_nested(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _normalize_scores(value: Any) -> Optional[List[float]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return None

    scores: List[float] = []
    for item in value:
        if not isinstance(item, (int, float)):
            return None
        scores.append(float(item))
    return scores


def _extract_scores(payload: Any) -> Optional[List[float]]:
    if isinstance(payload, list):
        return _normalize_scores(payload)

    if not isinstance(payload, dict):
        return None

    candidate_keys = os.getenv(
        "WS_GATEWAY_SCORE_KEYS",
        "scores,score,data.scores,data",
    ).split(",")
    for raw_key in candidate_keys:
        key = raw_key.strip()
        if not key:
            continue
        candidate = _extract_nested(payload, key) if "." in key else payload.get(key)
        scores = _normalize_scores(candidate)
        if scores is not None:
            return scores
    return None


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text.strip()
    return ""


def _extract_assistant_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    message = payload.get("message")
    if isinstance(message, dict) and message.get("role") == "assistant":
        return _extract_text_from_content(message.get("content"))

    if payload.get("role") == "assistant":
        return _extract_text_from_content(payload.get("content"))

    return ""


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_scores_from_text(text: str) -> Optional[List[float]]:
    cleaned = _strip_code_fences(text)
    if not cleaned:
        return None

    try:
        parsed = json.loads(cleaned)
    except Exception:
        left_brace = cleaned.find("{")
        right_brace = cleaned.rfind("}")
        if 0 <= left_brace < right_brace:
            try:
                parsed = json.loads(cleaned[left_brace:right_brace + 1])
            except Exception:
                parsed = None
        else:
            parsed = None

    if parsed is not None:
        extracted = _extract_scores(parsed)
        if extracted is not None:
            return extracted

    # Fallback: extract numeric array from malformed JSON-like text.
    array_match = re.search(r"\[\s*-?\d+(?:\.\d+)?(?:\s*,\s*-?\d+(?:\.\d+)?)*\s*\]", cleaned)
    if array_match:
        try:
            raw_array = json.loads(array_match.group(0))
            return _normalize_scores(raw_array)
        except Exception:
            return None

    return None


def _fallback_scores(texts: List[str]) -> List[float]:
    positive_weights = {
        "涨停": 1.6,
        "大涨": 1.4,
        "上涨": 1.0,
        "反弹": 0.9,
        "突破": 1.0,
        "业绩超预期": 1.8,
        "盈利": 1.0,
        "增持": 1.2,
        "买入": 1.1,
        "利好": 1.2,
        "乐观": 0.7,
    }
    negative_weights = {
        "跌停": 1.8,
        "暴跌": 1.7,
        "下跌": 1.0,
        "回撤": 1.1,
        "亏损": 1.2,
        "减持": 1.3,
        "卖出": 1.2,
        "利空": 1.3,
        "悲观": 0.8,
    }
    # 风险相关词单独做惩罚，避免“略正面但高风险”被高估。
    risk_penalty_weights = {
        "风险": 0.35,
        "爆雷": 0.75,
        "违约": 0.85,
        "退市": 0.95,
        "监管": 0.25,
        "问询": 0.30,
        "诉讼": 0.40,
        "减值": 0.45,
        "裁员": 0.40,
    }
    noise_tokens = [
        "哈哈",
        "呵呵",
        "路过",
        "打卡",
        "围观",
        "转发",
        "求带",
        "666",
        "111",
        "?",
        "？",
        "!",
        "！",
    ]

    def _weighted_count(text: str, weights: dict[str, float]) -> float:
        return sum(text.count(word) * weight for word, weight in weights.items())

    scores: List[float] = []
    for text in texts:
        if not text.strip():
            scores.append(0.0)
            continue

        positive_score = _weighted_count(text, positive_weights)
        negative_score = _weighted_count(text, negative_weights)
        risk_penalty = _weighted_count(text, risk_penalty_weights)

        signal_total = positive_score + negative_score + risk_penalty
        if signal_total <= 0.0:
            scores.append(0.0)
            continue

        # 基础分: 正负对冲后归一化。
        raw_score = (positive_score - negative_score) / (signal_total + 1.0)
        # 风险惩罚: 对下行风险更敏感，直接下拉分数。
        raw_score -= min(0.55, risk_penalty * 0.22)

        # 中性噪声压缩: 纯闲聊/情绪宣泄类文本向 0 收敛。
        noise_hits = sum(text.count(token) for token in noise_tokens)
        if noise_hits > 0 and signal_total < 1.2:
            raw_score *= 0.55
        elif signal_total < 0.6:
            raw_score *= 0.70

        scores.append(max(-1.0, min(1.0, float(raw_score))))

    return scores


@app.post("/api/v1/sentiment")
async def score_texts(req: SentimentRequest):
    """Translate REST requests to a WebSocket gateway.

    Configurable environment variables:
    - WS_GATEWAY_URL: WebSocket endpoint, e.g. ws://127.0.0.1:18789
    - WS_GATEWAY_TOKEN: gateway token, required
    - WS_GATEWAY_AUTH_TEMPLATE: JSON template for auth message
    - WS_GATEWAY_REQUEST_TEMPLATE: JSON template for score request
    - WS_GATEWAY_AUTH_TIMEOUT: seconds to wait for auth reply
    - WS_GATEWAY_RESPONSE_TIMEOUT: seconds to wait for score reply
    - WS_GATEWAY_SCORE_KEYS: comma-separated candidate response keys

    Template placeholders:
    - {{token}}: gateway token
    - {{id}}: request correlation id
    - {{texts_json}}: JSON-encoded texts array
    """

    if websockets is None:
        raise HTTPException(status_code=500, detail="websockets package not installed; run `pip install -r requirements.txt`")

    ws_url = os.getenv("WS_GATEWAY_URL", "ws://localhost:18789")
    ws_token = os.getenv("WS_GATEWAY_TOKEN")
    if not ws_token:
        raise HTTPException(status_code=400, detail="WS_GATEWAY_TOKEN is not set in environment")

    request_id = str(uuid.uuid4())
    auth_template = os.getenv("WS_GATEWAY_AUTH_TEMPLATE")
    request_template = os.getenv("WS_GATEWAY_REQUEST_TEMPLATE")
    auth_timeout = _env_int("WS_GATEWAY_AUTH_TIMEOUT", 1)
    response_timeout = _env_int("WS_GATEWAY_RESPONSE_TIMEOUT", 30)
    model_name = os.getenv("WS_GATEWAY_MODEL", "qwen2.5:0.5b")
    connect_scopes = [
        scope.strip()
        for scope in os.getenv(
            "WS_GATEWAY_SCOPES",
            "operator.admin,operator.read,operator.write,operator.approvals,operator.pairing",
        ).split(",")
        if scope.strip()
    ]

    auth_msg = (
        _render_template(auth_template, token=ws_token, request_id=request_id, texts=req.texts)
        if auth_template
        else None
    )

    try:
        # derive an HTTP origin header from ws_url for browser-like origin checks
        origin = None
        try:
            if ws_url.startswith("ws://"):
                origin = "http://" + ws_url[len("ws://") :].split("/", 1)[0]
            elif ws_url.startswith("wss://"):
                origin = "https://" + ws_url[len("wss://") :].split("/", 1)[0]
        except Exception:
            origin = None

        async with websockets.connect(ws_url, origin=origin) as ws:
            # If user provided an explicit auth template, send it first
            if auth_template:
                await ws.send(auth_msg)

                try:
                    auth_reply_raw = await asyncio.wait_for(ws.recv(), timeout=auth_timeout)
                except asyncio.TimeoutError:
                    auth_reply_raw = None

                if auth_reply_raw:
                    try:
                        auth_reply = json.loads(auth_reply_raw)
                    except Exception:
                        auth_reply = None
                    if isinstance(auth_reply, dict):
                        auth_ok = auth_reply.get("ok") is True or auth_reply.get("status") in {"ok", "success", "authenticated"}
                        if auth_reply.get("error"):
                            raise HTTPException(status_code=502, detail=f"Gateway auth failed: {auth_reply['error']}")
                        if not auth_ok and os.getenv("WS_GATEWAY_REQUIRE_AUTH_OK", "0") == "1":
                            raise HTTPException(status_code=502, detail=f"Gateway auth reply not accepted: {auth_reply}")
            else:
                # Automatic JSON-RPC connect flow: wait for connect.challenge event
                try:
                    challenge_raw = await asyncio.wait_for(ws.recv(), timeout=auth_timeout)
                except asyncio.TimeoutError:
                    challenge_raw = None

                if challenge_raw:
                    try:
                        chal = json.loads(challenge_raw)
                    except Exception:
                        chal = None
                    if isinstance(chal, dict) and chal.get("type") == "event" and chal.get("event") == "connect.challenge":
                        # send a `req` connect using the same scope set as the Control UI
                        connect_req = {
                            "type": "req",
                            "id": str(uuid.uuid4()),
                            "method": "connect",
                            "params": {
                                "minProtocol": 4,
                                "maxProtocol": 4,
                                "client": {"id": "openclaw-control-ui", "version": "proxy", "platform": "web", "mode": "ui"},
                                "role": "operator",
                                "scopes": connect_scopes,
                                "auth": {"token": ws_token},
                            },
                        }
                        await ws.send(json.dumps(connect_req))
                    else:
                        # no challenge; fall back to sending auth_msg if available
                        if auth_msg:
                            await ws.send(auth_msg)

            if request_template:
                request_msg = _render_template(request_template, token=ws_token, request_id=request_id, texts=req.texts)
                await ws.send(request_msg)

                try:
                    while True:
                        raw = await asyncio.wait_for(ws.recv(), timeout=response_timeout)
                        try:
                            payload = json.loads(raw)
                        except Exception:
                            continue

                        scores = _extract_scores(payload)
                        if scores is not None:
                            return {"scores": scores}

                        if isinstance(payload, dict) and payload.get("id") == request_id:
                            nested_scores = _extract_scores(payload.get("data"))
                            if nested_scores is not None:
                                return {"scores": nested_scores}

                except asyncio.TimeoutError as exc:
                    raise HTTPException(status_code=502, detail="Timeout waiting for gateway response") from exc

            session_create_id = str(uuid.uuid4())
            await ws.send(json.dumps({"type": "req", "id": session_create_id, "method": "sessions.create", "params": {"model": model_name}}))

            session_key: Optional[str] = None
            deadline = asyncio.get_running_loop().time() + response_timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise HTTPException(status_code=502, detail="Timeout waiting for gateway response")
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue
                if payload.get("type") == "res" and payload.get("id") == session_create_id:
                    create_payload = payload.get("payload") or {}
                    session_key = create_payload.get("key") or create_payload.get("sessionKey")
                    if not isinstance(session_key, str) or not session_key:
                        raise HTTPException(status_code=502, detail=f"Gateway did not return a session key: {payload}")
                    break

            prompt = [
                "你是一个情绪评分引擎。",
                "必须只输出严格 JSON，禁止 markdown、解释、前后缀。",
                "唯一允许格式：{\"scores\":[n1,n2,...]}。",
                "scores 中每个元素必须是 number，不是 string，不是 object。",
                "scores 长度必须等于输入文本数量。",
                "每个分数范围在 -1 到 1 之间，越大越正面，越小越负面。",
                "若不确定，使用 0.0，不要新增其它字段。",
                "输入文本如下：",
            ] + [f"{index + 1}. {text}" for index, text in enumerate(req.texts)]

            send_id = str(uuid.uuid4())
            await ws.send(
                json.dumps(
                    {
                        "type": "req",
                        "id": send_id,
                        "method": "chat.send",
                        "params": {
                            "sessionKey": session_key,
                            "message": "\n".join(prompt),
                            "deliver": True,
                            "idempotencyKey": str(uuid.uuid4()),
                        },
                    }
                )
            )

            collected_text = ""
            send_run_id: Optional[str] = None
            deadline = asyncio.get_running_loop().time() + response_timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue

                if payload.get("type") == "res" and payload.get("id") == send_id:
                    send_payload = payload.get("payload") or {}
                    run_id = send_payload.get("runId")
                    if isinstance(run_id, str) and run_id:
                        send_run_id = run_id
                    continue

                if payload.get("event") in {"chat", "session.message"}:
                    event_payload = payload.get("payload") or {}
                    if event_payload.get("sessionKey") != session_key:
                        continue
                    if send_run_id and event_payload.get("runId") not in {None, send_run_id}:
                        continue
                    text = _extract_assistant_text(event_payload)
                    if text:
                        collected_text = text
                        scores = _extract_scores_from_text(text)
                        if scores is not None:
                            return {"scores": scores}

                if payload.get("type") == "event" and payload.get("event") in {"chat", "session.message"}:
                    event_payload = payload.get("payload") or {}
                    if event_payload.get("sessionKey") != session_key:
                        continue
                    if send_run_id and event_payload.get("runId") not in {None, send_run_id}:
                        continue
                    text = _extract_assistant_text(event_payload)
                    if text:
                        collected_text = text
                        scores = _extract_scores_from_text(text)
                        if scores is not None:
                            return {"scores": scores}

            if collected_text:
                scores = _extract_scores_from_text(collected_text)
                if scores is not None:
                    return {"scores": scores}

            return {"scores": _fallback_scores(req.texts)}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WebSocket proxy error: {exc}") from exc
