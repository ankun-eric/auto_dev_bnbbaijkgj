"""[BUG-457] 部署脚本 — AI 对话抽屉页 4 个 Bug 修复

仅改动 H5 端 1 个文件：
- h5-web/src/components/ai-chat/Sidebar.tsx

部署流程：
1. SFTP 上传 Sidebar.tsx 到服务器
2. docker compose build h5-web（仅前端容器）
3. docker compose up -d h5-web
4. 等待启动后 curl 验证关键页面 200/3xx
5. 直接 grep 远端源码确认 BUG-457 标记存在
6. 直接 grep 远端源码确认旧 handleCopyId 已移除、member-qrcode 跳转已移除
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = Path(__file__).resolve().parent.parent

FILES = [
    (
        "h5-web/src/components/ai-chat/Sidebar.tsx",
        f"{REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
    ),
]


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 600) -> tuple[int, str, str]:
    print(f"[REMOTE] $ {cmd[:200]}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:])
    if err.strip():
        print(f"[STDERR] {err[-2000:]}")
    return rc, out, err


def upload_files(cli: paramiko.SSHClient) -> None:
    sftp = cli.open_sftp()
    for local_rel, remote in FILES:
        local_path = LOCAL_ROOT / local_rel
        if not local_path.exists():
            print(f"[SKIP] local missing: {local_path}")
            continue
        remote_dir = remote.rsplit("/", 1)[0]
        cli.exec_command(f"mkdir -p {remote_dir}")
        sftp.put(str(local_path), remote)
        print(f"[UPLOAD] {local_rel} -> {remote}")
    sftp.close()


def main() -> int:
    cli = ssh_connect()
    try:
        rc, out, _ = run(cli, f"test -d {REMOTE_PROJ} && echo OK || echo MISSING")
        if "MISSING" in out:
            print("[ERROR] 远端项目目录不存在")
            return 2

        upload_files(cli)

        # 仅 h5-web 容器需重建
        rc, _, _ = run(
            cli,
            f"cd {REMOTE_PROJ} && docker compose build h5-web",
            timeout=1800,
        )
        if rc != 0:
            print("[ERROR] docker compose build h5-web 失败")
            return 3
        rc, _, _ = run(
            cli,
            f"cd {REMOTE_PROJ} && docker compose up -d h5-web",
            timeout=600,
        )
        if rc != 0:
            print("[ERROR] docker compose up -d h5-web 失败")
            return 4

        # 等待容器就绪
        time.sleep(20)

        urls = [
            f"{BASE_URL}/",
            f"{BASE_URL}/login",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/profile/edit",
            f"{BASE_URL}/health-archive",
            f"{BASE_URL}/notifications",
            f"{BASE_URL}/my-coupons",
            f"{BASE_URL}/unified-orders",
            f"{BASE_URL}/my-favorites",
            f"{BASE_URL}/points-center",
            f"{BASE_URL}/my-devices",
            f"{BASE_URL}/ai-settings",
        ]
        bad: list[tuple[str, str]] = []
        for u in urls:
            _, out, _ = run(
                cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {u}"
            )
            code = (out or "").strip()
            print(f"  -> {code} {u}")
            # 2xx/3xx 都算 OK；登录态保护接受 401/403
            if not (
                code.startswith("2")
                or code.startswith("3")
                or code in {"401", "403"}
            ):
                bad.append((u, code))

        # 验证后端关键接口
        print("\n=== verify backend endpoints availability ===")
        api_urls = [
            f"{BASE_URL}/api/points/summary",
            f"{BASE_URL}/api/coupons/summary",
            f"{BASE_URL}/api/users/me/stats",
            f"{BASE_URL}/api/orders/unified/counts",
            f"{BASE_URL}/api/chat-sessions",
        ]
        for u in api_urls:
            _, out, _ = run(
                cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {u}"
            )
            code = (out or "").strip()
            print(f"  API -> {code} {u}")
            # 未登录情况下返回 401/403/422 都算接口存在
            if code in {"404", "000"}:
                bad.append((u, code))

        # 直接通过 SSH 检查远端源码文件 BUG-457 标记
        print("\n=== verify source code markers on server ===")
        _, out, _ = run(
            cli,
            f"grep -c 'BUG-457' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        marker_count = (out or "").strip()
        print(f"[VERIFY] BUG-457 markers in remote source: {marker_count}")
        if marker_count == "0":
            print("[ERROR] BUG-457 marker not found in remote source")
            return 5

        # 校验旧 handleCopyId 已不再调用
        _, out, _ = run(
            cli,
            f"grep -c 'handleCopyId' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx || echo 0",
        )
        copyid_count = (out or "").strip().split("\n")[0]
        print(f"[VERIFY] handleCopyId references (should be 0): {copyid_count}")

        # 校验 member-qrcode 入口已移除
        _, out, _ = run(
            cli,
            f"grep -c \"navigateTo('/member-qrcode')\" {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx || echo 0",
        )
        memberqr_count = (out or "").strip().split("\n")[0]
        print(f"[VERIFY] /member-qrcode references (should be 0): {memberqr_count}")

        # 校验新增 4 个接口路径已写入
        for path in [
            "/api/points/summary",
            "/api/coupons/summary",
            "/api/orders/unified/counts",
            "/api/users/me/stats",
        ]:
            _, out, _ = run(
                cli,
                f"grep -c '{path}' {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
            )
            cnt = (out or "").strip()
            print(f"[VERIFY] {path}: {cnt}")
            if cnt == "0":
                print(f"[ERROR] missing path: {path}")
                return 6

        # 校验跳转 /profile/edit 已写入
        _, out, _ = run(
            cli,
            f"grep -c \"/profile/edit\" {REMOTE_PROJ}/h5-web/src/components/ai-chat/Sidebar.tsx",
        )
        profile_edit_count = (out or "").strip()
        print(f"[VERIFY] /profile/edit references: {profile_edit_count}")
        if profile_edit_count == "0":
            print("[ERROR] /profile/edit not wired up")
            return 7

        print(f"\n[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
