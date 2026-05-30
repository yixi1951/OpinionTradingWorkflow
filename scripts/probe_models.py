import asyncio
import json
import uuid

import websockets

TOKEN = '6f751f53aed82616bb4288d8d4a0c16a06afc062f15fb202'
SCOPES = ['operator.admin', 'operator.read', 'operator.write', 'operator.approvals', 'operator.pairing']


async def main() -> None:
    async with websockets.connect('ws://localhost:18789', origin='http://localhost:18789') as ws:
        print('challenge', await ws.recv())
        await ws.send(json.dumps({
            'type': 'req',
            'id': str(uuid.uuid4()),
            'method': 'connect',
            'params': {
                'minProtocol': 4,
                'maxProtocol': 4,
                'client': {'id': 'openclaw-control-ui', 'version': 'probe', 'platform': 'web', 'mode': 'ui'},
                'role': 'operator',
                'scopes': SCOPES,
                'auth': {'token': TOKEN},
            },
        }))
        print('hello', await ws.recv())

        await ws.send(json.dumps({'type': 'req', 'id': str(uuid.uuid4()), 'method': 'models.list', 'params': {}}))
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                print('msg', msg)
        except Exception as exc:
            print('done', type(exc).__name__, exc)


if __name__ == '__main__':
    asyncio.run(main())
