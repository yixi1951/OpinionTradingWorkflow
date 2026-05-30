import asyncio
import json
import uuid

import websockets

TOKEN = '6f751f53aed82616bb4288d8d4a0c16a06afc062f15fb202'


async def main() -> None:
    async with websockets.connect('ws://localhost:18789', origin='http://localhost:18789') as ws:
        print('challenge', await ws.recv())
        connect_id = str(uuid.uuid4())
        await ws.send(json.dumps({
            'type': 'req',
            'id': connect_id,
            'method': 'connect',
            'params': {
                'minProtocol': 4,
                'maxProtocol': 4,
                'client': {
                    'id': 'openclaw-control-ui',
                    'version': 'probe',
                    'platform': 'web',
                    'mode': 'ui',
                },
                'role': 'operator',
                'scopes': ['operator.admin', 'operator.read', 'operator.write', 'operator.approvals', 'operator.pairing'],
                'auth': {'token': TOKEN},
            },
        }))
        print('hello', await ws.recv())
        infer_id = str(uuid.uuid4())
        await ws.send(json.dumps({
            'type': 'req',
            'id': infer_id,
            'method': 'infer',
            'params': {'texts': ['A股情绪测试']},
        }))
        try:
            while True:
                print('reply', await asyncio.wait_for(ws.recv(), timeout=3))
        except Exception as exc:
            print('done', type(exc).__name__, exc)


if __name__ == '__main__':
    asyncio.run(main())
