"""Probe backend openapi for public GET endpoints likely returning datetime."""
import urllib.request, ssl, json, re

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

for path in ["/openapi.json", "/api/openapi.json", "/docs/openapi.json"]:
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=15, context=ctx) as r:
            print(f"FOUND {url} -> {r.status}")
            data = json.loads(r.read().decode())
            break
    except Exception as e:
        print(f"  miss {url}: {e}")
        continue
else:
    print("no openapi available")
    raise SystemExit

# 找出无鉴权且 GET 的接口（heuristic: 没有 security 字段或 security=[]）
paths = data.get("paths", {})
candidates = []
for p, methods in paths.items():
    if "get" not in methods:
        continue
    info = methods["get"]
    sec = info.get("security", None)
    # 路径里有 {param} 的暂时跳过（需 id）
    if "{" in p:
        continue
    candidates.append((p, sec, info.get("summary", "")))

for p, sec, s in candidates[:40]:
    print(f"  GET {p}   sec={sec}  - {s}")
