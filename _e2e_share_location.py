import json, urllib.request, urllib.error, random

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

def call(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Client-Type", "h5-user")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

phone = "139" + "".join(random.choice("0123456789") for _ in range(8))
print("phone", phone)
s, r = call("POST", "/api/auth/register", {"phone": phone, "password": "test123456", "nickname": "E2E长辈"})
print("register", s)
s, r = call("POST", "/api/auth/login", {"phone": phone, "password": "test123456"})
print("login", s)
token = r.get("access_token") if isinstance(r, dict) else None
print("token?", bool(token))

s, r = call("PUT", "/api/care-card/home-address", {"home_address": "北京市海淀区中关村大街1号"}, token)
print("home-address", s, r)
s, r = call("POST", "/api/care-card/contacts", {"name": "小强", "relation": "儿子", "phone": "13800001234"}, token)
print("contact", s, r)
s, r = call("POST", "/api/care-card/share-location", {"latitude": 39.98, "longitude": 116.31, "address": "北京市海淀区中关村大街1号"}, token)
print("share-create", s, r)
share_token = r["data"]["token"] if isinstance(r, dict) and r.get("data") else None
print("share_token", share_token)
s, r = call("GET", "/api/care-card/share-location/" + share_token)
print("share-read", s)
print(json.dumps(r, ensure_ascii=False)[:600])
