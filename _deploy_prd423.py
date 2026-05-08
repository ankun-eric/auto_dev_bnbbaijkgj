#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[PRD-423 2026-05-08] 部署脚本：把本次改动同步到服务器并重新构建 backend + h5-web
"""
import sys
import os
import io
sys.stdout.reconfigure(encoding='utf-8')

import paramiko
from scp import SCPClient

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD  = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"

def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)

    def run(cmd, timeout=300):
        print(f"\n>>> {cmd}")
        sin, sout, serr = cli.exec_command(cmd, timeout=timeout)
        out = sout.read().decode('utf-8', errors='replace')
        err = serr.read().decode('utf-8', errors='replace')
        rc  = sout.channel.recv_exit_status()
        if out: print(out[:5000])
        if err: print("STDERR:", err[:3000])
        return rc, out, err

    # 1. 找出项目目录
    rc, out, _ = run(f"find /home /opt /srv -maxdepth 5 -type d -name '*{PROJECT_ID}*' 2>/dev/null | head -5")
    print("Found dirs:")
    print(out)
    candidates = [l.strip() for l in out.splitlines() if l.strip()]
    if not candidates:
        # 尝试用 docker inspect
        rc, out, _ = run(f"docker inspect {PROJECT_ID}-backend --format='{{{{.HostConfig.Binds}}}}' 2>/dev/null || true")
        print("docker inspect bind:")
        print(out)
        rc, out, _ = run(f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID} || true")
        print(out)
        rc, out, _ = run(f"sudo find / -maxdepth 6 -type d -name '*{PROJECT_ID}*' 2>/dev/null | head -5")
        print(out)
        candidates = [l.strip() for l in out.splitlines() if l.strip()]

    if not candidates:
        print("CANNOT find project dir on server.")
        cli.close()
        sys.exit(1)

    project_dir = candidates[0]
    print(f"\n[INFO] project_dir = {project_dir}")

    # 2. 上传新增/修改的文件
    scp = SCPClient(cli.get_transport())
    files = [
        # 后端
        ("backend/app/api/analytics.py",                              f"{project_dir}/backend/app/api/analytics.py"),
        ("backend/app/main.py",                                       f"{project_dir}/backend/app/main.py"),
        # 前端
        ("h5-web/src/lib/analytics.ts",                               f"{project_dir}/h5-web/src/lib/analytics.ts"),
        ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",                 f"{project_dir}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
        ("h5-web/src/app/chat/[sessionId]/page.tsx",                  f"{project_dir}/h5-web/src/app/chat/[sessionId]/page.tsx"),
    ]
    for local_rel, remote_path in files:
        local = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
        if not os.path.exists(local):
            print(f"[SKIP] local not found: {local}")
            continue
        print(f"\n[UPLOAD] {local} -> {remote_path}")
        # 确保父目录存在
        parent = os.path.dirname(remote_path)
        run(f"mkdir -p '{parent}'")
        scp.put(local, remote_path)
    scp.close()

    # 3. 重新构建后端 + h5（不启动整个 stack，只重启对应的两个容器）
    print("\n[STEP] rebuild backend & h5-web")
    rc, out, err = run(
        f"cd '{project_dir}' && docker compose up -d --no-deps --build backend h5-web 2>&1",
        timeout=900
    )
    if rc != 0:
        # 尝试旧 docker-compose 命令
        run(f"cd '{project_dir}' && docker-compose up -d --no-deps --build backend h5-web 2>&1", timeout=900)

    # 4. 检查容器状态
    run(f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID}")

    # 5. 等待几秒后健康检查
    import time
    print("\n[WAIT] 12s for services to start ...")
    time.sleep(12)
    run(f"docker logs --tail 50 {PROJECT_ID}-backend 2>&1 | tail -30")

    # 6. 验证 analytics 接口
    run(
        f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' "
        f"-X POST http://localhost/autodev/{PROJECT_ID}/api/analytics/track "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"event\":\"ai_chat_page_view\",\"params\":{{\"default_target\":\"self\"}},\"ts\":1700000000000}}'"
    )

    # 7. 验证 H5 首页
    run(f"curl -s -o /dev/null -w 'H5 home HTTP %{{http_code}}\\n' http://localhost/autodev/{PROJECT_ID}/")

    cli.close()
    print("\n[DONE] deploy script finished.")

if __name__ == "__main__":
    main()
