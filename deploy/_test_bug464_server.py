"""[BUG-464] 服务器侧非UI自动化测试

目标：在服务器上验证全局 Toast 修复的 CSS 已被 Next.js 构建并打包到产物中。

验证项：
1. 容器 running
2. 源码 globals.css 含 BUG-464 标记
3. 构建产物（standalone 下的 .next/static/css/*.css）含 .adm-toast-main-icon flex-direction:column
4. 主要受影响页面均可访问
"""
from __future__ import annotations

import sys

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 120) -> tuple[int, str, str]:
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def main() -> int:
    cli = ssh_connect()
    results: list[tuple[str, bool, str]] = []
    try:
        # 1. 容器 running
        _, out, _ = run(
            cli,
            f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-h5",
        )
        status = (out or "").strip()
        results.append(("h5 container running", status == "running", status))

        # 2. globals.css 源码 BUG-464 标记
        _, out, _ = run(
            cli,
            f"grep -c 'BUG-464' {REMOTE_PROJ}/h5-web/src/app/globals.css",
        )
        c = (out or "0").strip()
        results.append(("globals.css has BUG-464 marker", int(c or "0") >= 1, c))

        # 3. globals.css 源码 .adm-toast-main-icon 选择器
        _, out, _ = run(
            cli,
            f"grep -c 'adm-toast-main-icon' {REMOTE_PROJ}/h5-web/src/app/globals.css",
        )
        c = (out or "0").strip()
        results.append(
            ("globals.css has adm-toast-main-icon selector", int(c or "0") >= 1, c)
        )

        # 4. globals.css 源码 flex-direction: column
        _, out, _ = run(
            cli,
            f"grep -c 'flex-direction: column' {REMOTE_PROJ}/h5-web/src/app/globals.css",
        )
        c = (out or "0").strip()
        results.append(
            ("globals.css has flex-direction: column", int(c or "0") >= 1, c)
        )

        # 5. 容器内构建产物 css 中含 adm-toast-main-icon flex column 样式
        #    Next.js 会把 globals.css 编译进 .next/static/css/*.css
        cmd = (
            f"docker exec {DEPLOY_ID}-h5 sh -c "
            f"\"grep -l 'adm-toast-main-icon' /app/.next/static/css/*.css 2>/dev/null | wc -l\""
        )
        _, out, _ = run(cli, cmd)
        c = (out or "0").strip()
        results.append(("built css contains adm-toast-main-icon", int(c or "0") >= 1, c))

        cmd = (
            f"docker exec {DEPLOY_ID}-h5 sh -c "
            f"\"grep -El 'adm-toast-main-icon[^{{]*\\{{[^}}]*flex' /app/.next/static/css/*.css 2>/dev/null | wc -l\""
        )
        _, out, _ = run(cli, cmd)
        c = (out or "0").strip()
        results.append(
            ("built css has flex rule around adm-toast-main-icon", int(c or "0") >= 1, c)
        )

        # 6. 主要页面可访问
        for u in [
            f"{BASE_URL}/",
            f"{BASE_URL}/login",
            f"{BASE_URL}/unified-orders",
            f"{BASE_URL}/my-coupons",
            f"{BASE_URL}/health-profile",
        ]:
            _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {u}")
            code = (out or "").strip()
            ok = code.startswith("2") or code.startswith("3") or code in {"401", "403"}
            results.append((f"URL reachable {u}", ok, code))

        passed = sum(1 for _, ok, _ in results if ok)
        total = len(results)
        print(f"\n=== BUG-464 Server Test: {passed}/{total} PASS ===")
        for name, ok, detail in results:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {name} -> {detail}")
        return 0 if passed == total else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
