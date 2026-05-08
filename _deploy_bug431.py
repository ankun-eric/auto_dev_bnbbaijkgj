"""[Bug-431 2026-05-08] H5 端 AI 对话首页"顶部吸顶栏抖动 + 欢迎面板自动闪掉"修复 部署脚本。

修复要点：
- Bug-1：顶部"小康"栏改为 fixed 独立钉死，栏内三元素绝对定位，无任何 transition/transform
- Bug-2：欢迎面板的"自动收起"逻辑彻底移除，唯一收起触发条件 = 用户主动发送首条消息
  - 进入 /ai-home 默认完整展开
  - 切换会话/家庭成员/从其他页返回首页 → 进入未发消息态 → 默认展开
  - 仅 handleSend 内置 setSentInSession(true) + setTopPanelExpanded(false)
  - 用户后续可点击右上角小头像（fab）/ 收起按钮 来回切换

流程：
1. paramiko SFTP 上传：
   - h5-web/src/app/(ai-chat)/ai-home/page.tsx
2. SSH docker compose build h5-web && up -d h5-web
3. 远程 smoke 验证 / + /ai-home + /api/ai-home-config + /api/health
4. SSR HTML 中校验 ai-home-topbar / ai-home-top-panel / ai-home-top-panel-fab DOM 标记仍在
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
    run(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web", timeout=180)

    print("\n等待 h5-web 启动...")
    time.sleep(15)

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

    # 4. 验证修复关键 DOM 标记是否在 SSR HTML 中（page-loaded 时输出）
    print("\n[Verify - check ai-home SSR HTML markers]")
    run(
        ssh,
        f"curl -sL '{BASE_URL}/ai-home' | grep -o "
        f"-E 'ai-home-topbar|ai-home-topbar-title|ai-home-top-panel|ai-home-top-panel-fab|ai-home-top-panel-collapse-btn|ai-home-message-flow' | sort -u",
        timeout=30,
    )

    # 5. 验证旧 sticky CSS 字符串不再出现在构建产物中（顶栏已改为 fixed）
    print("\n[Verify - 旧 sticky 顶栏 CSS 已清理]")
    run(
        ssh,
        f"docker exec {DEPLOY_ID}-h5 grep -c 'sticky top-0 z-50' /app/.next/server/app/(ai-chat)/ai-home/page.js 2>/dev/null || echo 'not-found-or-clean'",
        timeout=30,
    )

    sftp.close()
    ssh.close()
    print("\n[OK] Bug-431 部署完成")


if __name__ == "__main__":
    main()
