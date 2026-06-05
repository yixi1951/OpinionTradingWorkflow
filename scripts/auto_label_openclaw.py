r"""使用 OpenClaw 服务对样本批量打分并生成建议标签。

默认会优先读取本机 OpenClaw 配置文件：
- %USERPROFILE%\.openclaw\openclaw.json
- %USERPROFILE%\.openclaw\openclaw.json.bak

如果配置文件存在且为本地网关模式，则自动派生：
- WS_GATEWAY_URL = ws://127.0.0.1:<gateway.port>
- WS_GATEWAY_TOKEN = gateway.auth.token

输出：data/labels/annotation_sample_openclaw.csv
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

# ensure repository root is on sys.path so we can import package
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.opinion_trading.core.openclaw_adapter import OpenClawClient


def _load_local_openclaw_config() -> dict:
    home = Path(os.environ.get("USERPROFILE", str(Path.home())))
    candidates = [home / ".openclaw" / "openclaw.json", home / ".openclaw" / "openclaw.json.bak"]
    for candidate in candidates:
        if candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {}


def _apply_openclaw_config() -> None:
    config = _load_local_openclaw_config()
    gateway = config.get("gateway") if isinstance(config, dict) else {}
    auth = gateway.get("auth") if isinstance(gateway, dict) else {}

    # Only auto-fill from local gateway configs.
    if isinstance(gateway, dict) and gateway.get("mode") == "local":
        port = gateway.get("port", 18789)
        os.environ.setdefault("WS_GATEWAY_URL", f"ws://127.0.0.1:{port}")
        token = auth.get("token") if isinstance(auth, dict) else None
        if isinstance(token, str) and token:
            os.environ.setdefault("WS_GATEWAY_TOKEN", token)

    defaults = config.get("agents", {}).get("defaults", {}) if isinstance(config, dict) else {}
    model_cfg = defaults.get("model", {}) if isinstance(defaults, dict) else {}
    primary = model_cfg.get("primary") if isinstance(model_cfg, dict) else None
    if isinstance(primary, str) and primary:
        os.environ.setdefault("WS_GATEWAY_MODEL", primary)

    # If the HTTP bridge is already configured externally, keep it.
    # Otherwise the caller can still point OPENCLAW_URL at the proxy manually.


def _wait_for_port(host: str, port: int, timeout_s: float = 10.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _ensure_http_bridge() -> None:
    if os.environ.get("OPENCLAW_URL"):
        return

    config = _load_local_openclaw_config()
    gateway = config.get("gateway") if isinstance(config, dict) else {}
    auth = gateway.get("auth") if isinstance(gateway, dict) else {}

    if not (isinstance(gateway, dict) and gateway.get("mode") == "local"):
        return

    proxy_port = int(os.environ.get("OPENCLAW_PROXY_PORT", "18790"))
    ws_port = int(gateway.get("port", 18789))
    token = auth.get("token") if isinstance(auth, dict) else None

    os.environ.setdefault("WS_GATEWAY_URL", f"ws://127.0.0.1:{ws_port}")
    if isinstance(token, str) and token:
        os.environ.setdefault("WS_GATEWAY_TOKEN", token)

    os.environ.setdefault("OPENCLAW_URL", f"http://127.0.0.1:{proxy_port}")

    if not _wait_for_port("127.0.0.1", ws_port, timeout_s=1.0):
        raise RuntimeError(
            f"OpenClaw gateway is not reachable at ws://127.0.0.1:{ws_port}; start OpenClaw first."
        )

    # Try to reuse an already-running bridge first.
    if _wait_for_port("127.0.0.1", proxy_port, timeout_s=1.0):
        return

    # Launch a local bridge for the current session.
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "openclaw_ws_proxy:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(proxy_port),
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not _wait_for_port("127.0.0.1", proxy_port, timeout_s=12.0):
        raise RuntimeError(
            f"Failed to start OpenClaw HTTP bridge on 127.0.0.1:{proxy_port}"
        )


def main(infile='data/labels/annotation_sample.csv', out='data/labels/annotation_sample_openclaw.csv'):
    _apply_openclaw_config()
    _ensure_http_bridge()

    p = Path(infile)
    if not p.exists():
        print('Input not found:', infile)
        return
    df = pd.read_csv(p)
    texts = df.get('text')
    if texts is None:
        for c in ['content','summary','title']:
            if c in df.columns:
                texts = df[c]
                break
    if texts is None:
        texts = df.astype(str).agg(' '.join, axis=1)

    client = OpenClawClient()
    if not client.is_configured():
        print('OpenClaw not configured. Check your local .openclaw config or set OPENCLAW_URL/OPENCLAW_TOKEN manually.')
        return

    print('Sending', len(texts), 'texts to OpenClaw...')
    scores = client.score_texts(texts.tolist())
    if scores is None:
        print('OpenClaw call failed or returned invalid response; check that the local OpenClaw gateway and bridge are running.')
        return
    out_df = df.copy()
    # interpret score >0 => bull, <0 => bear, =0 => neutral
    out_df['openclaw_score'] = scores
    out_df['openclaw_label'] = out_df['openclaw_score'].apply(lambda s: 'bull' if s>0 else ('bear' if s<0 else 'neutral'))
    out_df.to_csv(out, index=False, encoding='utf-8-sig')
    print('Wrote', out)


if __name__ == '__main__':
    main()
