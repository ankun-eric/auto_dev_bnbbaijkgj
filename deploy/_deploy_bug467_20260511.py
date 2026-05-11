"""[PRD-467 (2026-05-11)] 部署脚本 — AI 对话首页 ⋯ 菜单修复（H5 前端 Bug 修复）

修复范围（仅 H5 前端，无后端改动）：
  - h5-web/src/components/ai-chat/MoreMenu.tsx：
      a) ⋯菜单卡片底色 #FFFFFF → #F0F9FF（THEME.background）
      b) 分隔线 #E5E7EB → #BAE6FD（主题浅蓝色阶）
      c) 加 data-testid 便于自动化测试
  - h5-web/src/app/(ai-chat)/ai-home/page.tsx：
      a) 给 ⋯ 按钮加 data-testid="ai-home-more-btn"
      b) 引入 FontSizeLevel / FONT_SIZE_MAP / FONT_LABEL_MAP / FONT_TOAST_MAP
      c) 引入 fontPopoverOpen / fontSizeLevel state + 各 handle 函数
      d) MoreMenu 挂接 onScan / onFontSize（修复点击无响应 Bug）
      e) 在 ⋯ 按钮正下方渲染字号 popover（160×40，3 档 + 朝上小三角）
      f) 字号变化作用于消息流用户气泡 + AI 回答正文（fontSize: chatFontSize）

部署流程：
  1. SFTP 上传 2 个前端文件
  2. docker compose build h5-web（前端镜像构建）
  3. docker compose up -d h5-web（重启容器）
  4. 等容器健康，curl 验证 /ai-home 可达 + 关键源码标记
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
        "h5-web/src/components/ai-chat/MoreMenu.tsx",
        f"{REMOTE_PROJ}/h5-web/src/components/ai-chat/MoreMenu.tsx",
    ),
    (
        "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
        f"{REMOTE_PROJ}/h5-web/src/app/(ai-chat)/ai-home/page.tsx",
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
        run(cli, f"test -d {REMOTE_PROJ} && echo OK || echo MISSING")
        upload_files(cli)

        # ─── 源码标记校验 ───
        # MoreMenu.tsx：PRD-467 + onFontSize + #BAE6FD（视觉色）
        _, out, _ = run(
            cli,
            f"grep -c 'PRD-467' {REMOTE_PROJ}/h5-web/src/components/ai-chat/MoreMenu.tsx",
        )
        print(f"[VERIFY] MoreMenu PRD-467 markers: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'onFontSize' {REMOTE_PROJ}/h5-web/src/components/ai-chat/MoreMenu.tsx",
        )
        print(f"[VERIFY] MoreMenu onFontSize occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c '#BAE6FD' {REMOTE_PROJ}/h5-web/src/components/ai-chat/MoreMenu.tsx",
        )
        print(f"[VERIFY] MoreMenu primaryLight #BAE6FD: {(out or '').strip()}")

        # ai-home/page.tsx：PRD-467 标记 + 关键标识
        _, out, _ = run(
            cli,
            f"grep -c 'PRD-467' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] ai-home PRD-467 markers: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'fontPopoverOpen' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] ai-home fontPopoverOpen occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'handleScan' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] ai-home handleScan occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'handleFontSize' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] ai-home handleFontSize occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'handleFontChange' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] ai-home handleFontChange occurrences: {(out or '').strip()}")
        _, out, _ = run(
            cli,
            f"grep -c 'ai-home-font-popover' {REMOTE_PROJ}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        )
        print(f"[VERIFY] ai-home font-popover testid: {(out or '').strip()}")

        # ─── 构建并启动容器（仅 h5-web） ───
        run(cli, f"cd {REMOTE_PROJ} && docker compose build h5-web", timeout=3600)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d h5-web", timeout=600)

        time.sleep(15)

        # 等待 h5 容器健康
        for _ in range(36):
            _, out_h, _ = run(
                cli,
                f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-h5 2>/dev/null || echo NONE",
            )
            if (out_h or "").strip() == "running":
                break
            time.sleep(5)

        # ─── smoke：关键路由可达性 ───
        bad: list[tuple[str, str, str]] = []
        # T1: 前端 ai-home 页面应可达（200/302/3xx）
        _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/ai-home")
        code = (out or "").strip()
        print(f"[SMOKE T1] /ai-home -> {code}")
        if not (code.startswith("2") or code.startswith("3")):
            bad.append(("/ai-home", code, "FE_UNREACHABLE"))

        # T2: 前端 /scan 扫一扫页应可达
        _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/scan")
        code = (out or "").strip()
        print(f"[SMOKE T2] /scan -> {code}")
        if not (code.startswith("2") or code.startswith("3")):
            bad.append(("/scan", code, "SCAN_PAGE_UNREACHABLE"))

        # T3: 字号设置接口未登录应 401（证明后端未受影响、接口仍可用）
        _, out, _ = run(
            cli,
            f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/api/user/font-setting",
        )
        code = (out or "").strip()
        print(f"[SMOKE T3] GET /api/user/font-setting (no auth) -> {code}")
        if code == "500":
            bad.append(("/api/user/font-setting", code, "BACKEND_500"))
        elif code not in {"401", "403"}:
            bad.append(("/api/user/font-setting", code, "UNEXPECTED"))

        # T4: 前端登录页应可达（未登录字号点击会跳转此页）
        _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/login")
        code = (out or "").strip()
        print(f"[SMOKE T4] /login -> {code}")
        if not (code.startswith("2") or code.startswith("3")):
            bad.append(("/login", code, "LOGIN_PAGE_UNREACHABLE"))

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
