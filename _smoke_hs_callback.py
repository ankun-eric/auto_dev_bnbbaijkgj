"""[BUGFIX HS-V2-ALTER 2026-05-28] smoke 3 endpoints to confirm 500 gone."""
import urllib.request
import urllib.error
import ssl

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
ENDPOINTS = [
    ("GET", "/api/admin/home_safety/callback_config", None),
    ("GET", "/api/admin/home_safety/callback_log?page=1&size=20", None),
    ("PUT", "/api/admin/home_safety/callback_config",
     b'{"callback_url":"","auth_token":"","upstream_base_url":""}'),
]
ctx = ssl.create_default_context()


def hit(method, path, body):
    url = BASE + path
    req = urllib.request.Request(url, method=method, data=body)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=20)
        return resp.status, resp.read()[:300].decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "ignore")
        return e.code, body
    except Exception as e:
        return -1, repr(e)


for m, p, b in ENDPOINTS:
    code, body = hit(m, p, b)
    print(f"[{m}] {p} -> {code}  {body[:200]}")
