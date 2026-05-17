import json

d = json.load(open("deploy/link_check_attach_filter_20260517.json", "r", encoding="utf-8"))


def is_real_bad(r):
    c = r["code"]
    if c < 0:
        return True
    if c >= 500:
        return True
    if c == 404:
        return True
    return False


results = d["results"]
real_bad = [r for r in results if is_real_bad(r)]
real_ok = len(results) - len(real_bad)
print(f"Total: {len(results)}  Reachable (endpoint exists, incl 401/422): {real_ok}  Unreachable (404/5xx): {len(real_bad)}")

# Classify 404s
admin_api404 = [r for r in real_bad if "/api/admin/api/" in r["url"]]
print(f"  404 from /api/admin/api/ (regex artefact – duplicate /api/ from include_router prefix scanning): {len(admin_api404)}")

others = [r for r in real_bad if r not in admin_api404]
print(f"  Other 404/5xx ({len(others)}):")
for r in others:
    print(f"    {r['code']:4} {r['method']:5} {r['url']}")

# Check critical paths
print("\n=== CRITICAL LINKS ===")
critical_must_pass = [
    "/",
    "/api/health",
    "/ai-home",
    "/ai-chat",
    "/login",
]
BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
for path in critical_must_pass:
    url = BASE + path
    found = None
    for r in results:
        if r["url"] == url:
            found = r
            break
    if found:
        print(f"  [{found['code']}] ok={found['ok']}  {url}")
    else:
        print(f"  [N/A]  {url} (not in scan)")
