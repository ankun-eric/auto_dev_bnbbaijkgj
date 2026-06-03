"""[2026-04-25] AI 报告解读 4 Bugs - 远程部署 v2

策略：先尝试 git fetch（带重试），失败�?SFTP 上传 5 个本次改动文件兜底，
然后重建 backend + h5-web 容器，验�?gateway 路由�?
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
NETWORK = f"{DEPLOY_ID}-network"
GATEWAY = "gateway"
COMPOSE_FILE = "docker-compose.prod.yml"
GIT_URL_TOKEN = (
    "https://ankun-eric:" + os.environ.get("GH_TOKEN", "REDACTED") +
    "@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
)
EXPECTED_COMMIT = "66bc7d9"
LOCAL_ROOT = Path(__file__).resolve().parent.parent

# 本次 bug 修复涉及的文件（�?.dev_start_commit.txt 等无关物外）
FILES_TO_UPLOAD = [
    "backend/app/api/chat.py",
    "backend/app/api/report_interpret.py",
    "h5-web/src/lib/image-compress.ts",
    "h5-web/src/app/checkup/page.tsx",
    "h5-web/src/app/chat/[sessionId]/page.tsx",
]


def ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    transport = c.get_transport()
    if transport is not None:
        transport.set_keepalive(30)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    print(f"\n$ {cmd}", flush=True)
    _stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-5000:], flush=True)
    if err.strip():
        print("stderr:", err[-2500:], flush=True)
    print(f"exit={code}", flush=True)
    return code, out, err


def try_git_pull(c: paramiko.SSHClient) -> bool:
    """尝试 git pull 最�?3 次。返�?True 表示成功拉到 EXPECTED_COMMIT�?""
    run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL_TOKEN}", timeout=15)
    run(c, "git config --global http.lowSpeedLimit 1000 && git config --global http.lowSpeedTime 60", timeout=10)
    for attempt in range(1, 4):
        print(f"\n--- git fetch attempt {attempt}/3 ---", flush=True)
        # 每次�?5 分钟
        run(
            c,
            f"cd {PROJECT_DIR} && GIT_TERMINAL_PROMPT=0 timeout 300 "
            f"git fetch --depth=50 origin master",
            timeout=360,
        )
        # 检查远�?commit 是否包含期望
        code, out, _ = run(
            c,
            f"cd {PROJECT_DIR} && git log -1 origin/master --oneline 2>&1 || true",
            timeout=10,
        )
        if EXPECTED_COMMIT in out:
            print(f"  �?origin/master 已包�?{EXPECTED_COMMIT}", flush=True)
            run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=30)
            run(c, f"cd {PROJECT_DIR} && git clean -fd", timeout=20)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)
            return True
        time.sleep(5)
    return False


def sftp_upload_fix_files(c: paramiko.SSHClient) -> int:
    """SFTP 上传 5 个本次修改的源码文件作为降级方案�?""
    print("\n=== 降级：SFTP 直接上传修改文件 ===", flush=True)
    sftp = c.open_sftp()
    ok = 0
    try:
        for rel in FILES_TO_UPLOAD:
            local = LOCAL_ROOT / rel
            if not local.exists():
                print(f"[skip] 本地不存�? {local}", flush=True)
                continue
            remote = f"{PROJECT_DIR}/{rel}"
            remote_dir = remote.rsplit("/", 1)[0]
            run(c, f"mkdir -p {remote_dir}", timeout=10)
            sftp.put(str(local), remote)
            print(f"[ok] uploaded {rel}", flush=True)
            ok += 1
    finally:
        sftp.close()
    return ok


def main() -> int:
    print(f"== SSH 连接 {USER}@{HOST}:{PORT} ==", flush=True)
    c = ssh()
    try:
        run(c, f"ls -la {PROJECT_DIR} | head -3", timeout=10)

        pulled = try_git_pull(c)
        if not pulled:
            print(
                f"\n!! git pull 未能在远端获取到目标 commit {EXPECTED_COMMIT}, "
                f"降级�?SFTP 直传 ({len(FILES_TO_UPLOAD)} 个文�?",
                flush=True,
            )
            sftp_upload_fix_files(c)
            run(c, f"cd {PROJECT_DIR} && git status -s | head -20", timeout=10)
            run(c, f"cd {PROJECT_DIR} && git log -1 --oneline", timeout=10)
        else:
            print(f"\n�?git pull 成功，已切换�?{EXPECTED_COMMIT}", flush=True)

        # 重建 backend
        print("\n== 重建 backend ==", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache backend 2>&1 | tail -40",
            timeout=900,
        )

        # 重建 h5-web
        print("\n== 重建 h5-web ==", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} build --no-cache h5-web 2>&1 | tail -40",
            timeout=1500,
        )

        # 启动
        print("\n== 启动 backend + h5-web ==", flush=True)
        run(
            c,
            f"cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d backend h5-web 2>&1 | tail -30",
            timeout=180,
        )

        # 等容�?
        print("\n== 等待容器 healthy ==", flush=True)
        for i in range(20):
            time.sleep(5)
            code, out, _ = run(
                c,
                f"docker ps --format '{{{{.Names}}}}|{{{{.Status}}}}' | grep {DEPLOY_ID}",
                timeout=10,
            )
            lines = [ln for ln in out.splitlines() if ln.strip()]
            bad = [ln for ln in lines if "starting" in ln.lower() or "unhealthy" in ln.lower()]
            print(f"  [{i+1}/20] count={len(lines)} bad={len(bad)}", flush=True)
            if lines and not bad and any("backend" in ln for ln in lines) and any("h5" in ln for ln in lines):
                # 至少 30 �?
                if i >= 5:
                    break

        # 网络�?gateway reload
        print("\n== gateway 加入项目网络 + reload ==", flush=True)
        run(c, f"docker ps --format '{{{{.Names}}}}' | grep -i gateway", timeout=10)
        run(c, f"docker network connect {NETWORK} {GATEWAY} 2>&1 || true", timeout=15)
        run(c, f"docker network inspect {NETWORK} --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'", timeout=10)
        run(c, f"docker exec {GATEWAY} nginx -t 2>&1", timeout=15)
        run(c, f"docker exec {GATEWAY} nginx -s reload 2>&1", timeout=15)

        # 内部探测
        print("\n== 服务器内�?curl 自检 ==", flush=True)
        for path, name in [
            ("/", "h5_root"),
            ("/checkup", "checkup"),
            ("/login", "login"),
            ("/chat/test-id?type=report_interpret", "chat_session"),
            ("/api/health", "api_health"),
            ("/api/auth/captcha", "api_captcha"),
        ]:
            run(
                c,
                f"curl -sk -o /dev/null -w '{name}=%{{http_code}}\\n' "
                f"https://localhost/autodev/{DEPLOY_ID}{path}",
                timeout=15,
            )

        print("\n== 完成 ==", flush=True)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
