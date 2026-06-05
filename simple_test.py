import subprocess, json, sys, time

with open("test_urls.txt") as f:
    urls = [l.strip() for l in f if l.strip()]

results = []
for i, url in enumerate(urls):
    sys.stdout.write(f"[{i+1}/{len(urls)}] ")
    sys.stdout.flush()
    try:
        r = subprocess.run(
            ["curl", "-sI", "-L", "--connect-timeout", "5", "--max-time", "10", "--max-redirs", "10", url],
            capture_output=True, text=True, timeout=15
        )
        out = r.stdout
        codes = []
        for line in out.split('\n'):
            if line.startswith('HTTP/'):
                codes.append(line.split()[1])
        if codes:
            final = codes[-1]
            redirects = sum(1 for c in codes if c.startswith('3'))
            if redirects >= 10:
                print(f"LOOP  | {url}")
                results.append({"url": url, "status": "LOOP", "http": int(final)})
            elif int(final) < 400 or int(final) == 405:
                print(f"OK {final} | {url}")
                results.append({"url": url, "status": "OK", "http": int(final), "redirects": redirects})
            else:
                print(f"ERR {final} | {url}")
                results.append({"url": url, "status": "HTTP_ERR", "http": int(final)})
        else:
            print(f"NORESP | {url}")
            results.append({"url": url, "status": "NO_RESPONSE"})
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT | {url}")
        results.append({"url": url, "status": "TIMEOUT"})
    except Exception as e:
        print(f"FAIL | {url} - {e}")
        results.append({"url": url, "status": "ERROR", "detail": str(e)[:100]})

print(f"\n=== 汇总 ===")
ok = [r for r in results if r["status"] == "OK" and r["http"] < 400]
api405 = [r for r in results if r["status"] == "OK" and r["http"] == 405]
bad = [r for r in results if r["status"] in ("HTTP_ERR", "LOOP")]
err = [r for r in results if r["status"] in ("NO_RESPONSE", "TIMEOUT", "ERROR")]
print(f"✅ 可达: {len(ok)}")
print(f"⚠️  405: {len(api405)}")
print(f"❌ 不可达: {len(bad)}")
print(f"💥 失败: {len(err)}")

if bad:
    print("\n不可达:")
    for r in bad:
        print(f"  {r['http']} {r['url']}")
if err:
    print("\n失败:")
    for r in err:
        print(f"  {r['status']} {r['url']}")

with open("simple_test_results.json", "w") as f:
    json.dump({"ok": ok, "api405": api405, "bad": bad, "err": err}, f, indent=2, ensure_ascii=False)
