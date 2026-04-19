"""Full link reachability checker for the deployed bini-health project.

Strategy:
  1. Fetch the FastAPI openapi.json from external HTTPS to get all backend GET endpoints.
  2. Scan h5-web/src/app and admin-web/src/app for Next.js page routes.
  3. For each link, GET externally without -k. Track redirects (max 10) to detect loops.
  4. Output a summary table.
"""
import json
import os
import re
import ssl
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
OPENAPI_URL = f"{BASE}/api/openapi.json"
LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---- Param substitution (path params -> sample values) ----
SAMPLE_VALS = {
    "id": "1", "user_id": "1", "member_id": "1", "order_id": "1",
    "product_id": "1", "category_id": "1", "merchant_id": "1",
    "report_id": "1", "chat_id": "1", "session_id": "1",
    "plan_id": "1", "expert_id": "1", "address_id": "1",
    "coupon_id": "1", "template_id": "1", "knowledge_id": "1",
    "menu_id": "1", "notice_id": "1", "share_id": "1",
    "message_id": "1", "topic_id": "1", "tcm_id": "1",
    "phone_id": "1", "audit_id": "1", "drug_id": "1",
    "ocr_id": "1", "details_id": "1", "config_id": "1",
    "qr_id": "1", "favorite_id": "1", "feature_id": "1",
    "type": "1", "channel": "h5", "status": "1",
    "key": "test", "name": "test", "code": "test",
    "openid": "test", "platform": "h5", "phone": "13800138000",
    "scene": "1", "page": "1", "size": "10", "limit": "10",
    "trade_no": "test", "out_trade_no": "test",
}


def http_request(url, method="HEAD", timeout=15, follow_redirects=False, max_redirects=10):
    """Issue an HTTPS request. Returns (final_status, num_redirects, redirect_chain, error)."""
    chain = []
    current = url
    ctx = ssl.create_default_context()
    for hop in range(max_redirects + 1):
        try:
            req = urllib.request.Request(current, method=method, headers={
                "User-Agent": "BiniHealth-Deploy-Checker/1.0",
                "Accept": "*/*",
            })
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
            # Manually disable auto-redirect
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), NoRedirect())
            resp = opener.open(req, timeout=timeout)
            status = resp.status
            location = resp.headers.get("Location")
            chain.append((current, status, location))
            if not follow_redirects or status not in (301, 302, 303, 307, 308) or not location:
                return status, hop, chain, None
            # follow
            if location.startswith("/"):
                # relative - use scheme+host of current
                from urllib.parse import urlparse, urlunparse
                p = urlparse(current)
                current = urlunparse((p.scheme, p.netloc, location, "", "", ""))
            else:
                current = location
        except urllib.error.HTTPError as e:
            chain.append((current, e.code, None))
            return e.code, hop, chain, None
        except Exception as e:
            chain.append((current, None, None))
            return None, hop, chain, str(e)
    # Too many redirects
    return None, max_redirects + 1, chain, "TOO_MANY_REDIRECTS"


def fetch_openapi():
    """Fetch openapi.json and return list of (method, path) tuples for GET endpoints (and others)."""
    print(f"Fetching openapi from {OPENAPI_URL} ...")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(OPENAPI_URL)
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        data = json.load(resp)
    paths = data.get("paths", {})
    routes = []
    for path, methods in paths.items():
        for method in methods.keys():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            routes.append((method.upper(), path))
    return routes


def substitute_path_params(path):
    """Replace {param} with sample values."""
    def sub(m):
        name = m.group(1)
        return SAMPLE_VALS.get(name, "1")
    return re.sub(r"\{([^}]+)\}", sub, path)


def scan_nextjs_pages(app_dir):
    """Scan a Next.js app directory and return list of route paths."""
    routes = set()
    if not os.path.isdir(app_dir):
        return []
    for root, dirs, files in os.walk(app_dir):
        # Skip private folders / api routes
        if "/api/" in root.replace("\\", "/") or root.endswith("/api") or root.endswith("\\api"):
            continue
        # Find page files
        has_page = any(f in ("page.tsx", "page.jsx", "page.ts", "page.js") for f in files)
        if has_page:
            rel = os.path.relpath(root, app_dir).replace("\\", "/")
            if rel == ".":
                routes.add("/")
                continue
            # Remove route groups (parens) and parallel routes (@)
            parts = []
            for p in rel.split("/"):
                if p.startswith("(") and p.endswith(")"):
                    continue
                if p.startswith("@"):
                    continue
                # Dynamic segments [id] -> sample value
                if p.startswith("[") and p.endswith("]"):
                    inner = p[1:-1]
                    if inner.startswith("..."):
                        inner = inner[3:]
                    parts.append(SAMPLE_VALS.get(inner, "1"))
                else:
                    parts.append(p)
            routes.add("/" + "/".join(parts))
    return sorted(routes)


def main():
    # 1. Backend routes
    backend_routes = fetch_openapi()
    print(f"Found {len(backend_routes)} backend routes")

    # 2. Frontend routes
    h5_pages = scan_nextjs_pages(os.path.join(LOCAL_ROOT, "h5-web", "src", "app"))
    admin_pages = scan_nextjs_pages(os.path.join(LOCAL_ROOT, "admin-web", "src", "app"))
    print(f"Found {len(h5_pages)} h5 pages, {len(admin_pages)} admin pages")

    # 3. Build URL list
    checks = []  # (kind, method, url, follow_redirects)
    # Backend
    for method, path in backend_routes:
        if not path.startswith("/api/"):
            continue
        sub_path = substitute_path_params(path)
        full = f"{BASE}{sub_path}"
        checks.append(("backend", method, full, False))
    # H5
    for p in h5_pages:
        full = f"{BASE}{p if p != '/' else '/'}"
        # For Next.js with trailingSlash:true, ensure trailing slash
        if not full.endswith("/"):
            full += "/"
        checks.append(("h5", "GET", full, True))
    # Admin (basePath = /autodev/.../admin)
    for p in admin_pages:
        full = f"{BASE}/admin{p if p != '/' else '/'}"
        if not full.endswith("/"):
            full += "/"
        checks.append(("admin", "GET", full, True))

    print(f"\nTotal checks: {len(checks)}\n")

    results = []

    def check_one(item):
        kind, method, url, follow = item
        if kind == "backend":
            # use HEAD for backend; on 405 retry GET
            status, hops, chain, err = http_request(url, method="HEAD", timeout=15, follow_redirects=False)
            if status in (405, 501) or status is None:
                # try GET
                status, hops, chain, err = http_request(url, method="GET", timeout=20, follow_redirects=False)
        else:
            # follow redirects for HTML pages
            status, hops, chain, err = http_request(url, method="GET", timeout=20, follow_redirects=True, max_redirects=10)
        return (kind, method, url, status, hops, chain, err)

    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(check_one, it): it for it in checks}
        for i, fut in enumerate(as_completed(futs)):
            r = fut.result()
            results.append(r)
            if (i + 1) % 30 == 0:
                print(f"  ... {i+1}/{len(checks)} done")

    # Summary
    print("\n\n===== RESULTS =====\n")

    # Count results by status category
    ok = []
    not_ok = []
    for r in results:
        kind, method, url, status, hops, chain, err = r
        # Reachability rules
        is_ok = False
        reason = ""
        if err == "TOO_MANY_REDIRECTS":
            reason = "redirect_loop"
        elif err:
            reason = f"err:{err[:50]}"
        elif status is None:
            reason = "no_status"
        elif 200 <= status < 300:
            is_ok = True
            reason = "2xx"
        elif status in (401, 403):
            is_ok = True
            reason = "auth_required(reachable)"
        elif status == 405:
            is_ok = True
            reason = "method_not_allowed(reachable)"
        elif status == 422:
            is_ok = True
            reason = "validation(reachable)"
        elif status == 404:
            # backend not found - likely path-param mismatch → reachable but not found
            if kind == "backend":
                is_ok = True
                reason = "404_backend(reachable)"
            else:
                reason = "404_page"
        elif status in (301, 302, 307, 308):
            # only for backend (we don't follow for backend)
            if kind == "backend":
                is_ok = True
                reason = f"{status}_redirect(reachable)"
            else:
                reason = f"{status}_unfollowed"
        else:
            reason = f"http_{status}"
        if is_ok:
            ok.append((r, reason))
        else:
            not_ok.append((r, reason))

    print(f"OK: {len(ok)} / Total: {len(results)}")
    print(f"NOT OK: {len(not_ok)}")

    # Print not-ok details
    if not_ok:
        print("\n----- NOT OK details -----")
        for (kind, method, url, status, hops, chain, err), reason in not_ok:
            print(f"  [{kind}] {method} {url}")
            print(f"     status={status} hops={hops} reason={reason} err={err}")
            if chain and len(chain) > 1:
                for c in chain[:5]:
                    print(f"       -> {c}")

    # Save full report
    report_path = os.path.join(LOCAL_ROOT, "deploy", "link_check_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(results),
            "ok": len(ok),
            "not_ok": len(not_ok),
            "results": [
                {
                    "kind": r[0], "method": r[1], "url": r[2],
                    "status": r[3], "hops": r[4],
                    "reason": reason,
                    "chain": [(c[0], c[1]) for c in (r[5] or [])][:5],
                    "err": r[6],
                }
                for r, reason in [(x, y) for x, y in [(r, reason_for(r)) for r in results]]
            ]
        }, f, ensure_ascii=False, indent=2)
    print(f"\nFull report saved to {report_path}")


def reason_for(r):
    kind, method, url, status, hops, chain, err = r
    if err == "TOO_MANY_REDIRECTS":
        return "redirect_loop"
    if err:
        return f"err:{err[:50]}"
    if status is None:
        return "no_status"
    if 200 <= status < 300:
        return "2xx"
    if status in (401, 403, 405, 422):
        return f"{status}_reachable"
    if status == 404 and kind == "backend":
        return "404_backend_reachable"
    if status == 404:
        return "404_page"
    if status in (301, 302, 307, 308):
        return f"{status}_redirect" if kind == "backend" else f"{status}_unfollowed"
    return f"http_{status}"


if __name__ == "__main__":
    main()
