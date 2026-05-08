"""[PRD-429 2026-05-08] AI 回答消息满屏排版改造 部署脚本（H5 端）。

改造要点：
- AI 对话首页（/ai-home）和会话详情页（/chat/[sessionId]）的消息列表
  从"用户右气泡 + AI 左气泡"改为"无气泡纯文本流"
- 用户消息和 AI 回答均去除 background/border/borderRadius/boxShadow
- 头像独占一行放在文字上方，文字铺满整行（左右各 12px 安全边距）
- 超宽屏（PC/平板）下 max-width 760px 居中
- 代码块、表格、图片在满屏排版下保留合适样式
- 卡片类组件（健康自查摘要卡、药品识别卡）保留 360px 最大宽度

涉及文件：
- h5-web/src/app/(ai-chat)/ai-home/page.tsx
- h5-web/src/app/chat/[sessionId]/page.tsx

流程：
1. paramiko SFTP 上传 H5 改动文件
2. SSH docker compose build h5-web && up -d h5-web
3. 远程 smoke 验证 / + /ai-home + /api/ai-home-config + /api/health
4. 抓取 SSR HTML 验证新 data-testid 标记（ai-home-message-flow 等）
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
    ("h5-web/src/app/chat/[sessionId]/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/chat/[sessionId]/page.tsx"),
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 1200) -> tuple[int, str, str]:
    print(f"\n>>> {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-4000:])
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

    # 4. 验证 SSR HTML 中包含新满屏排版的关键 DOM 标记
    print("\n[Verify - check ai-home page contains new fullwidth message flow markers]")
    run(
        ssh,
        f"curl -s '{BASE_URL}/ai-home' | grep -o "
        f"-E 'ai-home-message-flow|ai-home-user-message|ai-home-ai-message|ai-fullwidth-message' | sort -u",
        timeout=30,
    )

    sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
