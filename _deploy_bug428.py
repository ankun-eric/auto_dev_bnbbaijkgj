"""[Bug-428 2026-05-08] H5 端 AI 对话首页"瀑布流回看"消失 修复 部署脚本。

修复要点：
- 顶部欢迎区/三大功能卡片/推荐胶囊 改为"始终挂载 + 通过 isExpanded 状态控制展开/收起"
- 收缩态显示右上角 AI 头像悬浮按钮，点击展开
- 展开态右上角"⌃ 收起"按钮 + 上滑/输入框聚焦/外部点击 自动收起
- 进入页面已有历史 → 自动滚到底部最新消息
- 不接入后台开关，硬编码常驻

流程：
1. paramiko SFTP 上传：
   - h5-web/src/app/(ai-chat)/ai-home/page.tsx
2. SSH docker compose build h5-web && up -d h5-web
3. 远程 smoke 验证 / + /ai-home + /api/ai-home-config
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
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 1200) -> tuple[int, str, str]:
    print(f"\n>>> {cmd[:200]}")
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
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -80",
        timeout=1800,
    )
    run(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web", timeout=180)

    print("\n等待 h5-web 启动...")
    time.sleep(12)

    # 3. smoke
    smoke_urls = [
        "/api/health",
        "/api/ai-home-config",
        "/",
        "/ai-home",
    ]
    print("\n[Smoke]")
    for u in smoke_urls:
        run(ssh, f"curl -s -o /dev/null -w '{u}=%{{http_code}}\\n' '{BASE_URL}{u}'")

    # 4. 验证修复关键 DOM 标记是否在 SSR HTML 中（页面源码）
    print("\n[Verify - check ai-home page contains new top-panel markers]")
    run(
        ssh,
        f"curl -s '{BASE_URL}/ai-home' | grep -o "
        f"-E 'ai-home-top-panel|ai-home-top-panel-fab|ai-home-top-panel-collapse-btn' | sort -u",
        timeout=30,
    )

    sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
