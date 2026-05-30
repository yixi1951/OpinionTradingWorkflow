import requests
import re
import os

token = os.getenv("WS_GATEWAY_TOKEN", "your-token-here")
r = requests.get(f"http://localhost:18789?token={token}", timeout=5)
print("STATUS", r.status_code)
srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', r.text)
for s in srcs:
    print("SCRIPT", s)
# also print any occurrences of 'challenge' nearby
if "challenge" in r.text:
    idx = r.text.find("challenge")
    print("\n...challenge context...")
    print(r.text[max(0, idx - 200) : idx + 200])
