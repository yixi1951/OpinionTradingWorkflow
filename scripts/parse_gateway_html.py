import requests, re
r = requests.get('http://localhost:18789?token=6f751f53aed82616bb4288d8d4a0c16a06afc062f15fb202', timeout=5)
print('STATUS', r.status_code)
srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', r.text)
for s in srcs:
    print('SCRIPT', s)
# also print any occurrences of 'challenge' nearby
if 'challenge' in r.text:
    idx = r.text.find('challenge')
    print('\n...challenge context...')
    print(r.text[max(0, idx-200):idx+200])
