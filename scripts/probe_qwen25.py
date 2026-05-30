import asyncio
import json
import uuid

import websockets

TOKEN = '6f751f53aed82616bb4288d8d4a0c16a06afc062f15fb202'
SCOPES = ['operator.admin', 'operator.read', 'operator.write', 'operator.approvals', 'operator.pairing']
MODEL = 'qwen2.5:1.5b'


async def main() -> None:
    async with websockets.connect('ws://localhost:18789', origin='http://localhost:18789', open_timeout=60) as ws:
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

        await ws.send(json.dumps({'type': 'req', 'id': 'create', 'method': 'sessions.create', 'params': {'model': MODEL}}))
        session_key = None
        while True:
            msg = json.loads(await ws.recv())
            print('create_msg', msg)
            if msg.get('type') == 'res' and msg.get('id') == 'create':
                session_key = (msg.get('payload') or {}).get('key')
                break
        print('session_key', session_key)

        ready = False
        describe_deadline = asyncio.get_running_loop().time() + 60
        while asyncio.get_running_loop().time() < describe_deadline:
            await ws.send(json.dumps({'type': 'req', 'id': 'describe', 'method': 'sessions.describe', 'params': {'key': session_key}}))
            while True:
                msg = json.loads(await ws.recv())
                print('describe_msg', msg)
                if msg.get('type') == 'res' and msg.get('id') == 'describe':
                    entry = (msg.get('payload') or {}).get('entry') or {}
                    if not entry.get('liveModelSwitchPending'):
                        ready = True
                    break
            if ready:
                break
            await asyncio.sleep(1)

        print('ready', ready)

        prompt = '你是情绪评分引擎。请只返回严格 JSON，不要代码块、解释、前后缀。输出格式必须是 {"scores":[...]}。输入文本：1. A股情绪测试 2. 市场风险偏好'
        await ws.send(json.dumps({'type': 'req', 'id': 'send', 'method': 'chat.send', 'params': {'sessionKey': session_key, 'message': prompt, 'deliver': True, 'idempotencyKey': str(uuid.uuid4())}}))
        start = asyncio.get_running_loop().time()
        while True:
            remaining = 60 - (asyncio.get_running_loop().time() - start)
            if remaining <= 0:
                print('timeout waiting')
                return
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
            print('msg', msg)
            if msg.get('type') == 'event' and msg.get('event') in {'chat', 'session.message'}:
                payload = msg.get('payload') or {}
                message = payload.get('message') or {}
                content = message.get('content')
                print('assistant_content', content)
                if isinstance(content, list):
                    text = ''.join(part.get('text','') for part in content if isinstance(part, dict))
                    print('assistant_text', text)
            if msg.get('type') == 'res' and msg.get('id') == 'send':
                print('send_ack', msg)


if __name__ == '__main__':
    asyncio.run(main())
