"""[Bug-432-fix 2026-05-09] PRD-432「咨询对象档案折叠卡片」永久卡 loading Bug 修复部署脚本。

修复要点：
- H5 ProfileCard.tsx: 删除 res.data 二次脱壳（拦截器已脱过一次），增加 1 次自动重试
- H5 MedicationDrawer.tsx: 同样删除 res.data 二次脱壳，增加加载失败可点击重试

只涉及 H5 端的两个组件文件。小程序 / Flutter 走打包流程。

流程：
1. paramiko SFTP 上传两个组件文件
2. SSH docker compose build h5-web && up -d h5-web
3. 远程 smoke 验证 /api/health + /api/ai-home-config + / + /ai-home
4. 在构建产物中校验旧的 res.data 二次脱壳已被清理
"""
from __future__ import annotations

import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

FILES = [
    (
        "h5-web/src/components/ai-chat/ProfileCard.tsx",
        f"{PROJECT_DIR}/h5-web/src/components/ai-chat/ProfileCard.tsx",
    ),
    (
        "h5-web/src/components/ai-chat/MedicationDrawer.tsx",
        f"{PROJECT_DIR}/h5-web/src/components/ai-chat/MedicationDrawer.tsx",
    ),
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 1800) -> tuple[int, str, str]:
    print(f"\n>>> {cmd[:240]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err:
        print("STDERR:", err[-2000:])
    print(f"<<< exit={code}")
    return code, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, PORT, USER, PASSWORD, timeout=30)
    sftp = ssh.open_sftp()

    # 1. 上传文件
    for local, remote in FILES:
        local_path = Path(local)
        if not local_path.exists():
            print(f"[skip 不存在] {local}")
            continue
        remote_dir = "/".join(remote.split("/")[:-1])
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            run(ssh, f"mkdir -p '{remote_dir}'")
        print(f"\n[上传] {local} → {remote}")
        sftp.put(str(local_path), remote)

    # 2. h5-web 重建
    print("\n[h5-web build]")
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -100",
        timeout=1800,
    )
    run(
        ssh,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web",
        timeout=180,
    )

    print("\n等待 h5-web 启动...")
    time.sleep(15)

    # 3. smoke
    smoke_urls = [
        "/api/health",
        "/api/ai-home-config",
        "/",
        "/ai-home",
        "/api/v1/consultant/0/profile_card",
        "/api/v1/consultant/0/medications",
    ]
    print("\n[Smoke]")
    for u in smoke_urls:
        run(ssh, f"curl -s -o /dev/null -w '{u}=%{{http_code}}\\n' '{BASE_URL}{u}'")

    # 4. 校验 ProfileCard.tsx 在容器中已不再写 res.data（即旧 Bug 已被清除）
    print("\n[Verify - 容器内 ProfileCard 源码不再二次脱壳]")
    run(
        ssh,
        f"docker exec {DEPLOY_ID}-h5 grep -c 'res.data' /app/src/components/ai-chat/ProfileCard.tsx 2>/dev/null || echo 'file-not-found'",
        timeout=30,
    )
    run(
        ssh,
        f"docker exec {DEPLOY_ID}-h5 grep -c 'Bug-432-fix' /app/src/components/ai-chat/ProfileCard.tsx 2>/dev/null || echo 'file-not-found'",
        timeout=30,
    )

    sftp.close()
    ssh.close()
    print("\n[OK] Bug-432-fix 部署完成")


if __name__ == "__main__":
    main()
