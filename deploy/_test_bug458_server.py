"""[BUG-458] 服务器侧非 UI 自动化测试脚本

通过 SSH 连接到部署服务器，对已构建的 .next 静态产物（h5-web 容器内）做关键代码片段
检索，验证 BUG-458 修复后的关键 testid / 布局规则确实进入到了线上构建产物中，避免改了
源码却没真正上线的情况。

10 项断言：
  T01  / 路径可达
  T02  /ai-home 路径可达
  T03  bh-sidebar-top-row testid 进入 .next 产物（顶栏行容器存在）
  T04  bh-user-nameblock testid 进入 .next 产物（名片块容器存在）
  T05  bh-id-capsule testid 进入 .next 产物（ID 胶囊存在）
  T06  bh-icon-bell testid 进入 .next 产物（铃铛存在）
  T07  bh-icon-settings testid 进入 .next 产物（设置存在）
  T08  BUG-458 注释标记进入远端源码（说明修复版源码已部署）
  T09  ID 胶囊不再带「📋 复制」相关代码（onClick 复制 / Toast 'ID 已复制' 全部下线）
  T10  顶栏「⊞ 会员二维码」入口仍然处于下线状态（BUG-457 不回归）
"""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
H5_CONTAINER = f"{DEPLOY_ID}-h5"


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 60) -> tuple[int, str]:
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out


def grep_in_next(cli: paramiko.SSHClient, needle: str) -> int:
    """在 h5 容器的 .next 目录中搜索关键字，返回命中文件数。"""
    rc, out = run(
        cli,
        f"docker exec {H5_CONTAINER} sh -c "
        f"'grep -rl \"{needle}\" /app/.next 2>/dev/null | wc -l'",
    )
    try:
        return int((out or "0").strip())
    except ValueError:
        return 0


def http_code(cli: paramiko.SSHClient, url: str) -> str:
    rc, out = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {url}")
    return (out or "").strip()


def assert_pass(name: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{(' — ' + detail) if detail else ''}")
    return ok


def main() -> int:
    cli = ssh_connect()
    try:
        results: list[bool] = []

        # T01 / 200
        code = http_code(cli, f"{BASE_URL}/")
        results.append(assert_pass("T01 / 200", code == "200", f"http={code}"))

        # T02 /ai-home 308 (未登录) 或 200 — 都接受
        code = http_code(cli, f"{BASE_URL}/ai-home")
        results.append(
            assert_pass(
                "T02 /ai-home 可达",
                code.startswith("2") or code.startswith("3"),
                f"http={code}",
            )
        )

        # T03 顶栏行容器
        n = grep_in_next(cli, "bh-sidebar-top-row")
        results.append(assert_pass("T03 bh-sidebar-top-row 进入 .next", n >= 1, f"hits={n}"))

        # T04 名片块容器
        n = grep_in_next(cli, "bh-user-nameblock")
        results.append(assert_pass("T04 bh-user-nameblock 进入 .next", n >= 1, f"hits={n}"))

        # T05 ID 胶囊
        n = grep_in_next(cli, "bh-id-capsule")
        results.append(assert_pass("T05 bh-id-capsule 进入 .next", n >= 1, f"hits={n}"))

        # T06 铃铛
        n = grep_in_next(cli, "bh-icon-bell")
        results.append(assert_pass("T06 bh-icon-bell 进入 .next", n >= 1, f"hits={n}"))

        # T07 设置
        n = grep_in_next(cli, "bh-icon-settings")
        results.append(assert_pass("T07 bh-icon-settings 进入 .next", n >= 1, f"hits={n}"))

        # T08 远端源码包含 BUG-458 标记 ≥1
        rc, out = run(
            cli,
            f"grep -c 'BUG-458' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        n = int((out or "0").strip() or "0")
        results.append(assert_pass("T08 远端源码包含 BUG-458 标记", n >= 1, f"count={n}"))

        # T09 ID 胶囊「ID 已复制」Toast 文案彻底下线
        n_copy_toast = grep_in_next(cli, "ID 已复制")
        n_copy_id = grep_in_next(cli, "handleCopyId")
        results.append(
            assert_pass(
                "T09 ID 胶囊复制功能已下线",
                n_copy_toast == 0 and n_copy_id == 0,
                f"copyToast={n_copy_toast}, handleCopyId={n_copy_id}",
            )
        )

        # T10 「会员二维码」⊞ 入口仍下线（BUG-457 不回归）
        n_qrcode = grep_in_next(cli, "bh-icon-qrcode")
        results.append(
            assert_pass(
                "T10 顶栏 ⊞ 二维码入口仍下线",
                n_qrcode == 0,
                f"hits={n_qrcode}",
            )
        )

        passed = sum(1 for r in results if r)
        total = len(results)
        print()
        print(f"[SUMMARY] {passed}/{total} PASS")
        return 0 if passed == total else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
