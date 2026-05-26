"""[守护人体系 PRD v1.3 2026-05-26] 部署 + 自动化测试

流程：
1. 上传新增/修改的源码文件
2. rebuild backend + h5-web
3. 重启容器
4. 容器内运行 pytest（v1.3 测试）
5. HTTP smoke 测试
"""
from __future__ import annotations
import os
import time
import sys
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
        print(f"[ssh] $ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    combined = out + ("\n[stderr]\n" + err if err.strip() else "")
    if not silent:
        tail = "\n".join(combined.splitlines()[-60:])
        print(tail)
        print(f"[ssh] exit={rc}")
    return rc, combined


def scp_put(sftp, local_path, remote_path):
    print(f"[scp] {os.path.basename(local_path)} -> {remote_path}")
    sftp.put(local_path, remote_path)


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = client.open_sftp()

    try:
        print("\n[1] 上传源码文件")
        files = [
            # 后端
            "backend/app/api/guardian_system_v13.py",
            "backend/app/main.py",
            "backend/tests/test_guardian_system_v13.py",
            # h5-web
            "h5-web/src/app/health-profile/v13/page.tsx",
            "h5-web/src/app/health-profile/i-guard/page.tsx",
        ]
        for rel in files:
            local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
            remote = f"{REMOTE_PROJECT_DIR}/{rel}"
            remote_dir = os.path.dirname(remote)
            ssh_run(client, f"mkdir -p '{remote_dir}'", timeout=10, silent=True)
            scp_put(sftp, local, remote)

        print("\n[2] Rebuild backend + h5-web")
        rc, _ = ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build backend 2>&1 | tail -10",
            timeout=600,
        )
        rc, _ = ssh_run(
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
                f"curl -sS -m 3 http://127.0.0.1/autodev/{DEPLOY_ID}/api/health 2>&1 | head -5",
                timeout=10,
                silent=True,
            )
            if rc == 0 and ("ok" in out.lower() or "healthy" in out.lower() or '"status"' in out):
                print(f"[ready] backend healthy (after {(i+1)*2}s)")
                ready = True
                break
        if not ready:
            print("[warn] backend health check timeout; continuing anyway")

        print("\n[5] 容器内运行 v1.3 测试")
        rc, out = ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose exec -T backend "
            f"python -m pytest tests/test_guardian_system_v13.py -v --tb=short 2>&1 | tail -60",
            timeout=300,
        )
        test_passed = rc == 0

        print("\n[6] HTTP smoke 测试关键接口")
        smoke_urls = [
            f"{BASE_URL}/api/health",
            # 不带 token 的接口会返 401，但说明路由已注册
            f"{BASE_URL}/api/guardian/v13/family/list",
        ]
        for u in smoke_urls:
            rc, out = ssh_run(
                client,
                f"curl -sS -o /dev/null -w '%{{http_code}}' -m 5 '{u}'",
                timeout=10,
            )
            print(f"[smoke] {u} -> {out.strip()}")

        print("\n[7] H5 前端构建状态")
        ssh_run(
            client,
            f"docker logs {DEPLOY_ID}-h5-web 2>&1 | tail -10",
            timeout=10,
        )

        print("\n[done] 部署完成")
        sys.exit(0 if test_passed else 2)
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        client.close()


if __name__ == "__main__":
    main()
