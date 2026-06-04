"""Verify via HTTPS"""
import sys, time
sys.path.insert(0, ".")
from _ssh_helper import run

base = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
checks = [
    ("openapi.json (后端)", f"{base}/openapi.json"),
    ("api/ 根 (后端 — 期望 200 或 404 /api/ 路径无 GET)", f"{base}/api/"),
    ("docs (后端 swagger 期望 200)", f"{base}/docs"),
    ("admin 根", f"{base}/admin"),
    ("admin/login 登录页 (期望 200 HTML)", f"{base}/admin/login"),
    ("h5 根 (期望 200 HTML)", f"{base}/"),
]
for name, url in checks:
    print(f"\n=== {name} ===\n$ {url}")
    rc, out, err = run(f"curl -sk -o /tmp/_body.out -w 'HTTP %{{http_code}}  size=%{{size_download}}  time=%{{time_total}}s\\n' '{url}'", timeout=30)
    print(out.rstrip())
    rc2, out2, _ = run("head -c 300 /tmp/_body.out", timeout=10)
    print("body[head300]:", out2.replace("\n", " ").strip()[:300])
