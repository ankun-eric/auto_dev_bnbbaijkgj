import json, ssl, urllib.request
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api"

# login
req = urllib.request.Request(f"{BASE}/auth/login", data=json.dumps({"phone":"13900000031","password":"Test@12345"}).encode(), method="POST", headers={"Content-Type":"application/json"})
tok = json.loads(urllib.request.urlopen(req, context=ctx).read().decode())["access_token"]
print("token len:", len(tok))

req = urllib.request.Request(f"{BASE}/questionnaire/answers/27", method="GET", headers={"Authorization": f"Bearer {tok}"})
try:
    r = urllib.request.urlopen(req, context=ctx, timeout=30)
    body = r.read().decode("utf-8","ignore")
    print("status:", r.status)
    print("body:", body[:3000])
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode("utf-8","ignore")[:500])
