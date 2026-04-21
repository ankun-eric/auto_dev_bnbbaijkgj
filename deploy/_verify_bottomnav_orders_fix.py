"""验证部署结果：
- 检查 backend 日志中的 bottom_nav_migration 输出
- 访问关键路由验证 200 状态
- 查询 DB 验证迁移结果
"""
import paramiko
import urllib.request
import urllib.error
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def ssh_run(ssh, cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    ec = stdout.channel.recv_exit_status()
    return ec, out, err


def http_check(url):
    req = urllib.request.Request(url, headers={"User-Agent": "deploy-check/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        return resp.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.reason
    except Exception as e:
        return 0, str(e)


def main():
    # 等待 backend 完全启动
    print("[*] 等待 backend 完全启动 30s ...")
    time.sleep(30)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    try:
        print("\n=== 1) 后端迁移日志 ===")
        ec, out, _ = ssh_run(
            ssh,
            f"docker logs {DEPLOY_ID}-backend 2>&1 | grep -iE 'bottom_nav|migration' | tail -30",
        )
        print(out or "(无迁移日志输出 - 说明 DB 中无需迁移的记录，属正常情况)")

        print("\n=== 2) DB 校验：bottom_nav_config 表中 name=订单 的路径 ===")
        sql = "SELECT id, name, path, is_visible FROM bottom_nav_config WHERE name IN ('订单','我的订单','Orders') OR path LIKE '%orders%';"
        cmd = (
            f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 "
            f"-e \"USE bini_health; {sql}\" 2>&1 | grep -v 'Using a password'"
        )
        ec, out, _ = ssh_run(ssh, cmd)
        print(out)

        print("\n=== 3) 查看最近 40 行 backend 日志（检查启动状态） ===")
        ec, out, _ = ssh_run(
            ssh, f"docker logs {DEPLOY_ID}-backend 2>&1 | tail -40"
        )
        print(out)

    finally:
        ssh.close()

    print("\n=== 4) 外网 HTTP 可达性检查 ===")
    urls = [
        (f"{BASE}/admin/bottom-nav", "admin 底部导航配置页"),
        (f"{BASE}/admin/login", "admin 登录页"),
        (f"{BASE}/api/bottom-nav/", "后端 API 底部导航"),
        (f"{BASE}/unified-orders", "H5 订单页（新路径）"),
        (f"{BASE}/", "H5 首页"),
    ]
    fails = []
    for url, name in urls:
        code, msg = http_check(url)
        mark = "OK" if code in (200, 301, 302, 307, 308) else "FAIL"
        print(f"  [{mark}] {code} {name}: {url}  {msg}")
        if mark == "FAIL":
            fails.append((url, code, msg))

    if fails:
        print("\n[-] 存在不可达 URL，请排查")
        for u in fails:
            print("   -", u)
    else:
        print("\n[+] 全部关键链接可达")


if __name__ == "__main__":
    main()
