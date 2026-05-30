import requests
url='http://localhost:18789/assets/index-s15Q2hqZ.js'
r = requests.get(url, timeout=5)
print('STATUS', r.status_code)
text = r.text
patterns = ['sendConnect','sendConnect(','explicitGatewayToken','signedAt','signature','deviceId','privateKey','authToken','connect.response','connect.challenge','nonce']
for kw in patterns:
    if kw in text:
        print('\nFOUND', kw)
        i = text.find(kw)
        print(text[max(0,i-300):i+300])
        
print('\n--- summary lines containing connect.challenge ---')
for line in text.splitlines():
    if 'connect.challenge' in line or 'sendConnect' in line or 'connect.response' in line:
        print(line.strip())
        
        print('\n--- searching for sendConnect definition ---')
        for idx in range(len(text)):
            if text[idx:idx+11]=='sendConnect(' or text[idx:idx+12]=='sendConnect=':
                print('\nFOUND sendConnect at', idx)
                print(text[max(0,idx-200):idx+200])
