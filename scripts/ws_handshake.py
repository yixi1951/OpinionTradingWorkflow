import asyncio
import json
import websockets
import uuid
import os

TOKEN = os.getenv("WS_GATEWAY_TOKEN", "your-token-here")


async def probe(url):
    try:
        # include Origin matching the gateway host to satisfy origin checks
        async with websockets.connect(url, origin="http://localhost:18789") as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=2)
            print("RECV", url, raw)
            try:
                obj = json.loads(raw)
            except Exception:
                obj = None
            if (
                isinstance(obj, dict)
                and obj.get("type") == "event"
                and obj.get("event") == "connect.challenge"
            ):
                # send a JSON-RPC style connect request as the client does
                req = {
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
                        "scopes": ["operator.read"],
                        "auth": {"token": TOKEN},
                    },
                }
                await ws.send(json.dumps(req))
                raw2 = await asyncio.wait_for(ws.recv(), timeout=2)
                print("RECV2", url, raw2)
            else:
                print("No challenge or unexpected payload")
    except Exception as e:
        print("ERR", url, type(e).__name__, str(e))


async def main():
    await asyncio.gather(probe("ws://127.0.0.1:18789"), probe("ws://localhost:18789"))


if __name__ == "__main__":
    asyncio.run(main())
