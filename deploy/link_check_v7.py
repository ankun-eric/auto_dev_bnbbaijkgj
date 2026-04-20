"""完整链接可达性检查 - v7 bug-fix 部署后."""
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

    # H5 主要页面
    h5_paths = [
        "",
        "/home",
        "/points",
        "/points/records",
        "/ai",
        "/profile",
        "/profile/edit",
        "/health-profile",
        "/services",
        "/orders",
        "/messages",
        "/search",
        "/health-plan",
        "/my-coupons",
        "/invite",
    ]

    # API 端点
    api_paths = [
        "/api/health",
        "/api/home-config",
        "/api/settings/logo",
        "/api/h5/bottom-nav",
    ]

    print("=" * 70)
    print(f"H5 页面链接可达性检查 ({DOMAIN}{BASE})")
    print("=" * 70)
    ok_h5 = 0
    fail_h5 = 0
    for p in h5_paths:
        url = f"https://{DOMAIN}{BASE}{p}"
        cmd = f"curl -sL -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'"
        _, stdout, _ = c.exec_command(cmd, timeout=30)
        code = stdout.read().decode().strip()
        ok = code in ("200", "301", "302", "307", "308")
        flag = "[OK]  " if ok else "[FAIL]"
        if ok:
            ok_h5 += 1
        else:
            fail_h5 += 1
        print(f"  {flag} {code}  {url}")

    print()
    print("=" * 70)
    print(f"API 端点检查")
    print("=" * 70)
    ok_api = 0
    fail_api = 0
    for p in api_paths:
        url = f"https://{DOMAIN}{BASE}{p}"
        cmd = f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 '{url}'"
        _, stdout, _ = c.exec_command(cmd, timeout=30)
        code = stdout.read().decode().strip()
        ok = code == "200"
        flag = "[OK]  " if ok else "[FAIL]"
        if ok:
            ok_api += 1
        else:
            fail_api += 1
        print(f"  {flag} {code}  {url}")

    print()
    print("=" * 70)
    print(f"汇总: H5 {ok_h5}/{ok_h5+fail_h5} OK, API {ok_api}/{ok_api+fail_api} OK")
    print("=" * 70)

    # placeholder 数据校验
    print("\nplaceholder 校验:")
    cmd = f"curl -s --max-time 15 'https://{DOMAIN}{BASE}/api/home-config'"
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    body = stdout.read().decode()
    print(f"  {body[:200]}")
    if "搜索您想要的健康服务" in body:
        print("  ✓ Bug 2 修复验证通过：placeholder = '搜索您想要的健康服务'")
    else:
        print("  ✗ placeholder 文案未更新")

    c.close()
    return fail_h5 + fail_api == 0


if __name__ == "__main__":
    success = main()
    import sys
    sys.exit(0 if success else 1)
