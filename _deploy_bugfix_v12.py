"""[Bug 修复 v1.2] 全量部署 + 服务器测试

流程：
1. 把本地改动 rsync/scp 上去（实际通过 git pull or scp）
2. rebuild backend + admin-web + h5-web 镜像
3. 重启容器
4. 容器内运行 pytest（带新增的 v1.2 修复测试）
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
        print("\n[1] 上传修改的源码文件")
        files = [
            # 后端
            "backend/app/api/guardian_system_v12.py",
            "backend/tests/test_guardian_system_v12.py",
            # admin-web
            "admin-web/src/app/(admin)/emergency-sources/page.tsx",
            "admin-web/src/app/(admin)/emergency-sources/page.legacy.tsx",
            "admin-web/src/app/(admin)/family-management/page.tsx",
            "admin-web/src/app/(admin)/family-management/page.legacy.tsx",
            # h5-web
            "h5-web/src/components/ai-chat/MoreMenu.tsx",
            "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
            "h5-web/src/app/health-profile/page.tsx",
            "h5-web/src/app/health-profile/i-guard/page.tsx",
        ]
        for rel in files:
            local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
            remote = f"{REMOTE_PROJECT_DIR}/{rel}"
            # 确保目录存在
            remote_dir = os.path.dirname(remote)
            ssh_run(client, f"mkdir -p '{remote_dir}'", timeout=10, silent=True)
            scp_put(sftp, local, remote)

        print("\n[2] Rebuild backend + h5-web + admin-web")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build backend 2>&1 | tail -8",
            timeout=600,
        )
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build admin-web h5-web 2>&1 | tail -15",
            timeout=900,
        )

        print("\n[3] 重启容器")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose up -d backend admin-web h5-web 2>&1 | tail -10",
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
            if "Error" in out and "Traceback" in out:
                print("    ⚠️ backend 启动报错，查看完整日志：")
                ssh_run(
                    client,
                    f"docker logs --tail=120 {DEPLOY_ID}-backend 2>&1 | tail -100",
                    timeout=20,
                )
                break
        if not ready:
            print("    ⚠️ backend 未就绪")

        print("\n[5] HTTP smoke - 新接口可达性")
        smoke_paths = [
            "/api/openapi.json",
            "/api/admin/emergency-sources",
            "/api/admin/family-management",
            "/health-profile/i-guard",
            "/member-center",
            "/admin/family-management",
            "/admin/emergency-sources",
        ]
        for path in smoke_paths:
            ssh_run(
                client,
                f"curl -sk -o /tmp/resp.txt -w '{path} → %{{http_code}}\\n' '{BASE_URL}{path}'; "
                f"echo;  head -c 200 /tmp/resp.txt | tr -d '\\r'; echo",
                timeout=15,
            )

        print("\n[6] 验证 UTF-8 Content-Type（中文乱码修复核心）")
        ssh_run(
            client,
            f"curl -sk -I '{BASE_URL}/api/admin/emergency-sources' 2>&1 | grep -i content-type || echo '需登录'; "
            # admin 接口需要 token，从 admin login 获取
            f"echo '--- admin login ---'; "
            f"TOKEN=$(curl -sk -X POST '{BASE_URL}/api/admin/login' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"phone\":\"13900000000\",\"password\":\"admin123\"}}' "
            f"| python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get(\"token\") or d.get(\"access_token\") or \"\")'); "
            f"echo \"token=$TOKEN\"; "
            f"if [ -n \"$TOKEN\" ]; then "
            f"curl -sk -i -H \"Authorization: Bearer $TOKEN\" '{BASE_URL}/api/admin/emergency-sources' "
            f"| grep -i -E 'content-type|HTTP/' | head -5; "
            f"curl -sk -H \"Authorization: Bearer $TOKEN\" '{BASE_URL}/api/admin/emergency-sources' "
            f"| head -c 400; echo; fi",
            timeout=30,
        )

        print("\n[7] 服务器内单元测试（含新增的 v1.2 修复测试 T13-T18）")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend bash -c "
            f"'cd /app && python -m pytest tests/test_guardian_system_v12.py -v 2>&1 | tail -50'",
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
