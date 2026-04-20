"""Check reachability of H5 + backend URLs after deployment."""
import json
import urllib.request
import urllib.error
import ssl
import time

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

URLS = [
    ("H5 root", f"{BASE}/"),
    ("H5 login", f"{BASE}/login"),
    ("H5 home tab", f"{BASE}/home"),
    ("Admin", f"{BASE}/admin"),
    ("Admin (trailing)", f"{BASE}/admin/"),
    ("API home-config", f"{BASE}/api/home-config"),
    ("API home-banners", f"{BASE}/api/home-banners"),
    ("API home-menus", f"{BASE}/api/home-menus"),
    ("API content articles", f"{BASE}/api/content/articles?page=1&page_size=3"),
    ("API health", f"{BASE}/api/health"),
]


def check(url, timeout=15):
    """Return (status_code, body_preview, err)."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "deploy-link-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = resp.status
            data = resp.read(400)
            return status, data.decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read(400).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body, None
    except Exception as e:
        return None, "", str(e)


def judge(status, err):
    if err:
        return "FAIL", err
    if status is None:
        return "FAIL", "no status"
    if 200 <= status < 300:
        return "PASS", f"{status}"
    if 300 <= status < 400:
        return "PASS", f"redirect {status}"
    if status in (401, 403):
        return "PASS", f"auth required {status}"
    if status == 404:
        return "FAIL", "404"
    if 500 <= status < 600:
        return "FAIL", f"server {status}"
    return "FAIL", f"unexpected {status}"


def main():
    results = []
    print(f"Checking {len(URLS)} URLs...")
    for name, url in URLS:
        status, body, err = check(url)
        verdict, reason = judge(status, err)
        preview = body.replace("\n", " ")[:100]
        line = f"[{verdict}] {name:20s} {status!s:5s} - {reason} | {url}"
        print(line)
        if preview:
            print(f"    body: {preview}")
        results.append({
            "name": name,
            "url": url,
            "status": status,
            "verdict": verdict,
            "reason": reason,
            "body_preview": preview,
            "error": err,
        })
    print()
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")
    print(f"=== Summary: {passed}/{len(URLS)} PASS, {failed} FAIL ===")
    with open("deploy/link_check_home3bugs_result.json", "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "failed": failed, "results": results}, f, ensure_ascii=False, indent=2)
    return failed == 0


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
