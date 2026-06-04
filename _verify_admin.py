from _ssh_helper import run

ADMIN = "6b099ed3-7175-4a78-91f4-44570c84ed27-admin"
BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

def step(title, cmd, timeout=60):
    print(f"\n========== {title} ==========")
    rc, out, err = run(cmd, timeout=timeout)
    print(out)
    if err.strip():
        print("[stderr]", err[-400:])
    return out

# 网关重新解析 + reload
step("网关重新解析admin", f"sudo docker exec gateway-nginx getent hosts {ADMIN}")
step("reload网关", "sudo docker exec gateway-nginx nginx -s reload 2>&1; echo reload=$?")
step("网关内连admin(应200)", f"sudo docker exec gateway-nginx wget -qO- -T5 'http://{ADMIN}:3000//admin/' 2>&1 | head -c 200; echo; echo RC=$?")

print("\n========== 外部HTTPS最终验证 ==========")
for p in ["/admin/", "/admin/login", "/admin/home-safety", "/admin/_next/static/", "/", "/ai-home/"]:
    rc, out, err = run(f"curl -sk -o /dev/null -w 'HTTP %{{http_code}}' '{BASE}{p}'", timeout=30)
    print(f"{p:30s} -> {out.strip()}")

print("\n========== admin首页正文抽样 ==========")
rc, out, err = run(f"curl -sk '{BASE}/admin/' | head -c 500", timeout=30)
print(out)
