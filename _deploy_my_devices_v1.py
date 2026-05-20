"""[PRD-MY-DEVICES-V1 2026-05-21] 「我的设备」V2 部署脚本。

将本次新增/修改的文件上传到部署服务器，触发 backend + h5-web 重建，
并执行后端 pytest + HTTP 烟雾测试。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"


FILES_TO_UPLOAD: list[tuple[str, str]] = [
    # backend
    ("backend/app/api/devices_v2.py", f"{DEPLOY_DIR}/backend/app/api/devices_v2.py"),
    ("backend/app/models/devices_v2.py", f"{DEPLOY_DIR}/backend/app/models/devices_v2.py"),
    ("backend/app/main.py", f"{DEPLOY_DIR}/backend/app/main.py"),
    (
        "backend/tests/test_my_devices_v1_20260521.py",
        f"{DEPLOY_DIR}/backend/tests/test_my_devices_v1_20260521.py",
    ),
    # h5-web sidebar 修复
    (
        "h5-web/src/components/ai-chat/Sidebar.tsx",
        f"{DEPLOY_DIR}/h5-web/src/components/ai-chat/Sidebar.tsx",
    ),
    # h5-web 我的设备页面
    ("h5-web/src/app/devices/page.tsx", f"{DEPLOY_DIR}/h5-web/src/app/devices/page.tsx"),
    (
        "h5-web/src/app/devices/components/theme.ts",
        f"{DEPLOY_DIR}/h5-web/src/app/devices/components/theme.ts",
    ),
    (
        "h5-web/src/app/devices/components/MyDeviceCard.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/devices/components/MyDeviceCard.tsx",
    ),
    (
        "h5-web/src/app/devices/components/BrandSection.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/devices/components/BrandSection.tsx",
    ),
    (
        "h5-web/src/app/devices/components/BindDeviceDrawer.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/devices/components/BindDeviceDrawer.tsx",
    ),
    (
        "h5-web/src/app/devices/components/EditDeviceDrawer.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/devices/components/EditDeviceDrawer.tsx",
    ),
    (
        "h5-web/src/app/devices/components/UnbindConfirmModal.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/devices/components/UnbindConfirmModal.tsx",
    ),
    (
        "h5-web/src/app/devices/components/ScanQRButton.tsx",
        f"{DEPLOY_DIR}/h5-web/src/app/devices/components/ScanQRButton.tsx",
    ),
    ("h5-web/src/lib/api/devices.ts", f"{DEPLOY_DIR}/h5-web/src/lib/api/devices.ts"),
]


def make_ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30, banner_timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 1800) -> tuple[int, str]:
    print(f"$ {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    rc = stdout.channel.recv_exit_status()
    combined = (out + err).rstrip()
    if combined:
        print(combined[-4000:])
    return rc, combined


def upload(cli: paramiko.SSHClient, local: str, remote: str) -> None:
    p = Path(local)
    if not p.exists():
        print(f"  ⚠️ 本地文件不存在，跳过：{local}")
        return
    parent = remote.rsplit("/", 1)[0]
    run(cli, f"mkdir -p '{parent}'", timeout=60)
    sftp = cli.open_sftp()
    try:
        sftp.put(str(p), remote)
        print(f"  ✅ uploaded {local} -> {remote}")
    finally:
        sftp.close()


def main() -> int:
    print("=" * 60)
    print("[PRD-MY-DEVICES-V1] 部署开始")
    print(f"  Host:       {HOST}")
    print(f"  DeployDir:  {DEPLOY_DIR}")
    print(f"  BaseURL:    {BASE_URL}")
    print("=" * 60)

    cli = make_ssh()
    try:
        # 1) 上传文件
        print("\n--- 步骤 1：上传变更文件 ---")
        for local, remote in FILES_TO_UPLOAD:
            upload(cli, local, remote)

        # 2) build & up
        print("\n--- 步骤 2：docker compose build & up backend + h5-web ---")
        rc, _ = run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose build backend h5-web 2>&1 | tail -150",
            timeout=2400,
        )
        if rc != 0:
            print("⚠️ docker compose build 返回非 0，仍将尝试 up")
        run(
            cli,
            f"cd {DEPLOY_DIR} && docker compose up -d backend h5-web 2>&1 | tail -30",
            timeout=600,
        )

        # 3) 等待后端启动 + 检查迁移日志
        print("\n--- 步骤 3：等待 30s 后检查迁移日志 ---")
        time.sleep(30)
        run(
            cli,
            f"docker logs --tail 400 {PROJECT_ID}-backend 2>&1 | "
            "grep -E 'my_devices_v1|devices_v2|device_catalog' || true",
            timeout=60,
        )

        # 4) HTTP 探活
        print("\n--- 步骤 4：HTTP 探活 ---")
        for path in [
            "/api/health",
            "/",
            "/devices/",
            "/api/devices/catalog",  # 401 期望（未带 token），但响应应该到达 backend
        ]:
            run(
                cli,
                f"curl -sk -o /dev/null -w '{path} HTTP_%{{http_code}}\\n' '{BASE_URL}{path}'",
                timeout=60,
            )

        # 5) 远端 pytest
        print("\n--- 步骤 5：远端 pytest（test_my_devices_v1_20260521.py） ---")
        run(
            cli,
            f"docker exec {PROJECT_ID}-backend python -m pytest "
            f"tests/test_my_devices_v1_20260521.py -v --no-header 2>&1 | tail -120",
            timeout=300,
        )

        print("\n" + "=" * 60)
        print("[PRD-MY-DEVICES-V1] 部署完成")
        print("=" * 60)
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
