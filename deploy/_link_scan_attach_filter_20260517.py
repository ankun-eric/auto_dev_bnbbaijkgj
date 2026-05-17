"""
Full link scan for the bug-fix deployment.

Extracts:
  - All backend FastAPI routes (GET-checkable subset)
  - All h5-web Next.js page routes (app/**/page.tsx)
Then runs external HTTPS curl on each, reports table + summary.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import ssl

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend" / "app"
H5_DIR = ROOT / "h5-web" / "src" / "app"

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


# ───────── Backend FastAPI scanning ─────────
RE_DECO = re.compile(r"@(?:app|router)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]")
RE_PREFIX = re.compile(r"APIRouter\(\s*prefix\s*=\s*['\"]([^'\"]+)['\"]")
RE_INCLUDE = re.compile(r"app\.include_router\(\s*([\w_\.]+)\s*(?:,\s*prefix\s*=\s*['\"]([^'\"]+)['\"])?")


def scan_backend_routes():
    routes = []
    # First pass: collect all (file -> router_prefix) by reading APIRouter declarations
    file_prefix = {}
    for py in BACKEND_DIR.rglob("*.py"):
        try:
            txt = py.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        m = RE_PREFIX.search(txt)
        if m:
            file_prefix[py.stem] = m.group(1)

    # Second pass: collect main.py include_router prefixes
    include_prefix = {}
    main_py = BACKEND_DIR / "main.py"
    if main_py.exists():
        main_txt = main_py.read_text("utf-8", errors="ignore")
        for inc in RE_INCLUDE.finditer(main_txt):
            mod_ref = inc.group(1)
            pre = inc.group(2) or ""
            short = mod_ref.split(".")[-1]
            # strip ".router" suffix
            if short.endswith("_router"):
                short = short[:-7]
            include_prefix[short] = pre

    # Third pass: all decorators
    for py in BACKEND_DIR.rglob("*.py"):
        try:
            txt = py.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        for m in RE_DECO.finditer(txt):
            method = m.group(1).upper()
            path = m.group(2)
            full = path
            # Handle router files: prepend prefix
            stem = py.stem
            if py.name != "main.py":
                router_prefix = file_prefix.get(stem, "")
                # include_router prefix from main.py
                # search any include_router referencing this module
                inc_pre = ""
                if main_py.exists():
                    # rough: match the module name
                    for mod, pre in include_prefix.items():
                        if mod == stem or mod == stem.replace("_", ""):
                            inc_pre = pre
                            break
                full = (inc_pre or "") + (router_prefix or "") + path
            routes.append((method, full, str(py.relative_to(ROOT))))
    return routes


# ───────── Next.js (app router) scanning ─────────
def scan_h5_routes():
    """Scan h5-web/src/app/**/page.tsx to get route paths."""
    routes = []
    if not H5_DIR.exists():
        return routes
    for page in H5_DIR.rglob("page.tsx"):
        rel = page.relative_to(H5_DIR).parent  # remove /page.tsx
        parts = rel.parts
        # Strip route groups (parens-wrapped folders like (ai-chat))
        kept = [p for p in parts if not (p.startswith("(") and p.endswith(")"))]
        # Replace dynamic [param] with sample value
        kept2 = []
        for p in kept:
            if p.startswith("[") and p.endswith("]"):
                kept2.append("1")  # sample value
            else:
                kept2.append(p)
        route = "/" + "/".join(kept2)
        if route == "/":
            route = "/"
        routes.append(("GET", route, str(page.relative_to(ROOT))))
    return routes


# ───────── HTTP checking ─────────
ctx = ssl.create_default_context()


def check_url(method: str, url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, method=method)
        req.add_header("User-Agent", "link-checker/1.0")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, r.headers.get("Location") or ""
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location", "") if e.headers else ""
    except urllib.error.URLError as e:
        return -1, str(e.reason)[:80]
    except Exception as e:
        return -2, str(e)[:80]


def is_reachable(code: int) -> bool:
    if code < 0:
        return False
    if 200 <= code < 400:
        return True
    if code == 405:
        return True  # method-not-allowed = endpoint exists
    return False


def main():
    print("=== Scanning backend routes ===")
    be = scan_backend_routes()
    # Filter: only GET methods (skip params we can't fill), exclude obviously dynamic-only
    be_get = []
    for m, p, src in be:
        if m != "GET":
            continue
        # exclude param-required routes we can't fill; replace simple {param} with 1
        if "{" in p:
            p2 = re.sub(r"\{[^}]+\}", "1", p)
        else:
            p2 = p
        # Skip internal admin-only with no public path (still test, they should 401/403=reachable)
        be_get.append((m, p2, src))
    print(f"  backend GET routes: {len(be_get)}")

    print("=== Scanning h5-web routes ===")
    fe = scan_h5_routes()
    print(f"  h5-web pages: {len(fe)}")

    # Build URL list with dedup
    seen = set()
    items = []
    # backend - all routes have /api prefix (FastAPI app-level routes mostly use /api/...)
    for m, p, src in be_get:
        # If path doesn't already start with /api, prepend it (heuristic for include_router-mounted)
        # We can't always know; only include those that already have a slash path
        if not p.startswith("/"):
            continue
        # Drop /admin/ for now? Keep all
        url = BASE + p
        if url in seen:
            continue
        seen.add(url)
        items.append(("backend", m, url, src))
    # frontend
    for m, p, src in fe:
        url = BASE + p
        if url in seen:
            continue
        seen.add(url)
        items.append(("frontend", m, url, src))

    print(f"\n=== Total URLs to check: {len(items)} ===\n")

    results = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(check_url, m, url): (kind, m, url, src) for (kind, m, url, src) in items}
        for fut in as_completed(futs):
            kind, m, url, src = futs[fut]
            try:
                code, loc = fut.result()
            except Exception as e:
                code, loc = -3, str(e)[:80]
            reachable = is_reachable(code)
            results.append({
                "kind": kind, "method": m, "url": url, "src": src,
                "code": code, "loc": loc, "ok": reachable,
            })

    # Sort & print
    results.sort(key=lambda r: (r["kind"], not r["ok"], r["url"]))
    ok_be = sum(1 for r in results if r["kind"] == "backend" and r["ok"])
    bad_be = sum(1 for r in results if r["kind"] == "backend" and not r["ok"])
    ok_fe = sum(1 for r in results if r["kind"] == "frontend" and r["ok"])
    bad_fe = sum(1 for r in results if r["kind"] == "frontend" and not r["ok"])
    total = len(results)

    # Print summary
    print(f"\n=== SUMMARY ===")
    print(f"  Total:    {total}")
    print(f"  Backend:  {ok_be}/{ok_be+bad_be} reachable")
    print(f"  Frontend: {ok_fe}/{ok_fe+bad_fe} reachable")
    print(f"  Reachable: {ok_be+ok_fe}/{total}")
    print(f"  Unreachable: {bad_be+bad_fe}/{total}")

    # Print unreachable details
    bad = [r for r in results if not r["ok"]]
    if bad:
        print(f"\n=== UNREACHABLE LINKS ({len(bad)}) ===")
        for r in bad[:200]:
            print(f"  [{r['code']}] {r['method']} {r['url']}  (src: {r['src']})")

    # Save report
    rpt_path = ROOT / "deploy" / "link_check_attach_filter_20260517.json"
    with open(rpt_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": total,
            "reachable": ok_be + ok_fe,
            "unreachable": bad_be + bad_fe,
            "backend_ok": ok_be, "backend_bad": bad_be,
            "frontend_ok": ok_fe, "frontend_bad": bad_fe,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to {rpt_path}")

    # Also print critical-link results
    print("\n=== KEY LINKS ===")
    for must in [
        f"{BASE}/",
        f"{BASE}/api/health",
    ]:
        for r in results:
            if r["url"] == must:
                print(f"  [{r['code']}] {r['url']}  (ok={r['ok']})")
                break


if __name__ == "__main__":
    main()
