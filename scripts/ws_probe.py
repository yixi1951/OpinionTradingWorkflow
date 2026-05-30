import asyncio
import json
import websockets

TOKEN='6f751f53aed82616bb4288d8d4a0c16a06afc062f15fb202'

async def try_one(url):
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({'op':'auth','token':TOKEN}))
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                msg = '<no-reply>'
            print('OK', url, 'reply=', msg)
    except Exception as e:
        print('ERR', url, type(e).__name__, str(e))

async def main():
    await asyncio.gather(
        try_one('ws://127.0.0.1:18789'),
        try_one('ws://localhost:18789')
    )

if __name__ == '__main__':
    asyncio.run(main())
