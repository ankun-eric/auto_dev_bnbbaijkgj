"""[BUGFIX HS-V2-ALTER 2026-05-28] 修复后 smoke：直接探测三个之前 500 的接口，期望不再 500。"""
import paramiko, json

HOST = "newbb.test.bangbangvip.com"
DEPLOY = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://{HOST}/autodev/{DEPLOY}"

ENDPOINTS = [
    ("GET",  f"{BASE}/api/admin/home_safety/callback_log?page=1&size=20", "回调原始记录列表"),
    ("GET",  f"{BASE}/api/admin/home_safety/callback_config",             "回调地址配置加载"),
    ("GET",  f"{BASE}/api/admin/home_safety/callback_config/precheck",    "回调地址自检接口"),
]

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="ubuntu", password="Newbang888", timeout=30)

    print("=== 修复后 HTTP smoke（在服务器上 curl，避免被外网防护扰动）===\n")
    all_ok = True
    for method, url, name in ENDPOINTS:
        cmd = f'curl -s -o /tmp/resp.txt -w "%{{http_code}}" -X {method} "{url}" && echo "---" && head -c 400 /tmp/resp.txt'
        _, o, _ = ssh.exec_command(cmd, timeout=20)
        out = o.read().decode("utf-8", errors="replace")
        code = out.split("---")[0].strip()
        body = out.split("---", 1)[1].strip() if "---" in out else ""
        # 期望：401（未带 token，鉴权拦截，但已脱离 500 异常） 而不是 500
        verdict = "PASS（未鉴权 401，业务侧不再 500）" if code == "401" else (
                  "FAIL（仍 500）" if code == "500" else f"UNEXPECTED {code}")
        if code != "401":
            all_ok = False
        print(f"[{verdict}] {name}\n  {method} {url}\n  HTTP {code}  body: {body[:200]}\n")

    print("=== 后端容器最近 30 行日志（确认没有 OperationalError）===")
    _, o, _ = ssh.exec_command(
        f"docker logs --tail 30 {DEPLOY}-backend 2>&1 | tail -30", timeout=15)
    print(o.read().decode("utf-8", errors="replace"))

    ssh.close()
    print(f"\n[最终] {'ALL PASS' if all_ok else 'CHECK NEEDED'}")

if __name__ == "__main__":
    main()
