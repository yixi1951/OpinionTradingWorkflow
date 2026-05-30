import asyncio
import json
import uuid

import websockets

TOKEN = '6f751f53aed82616bb4288d8d4a0c16a06afc062f15fb202'
SCOPES = ['operator.admin', 'operator.read', 'operator.write', 'operator.approvals', 'operator.pairing']


async def main() -> None:
    async with websockets.connect('ws://localhost:18789', origin='http://localhost:18789') as ws:
        await ws.recv()
        await ws.send(json.dumps({
            'type': 'req',
            'id': 'connect',
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
        while True:
            msg = json.loads(await ws.recv())
            if msg.get('type') == 'res' and msg.get('id') == 'connect':
                print('connect', msg)
                break

        create_id = 'create'
        await ws.send(json.dumps({'type': 'req', 'id': create_id, 'method': 'sessions.create', 'params': {'model': 'gemma4'}}))
        session_key = None
        while True:
            msg = json.loads(await ws.recv())
            print('msg', msg)
            if msg.get('type') == 'res' and msg.get('id') == create_id:
                payload = msg.get('payload') or {}
                session_key = payload.get('key') or payload.get('sessionKey')
                break
        print('session_key', session_key)
        if not session_key:
            return

        send_id = 'send'
        await ws.send(json.dumps({
            'type': 'req',
            'id': send_id,
            'method': 'chat.send',
            'params': {
                'sessionKey': session_key,
                'message': '请只回复 JSON，格式为 {"scores":[0.1,-0.2]}。',
                'deliver': True,
                'idempotencyKey': str(uuid.uuid4()),
            },
        }))
        while True:
            msg = json.loads(await ws.recv())
            print('after_send', msg)
            if msg.get('type') == 'res' and msg.get('id') == send_id:
                break

        history_id = 'history'
        await ws.send(json.dumps({'type': 'req', 'id': history_id, 'method': 'chat.history', 'params': {'sessionKey': session_key, 'limit': 5, 'maxChars': 2000}}))
        while True:
            msg = json.loads(await ws.recv())
            print('history_msg', msg)
            if msg.get('type') == 'res' and msg.get('id') == history_id:
                break


if __name__ == '__main__':
    asyncio.run(main())
