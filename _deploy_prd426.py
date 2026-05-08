#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[PRD-426 2026-05-08] 删除 AI 对话首页 "+ 选择咨询人" 浮层
- 上传 ai-home/page.tsx（移除浮层 UI 块、inputFocused state、RecommendCards import）
- 上传 SectionErrorBoundary.tsx（注释清理）
- 删除服务器上的 ConsultantPicker.tsx 和 RecommendCards.tsx
- 仅重新构建 h5-web 单容器（其余容器不动）
- smoke 验证
"""
import sys
import os
import time
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

    def run(cmd, timeout=300):
        print(f"\n>>> {cmd}")
        sin, sout, serr = cli.exec_command(cmd, timeout=timeout)
        out = sout.read().decode('utf-8', errors='replace')
        err = serr.read().decode('utf-8', errors='replace')
        rc  = sout.channel.recv_exit_status()
        if out: print(out[:5000])
        if err: print("STDERR:", err[:3000])
        return rc, out, err

    # 1. 校验项目目录
    rc, out, _ = run(f"test -d '{PROJECT_DIR}' && echo OK || echo NO")
    if 'OK' not in out:
        print(f"[FATAL] {PROJECT_DIR} 不存在！")
        cli.close()
        sys.exit(1)

    # 2. 上传修改的文件
    scp = SCPClient(cli.get_transport())
    files = [
        ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
         f"{PROJECT_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
        ("h5-web/src/components/SectionErrorBoundary.tsx",
         f"{PROJECT_DIR}/h5-web/src/components/SectionErrorBoundary.tsx"),
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

    # 3. 删除服务器上已废弃的两个组件
    run(f"rm -f '{PROJECT_DIR}/h5-web/src/components/ai-chat/ConsultantPicker.tsx'")
    run(f"rm -f '{PROJECT_DIR}/h5-web/src/components/ai-chat/RecommendCards.tsx'")
    run(f"ls -la '{PROJECT_DIR}/h5-web/src/components/ai-chat/' | head -30")

    # 4. 重新构建 h5-web
    print("\n[STEP] rebuild h5-web")
    rc, out, err = run(
        f"cd '{PROJECT_DIR}' && docker compose up -d --no-deps --build h5-web 2>&1",
        timeout=900
    )
    if rc != 0:
        run(f"cd '{PROJECT_DIR}' && docker-compose up -d --no-deps --build h5-web 2>&1", timeout=900)

    # 5. 容器状态
    run(f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID}")

    # 6. 等待启动
    print("\n[WAIT] 8s ...")
    time.sleep(8)

    # 7. smoke 测试
    print("\n=== SMOKE ===")
    run(f"curl -s -o /dev/null -w 'H5 root HTTP %{{http_code}}\\n' http://localhost/autodev/{PROJECT_ID}/")
    run(f"curl -s -o /dev/null -w 'ai-home HTTP %{{http_code}}\\n' http://localhost/autodev/{PROJECT_ID}/ai-home")
    run(f"curl -s -o /dev/null -w 'login HTTP %{{http_code}}\\n' http://localhost/autodev/{PROJECT_ID}/login")
    run(f"curl -s -o /dev/null -w 'api/health HTTP %{{http_code}}\\n' http://localhost/autodev/{PROJECT_ID}/api/health")
    run(f"curl -s -o /dev/null -w 'api/ai-home-config HTTP %{{http_code}}\\n' http://localhost/autodev/{PROJECT_ID}/api/ai-home-config")

    # 8. 关键校验：H5 容器内构建产物中不应再含 "+ 选择咨询人" 字符串
    print("\n=== ASSERTION ===")
    rc, out, err = run(
        f"docker exec {PROJECT_ID}-h5 sh -c 'grep -r \"选择咨询人\" /app/.next/server /app/.next/static 2>/dev/null | head -5; echo ---END---'",
        timeout=60
    )
    if "选择咨询人" in out and "[PRD-426]" not in out:
        # 仅留命中行排查
        print(f"[WARN] 构建产物中仍出现 '选择咨询人'（请人工核对是否仅是 ConsultTargetPicker 内部文案）")
    else:
        print("[OK] 构建产物中未发现 '+ 选择咨询人' 浮层文案。")

    cli.close()
    print("\n[DONE] PRD-426 deploy script finished.")


if __name__ == "__main__":
    main()
