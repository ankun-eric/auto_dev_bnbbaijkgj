#!/usr/bin/env python3
"""[BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29]
将本次「居家安全设备页 + 添加家人按钮白屏 gateway ok」修复部署到测试环境。

策略：
1. 仅上传本次改动到的文件（前端 + 后端 + 测试），不动其他容器
2. 远程通过 docker compose 重新 build h5-web、backend 并重启对应服务
3. 远程跑后端 pytest 验证 frontend_log 接口可用
4. 用 curl 验证 H5 居家安全设备页可达（不再返回 gateway ok）
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))


CHANGED_FILES = [
    # H5 前端：核心修复
    "h5-web/src/components/family/FamilyMemberTabs.tsx",
    "h5-web/src/lib/api.ts",
    # 后端：前端日志接口
    "backend/app/api/frontend_log.py",
    "backend/app/main.py",
    # 测试
    "backend/tests/test_frontend_log_gateway_fallback.py",
]


def _connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    return cli


def run(cmd: str, timeout: int = 1200) -> tuple[int, str, str]:
    cli = _connect()
    try:
        stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err
    finally:
        cli.close()


def sftp_upload(files: list[str]) -> None:
    cli = _connect()
    try:
        sftp = cli.open_sftp()
        for rel in files:
            local = os.path.join(LOCAL_DIR, rel.replace("/", os.sep))
            remote = f"{REMOTE_DIR}/{rel}"
            # 确保远端目录存在
            parent = os.path.dirname(remote)
            mk = f"mkdir -p {parent}"
            cli.exec_command(mk)[1].channel.recv_exit_status()
            print(f"  uploading {rel} ...", flush=True)
            sftp.put(local, remote)
        sftp.close()
    finally:
        cli.close()


def banner(s: str) -> None:
    print(f"\n============ {s} ============", flush=True)


def main() -> int:
    banner("Step 1/5: upload changed files to remote")
    sftp_upload(CHANGED_FILES)

    banner("Step 2/5: rebuild backend + h5-web containers")
    cmd = (
        f"cd {REMOTE_DIR} && "
        f"docker compose -f docker-compose.prod.yml build backend h5-web 2>&1 | tail -40 && "
        f"docker compose -f docker-compose.prod.yml up -d backend h5-web 2>&1 | tail -20"
    )
    rc, out, err = run(cmd, timeout=1500)
    print(out)
    if err:
        print("STDERR:", err)
    if rc != 0:
        print(f"!! rebuild failed (rc={rc})")
        return 1

    banner("Step 3/5: wait for containers to be ready")
    for i in range(24):
        rc, out, _ = run(
            f"docker ps --filter name={DEPLOY_ID}-backend --filter name={DEPLOY_ID}-h5 "
            f"--format '{{{{.Names}}}}\t{{{{.Status}}}}'"
        )
        print(out.strip())
        if "Up" in out and out.count("Up") >= 2:
            time.sleep(5)
            break
        time.sleep(5)

    banner("Step 4/5: run backend pytest (frontend_log)")
    cmd = (
        f"docker exec {DEPLOY_ID}-backend "
        f"sh -lc 'cd /app && pip install -q pytest pytest-asyncio httpx 2>/dev/null; "
        f"python -m pytest tests/test_frontend_log_gateway_fallback.py -v 2>&1 | tail -60'"
    )
    rc, out, err = run(cmd, timeout=600)
    print(out)
    if err:
        print("STDERR:", err)

    banner("Step 5/5: external curl smoke tests")
    base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    # 检查 h5 入口、家庭成员接口、前端日志接口
    for path, note in [
        ("/", "h5 root"),
        ("/home-safety/", "home-safety page"),
        ("/api/_frontend_log", "frontend_log endpoint (GET should be 405)"),
    ]:
        cmd = f"curl -ksS -o /dev/null -w 'HTTP %{{http_code}} ct=%{{content_type}}\\n' {base}{path}"
        rc, out, _ = run(cmd, timeout=60)
        print(f"  {note}: {out.strip()}")

    # 直接 POST 测一下 frontend_log
    cmd = (
        f"curl -ksS -o /dev/null -w 'POST _frontend_log HTTP %{{http_code}}\\n' "
        f"-X POST -H 'Content-Type: application/json' "
        f"-d '{{\"type\":\"gateway_fallback\",\"url\":\"/api/x\",\"body_excerpt\":\"gateway ok\"}}' "
        f"{base}/api/_frontend_log"
    )
    rc, out, _ = run(cmd, timeout=60)
    print(f"  {out.strip()}")

    print("\nDONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
