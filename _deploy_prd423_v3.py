#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[PRD-423 v3] 部署到正确目录 /home/ubuntu/{PROJECT_ID}/
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
import paramiko
from scp import SCPClient

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD  = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_ID}"
LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"

def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)

    def run(cmd, timeout=900):
        print(f"\n>>> {cmd[:300]}")
        sin, sout, serr = cli.exec_command(cmd, timeout=timeout)
        out = sout.read().decode('utf-8', errors='replace')
        err = serr.read().decode('utf-8', errors='replace')
        rc  = sout.channel.recv_exit_status()
        if out: print(out[:8000])
        if err: print("STDERR:", err[:3000])
        return rc, out, err

    scp = SCPClient(cli.get_transport())
    files = [
        # 后端
        ("backend/app/api/analytics.py",                              f"{PROJECT_DIR}/backend/app/api/analytics.py"),
        ("backend/app/main.py",                                       f"{PROJECT_DIR}/backend/app/main.py"),
        # 前端
        ("h5-web/src/lib/analytics.ts",                               f"{PROJECT_DIR}/h5-web/src/lib/analytics.ts"),
        ("h5-web/src/components/ai-chat/DraggablePunchCard.tsx",      f"{PROJECT_DIR}/h5-web/src/components/ai-chat/DraggablePunchCard.tsx"),
        ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",                 f"{PROJECT_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
        ("h5-web/src/app/chat/[sessionId]/page.tsx",                  f"{PROJECT_DIR}/h5-web/src/app/chat/[sessionId]/page.tsx"),
    ]
    for local_rel, remote_path in files:
        local = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
        if not os.path.exists(local):
            print(f"[SKIP] local not found: {local}")
            continue
        print(f"\n[UPLOAD] {local} -> {remote_path}")
        parent = os.path.dirname(remote_path)
        run(f"mkdir -p '{parent}'")
        scp.put(local, remote_path)
    scp.close()

    # 重新构建 backend + h5-web
    print("\n[STEP] rebuild backend & h5-web")
    rc, out, err = run(
        f"cd '{PROJECT_DIR}' && docker compose up -d --no-deps --build backend h5-web 2>&1",
        timeout=1200
    )
    print(f"build rc={rc}")

    # 容器状态
    run(f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID}")

    # 等待
    print("\n[WAIT] 15s ...")
    time.sleep(15)

    # 后端日志
    run(f"docker logs --tail 30 {PROJECT_ID}-backend 2>&1 | tail -30")
    # h5 日志
    run(f"docker logs --tail 30 {PROJECT_ID}-h5 2>&1 | tail -30")

    # 健康检查 (从外部访问)
    run(
        f"curl -sS -L -o /dev/null -w 'analytics POST -> %{{http_code}}\\n' "
        f"-X POST 'https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/api/analytics/track' "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"event\":\"ai_chat_page_view\",\"params\":{{\"default_target\":\"self\"}},\"ts\":1700000000000}}' --insecure"
    )
    run(
        f"curl -sS -L -o /dev/null -w 'h5 / -> %{{http_code}}\\n' "
        f"'https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/' --insecure"
    )
    run(
        f"curl -sS -L -o /dev/null -w 'h5 ai-home -> %{{http_code}}\\n' "
        f"'https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/ai-home' --insecure"
    )

    cli.close()
    print("\n[DONE]")

if __name__ == "__main__":
    main()
