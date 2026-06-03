import urllib.request, urllib.error, json, ssl

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def post(url, data, headers=None):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                  headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

print("[1] v2 callback (unbound device)")
sc, body = post(f"{BASE}/api/home_safety/callback/alarm",
                {"msgId": "smoke_final_v2_a",
                 "param": {"devId": "NOEXIST1", "devType": "1", "occurTime": 1547100617645, "gwId": "GW123"},
                 "dataType": "call-msg"})
print(f"  HTTP {sc} BODY={body[:300]}")

print("\n[2] v2 callback (duplicate msgId)")
sc, body = post(f"{BASE}/api/home_safety/callback/alarm",
                {"msgId": "smoke_final_v2_a",
                 "param": {"devId": "NOEXIST1", "devType": "1", "occurTime": 1547100617645, "gwId": "GW123"},
                 "dataType": "call-msg"})
print(f"  HTTP {sc} BODY={body[:300]}")

print("\n[3] v2 alt path /callback/home_safety/alarm")
sc, body = post(f"{BASE}/callback/home_safety/alarm",
                {"msgId": "smoke_final_v2_b",
                 "param": {"devId": "NOEXIST2", "devType": "2", "occurTime": 1547100617645},
                 "dataType": "call-msg"})
print(f"  HTTP {sc} BODY={body[:300]}")

print("\n[4] admin push_history (no auth → expect 401)")
sc, body = get(f"{BASE}/api/admin/home_safety/callback_config/push_history?limit=3")
print(f"  HTTP {sc} BODY={body[:200]}")

print("\n[5] admin callback_config GET (no auth → expect 401)")
sc, body = get(f"{BASE}/api/admin/home_safety/callback_config")
print(f"  HTTP {sc} BODY={body[:200]}")

print("\n[6] admin page render")
sc, body = get(f"{BASE}/admin/home-safety")
print(f"  HTTP {sc} BODY_LEN={len(body)}")
