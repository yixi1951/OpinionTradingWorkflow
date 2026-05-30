import asyncio
import json
import uuid
import os

import websockets

TOKEN = os.getenv("WS_GATEWAY_TOKEN", "your-token-here")
SCOPES = [
    "operator.admin",
    "operator.read",
    "operator.write",
    "operator.approvals",
    "operator.pairing",
]
SESSION_KEY = "agent:main:main"


async def main() -> None:
    async with websockets.connect(
        "ws://localhost:18789", origin="http://localhost:18789"
    ) as ws:
        print("challenge", await ws.recv())
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": str(uuid.uuid4()),
                    "method": "connect",
                    "params": {
                        "minProtocol": 4,
                        "maxProtocol": 4,
                        "client": {
                            "id": "openclaw-control-ui",
                            "version": "probe",
                            "platform": "web",
                            "mode": "ui",
                        },
                        "role": "operator",
                        "scopes": SCOPES,
                        "auth": {"token": TOKEN},
                    },
                }
            )
        )
        print("hello", await ws.recv())

        patch_id = str(uuid.uuid4())
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": patch_id,
                    "method": "sessions.patch",
                    "params": {"key": SESSION_KEY, "model": "gemma4"},
                }
            )
        )
        print("patch", await ws.recv())

        send_id = str(uuid.uuid4())
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": send_id,
                    "method": "chat.send",
                    "params": {
                        "sessionKey": SESSION_KEY,
                        "message": '请只回复 JSON，格式为 {"scores":[0.1,-0.2]}。',
                        "deliver": True,
                        "idempotencyKey": str(uuid.uuid4()),
                    },
                }
            )
        )
        print("send", await ws.recv())

        history_id = str(uuid.uuid4())
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": history_id,
                    "method": "chat.history",
                    "params": {"sessionKey": SESSION_KEY, "limit": 5, "maxChars": 2000},
                }
            )
        )
        print("history", await ws.recv())

        try:
            while True:
                print("event", await asyncio.wait_for(ws.recv(), timeout=5))
        except Exception as exc:
            print("done", type(exc).__name__, exc)


if __name__ == "__main__":
    asyncio.run(main())
