"""[会员中心优化 PRD v2.0 2026-05-26] 部署 + 服务器测试

流程：
1. 上传修改/新增文件
2. rebuild backend + h5-web
3. 重启 backend + h5-web
4. 等待启动 + smoke 测试新接口
5. 容器内运行 pytest test_member_center_v2.py
"""
from __future__ import annotations

import os
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))


def ssh_run(client, cmd, timeout=600, silent=False):
    if not silent:
        print(f"[ssh] $ {cmd[:240]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    combined = out + ("\n[stderr]\n" + err if err.strip() else "")
    if not silent:
        tail = "\n".join(combined.splitlines()[-80:])
        print(tail)
        print(f"[ssh] exit={rc}")
    return rc, combined


def scp_put(sftp, local_path, remote_path):
    print(f"[scp] {local_path} → {remote_path}")
    sftp.put(local_path, remote_path)


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = client.open_sftp()

    try:
        print("\n[1] 上传源码文件")
        files = [
            "backend/app/api/member_center_v2.py",
            "backend/app/services/schema_sync.py",
            "backend/app/models/models.py",
            "backend/app/main.py",
            "backend/tests/test_member_center_v2.py",
            "h5-web/src/components/ai-chat/MoreMenu.tsx",
            "h5-web/src/app/member-center/page.tsx",
        ]
        for rel in files:
            local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
            if not os.path.exists(local):
                print(f"    ⚠️ 本地缺失：{local}，跳过")
                continue
            remote = f"{REMOTE_PROJECT_DIR}/{rel}"
            remote_dir = os.path.dirname(remote)
            ssh_run(client, f"mkdir -p '{remote_dir}'", timeout=10, silent=True)
            scp_put(sftp, local, remote)

        print("\n[2] Rebuild backend")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build backend 2>&1 | tail -15",
            timeout=900,
        )
        print("\n[2b] Rebuild h5-web")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build h5-web 2>&1 | tail -15",
            timeout=900,
        )

        print("\n[3] 重启容器")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose up -d backend h5-web 2>&1 | tail -10",
            timeout=180,
        )

        print("\n[4] 等待 backend 启动")
        ready = False
        for i in range(45):
            time.sleep(2)
            rc, out = ssh_run(
                client,
                f"docker logs --tail=60 {DEPLOY_ID}-backend 2>&1 | tail -30",
                timeout=20,
                silent=True,
            )
            if "Application startup complete" in out or "Uvicorn running" in out:
                print(f"    backend ready @ {(i + 1) * 2}s")
                ready = True
                break
            if "Traceback" in out and ("Error" in out or "Exception" in out):
                print("    ⚠️ backend 启动报错，查看完整日志：")
                ssh_run(
                    client,
                    f"docker logs --tail=150 {DEPLOY_ID}-backend 2>&1 | tail -120",
                    timeout=20,
                )
                break
        if not ready:
            print("    ⚠️ backend 未就绪 / 启动超时")

        print("\n[5] HTTP smoke - 新接口可达性")
        smoke_paths = [
            "/api/openapi.json",
            "/api/member/plans",
            "/member-center",
        ]
        for path in smoke_paths:
            ssh_run(
                client,
                f"curl -sk -o /tmp/resp.txt -w '{path} → %{{http_code}}\\n' '{BASE_URL}{path}'; "
                f"head -c 200 /tmp/resp.txt | tr -d '\\r'; echo",
                timeout=20,
            )

        print("\n[6] 容器内 pytest test_member_center_v2.py")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend bash -c "
            f"'cd /app && python -m pytest tests/test_member_center_v2.py -v --tb=short 2>&1 | tail -100'",
            timeout=400,
        )

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        client.close()


if __name__ == "__main__":
    main()
