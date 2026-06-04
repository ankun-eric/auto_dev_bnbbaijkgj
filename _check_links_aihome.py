import urllib.request, ssl

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
ctx = ssl.create_default_context()

links = [
    ("frontend root", "GET", f"{BASE}/"),
    ("ai-home page", "GET", f"{BASE}/ai-home"),
    ("backend health", "GET", f"{BASE}/api/health"),
    ("login page", "GET", f"{BASE}/login"),
    ("report-history", "GET", f"{BASE}/report-history"),
]

ok = 0
fail = 0
for name, method, url in links:
    try:
        req = urllib.request.Request(url, method=method, headers={"User-Agent": "deploy-check"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            code = r.status
            body = r.read(2000).decode("utf-8", "ignore")
        verdict = "OK" if code in (200, 405) else "CHECK"
        if code in (200, 405):
            ok += 1
        else:
            fail += 1
        print(f"[{verdict}] {code} {name} -> {url}")
    except urllib.error.HTTPError as e:
        if e.code in (200, 405):
            ok += 1
            print(f"[OK] {e.code} {name} -> {url}")
        else:
            fail += 1
            print(f"[FAIL] HTTP {e.code} {name} -> {url}")
    except Exception as e:
        fail += 1
        print(f"[FAIL] {type(e).__name__}: {e} {name} -> {url}")

print(f"\nSummary: {ok} reachable, {fail} failed")
