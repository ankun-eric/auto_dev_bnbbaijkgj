"""End-to-end verify: 前端页面加载 + 后端登录接口能通"""
import sys
sys.path.insert(0, ".")
from _ssh_helper import run

base = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

print("\n========== 前端页面加载验证 ==========")
front_checks = [
    ("H5 根", f"{base}/"),
    ("Admin 根 (跟随301/308)", f"{base}/admin"),
    ("Admin /login 登录页", f"{base}/admin/login"),
]
for name, url in front_checks:
    rc, out, _ = run(f"curl -skL -o /tmp/_b.out -w 'HTTP %{{http_code}}  size=%{{size_download}}\\n' '{url}'", timeout=20)
    print(f"\n--- {name} ---")
    print(out.strip())
    rc, body, _ = run("head -c 400 /tmp/_b.out", timeout=10)
    snippet = body.replace("\n", " ").strip()[:400]
    print("body:", snippet)
    is_html = "<!DOCTYPE" in body or "<html" in body
    print("HTML?", is_html)

print("\n\n========== 后端登录接口验证（POST，应非404）==========")
# 尝试几个可能的登录接口
endpoints = [
    "/api/admin/login",
    "/api/auth/login",
    "/api/v1/admin/login",
    "/api/v1/auth/login",
]
for ep in endpoints:
    url = base + ep
    rc, out, _ = run(
        f"curl -sk -o /tmp/_b.out -w 'HTTP %{{http_code}}\\n' -X POST -H 'Content-Type: application/json' -d '{{}}' '{url}'",
        timeout=20)
    rc2, body, _ = run("head -c 250 /tmp/_b.out", timeout=10)
    print(f"\nPOST {ep}: {out.strip()}  body={body.strip()[:200]}")
