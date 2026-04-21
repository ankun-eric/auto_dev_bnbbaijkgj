"""完整验证 bug-fix v7 部署后的关键链接 + API 数据正确性。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = "newbb.test.bangbangvip.com"
BASE = f"/autodev/{DEPLOY_ID}"


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)

    def run(cmd, quiet=False):
        _, stdout, stderr = c.exec_command(cmd, timeout=60)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        if not quiet:
            if out:
                print(out.rstrip())
            if err:
                print(f"[stderr] {err.rstrip()}")
        return out, err, code

    print("=" * 60)
    print("1. H5 页面 GET 检查（含跟随重定向）")
    print("=" * 60)
    h5_paths = [
        "/h5/",
        "/h5/home",
        "/h5/points",
        "/h5/ai",
        "/h5/profile",
        "/h5/profile/edit",
        "/h5/services",
        "/h5/unified-orders",
        "/h5/messages",
        "/h5/search",
    ]
    for p in h5_paths:
        url = f"https://{DOMAIN}{BASE}{p}"
        out, _, _ = run(f"curl -sL -o /dev/null -w '%{{http_code}}' '{url}'", quiet=True)
        status = "OK" if out.strip() in ("200", "301", "302", "307", "308") else "FAIL"
        print(f"  [{status}] {out.strip()}  {url}")

    print()
    print("=" * 60)
    print("2. 关键 API GET 检查")
    print("=" * 60)
    apis = [
        "/api/health",
        "/api/home-config",
        "/api/settings/logo",
        "/api/h5/bottom-nav",
    ]
    for p in apis:
        url = f"https://{DOMAIN}{BASE}{p}"
        out, _, _ = run(f"curl -s -o /dev/null -w '%{{http_code}}' '{url}'", quiet=True)
        status = "OK" if out.strip() == "200" else "FAIL"
        print(f"  [{status}] {out.strip()}  {url}")

    print()
    print("=" * 60)
    print("3. /api/home-config 返回 placeholder 是否为新文案")
    print("=" * 60)
    url = f"https://{DOMAIN}{BASE}/api/home-config"
    out, _, _ = run(f"curl -s '{url}'", quiet=True)
    print(out[:500])
    if "搜索您想要的健康服务" in out:
        print("  ✓ placeholder 为新文案「搜索您想要的健康服务」")
    else:
        print("  ✗ placeholder 文案不正确")

    print()
    print("=" * 60)
    print("4. DB 中 home_search_placeholder 直接核对")
    print("=" * 60)
    sql = "SELECT config_key, LEFT(config_value, 60) FROM system_config WHERE config_key IN ('home_search_placeholder','placeholder_v7_normalized');"
    out, err, code = run(
        f"docker exec {DEPLOY_ID}-db mysql -u root -proot bini_health_db -e \"{sql}\" 2>&1 | grep -v 'Using a password'",
    )

    print()
    print("=" * 60)
    print("5. 后端最近 30 条访问日志（确认 v7 迁移成功）")
    print("=" * 60)
    run(f"docker logs {DEPLOY_ID}-backend 2>&1 | grep -i 'v7\\|placeholder\\|migrate' | tail -20")

    c.close()


if __name__ == "__main__":
    main()
