"""[PRD-GUARDIAN-V1.3.1 2026-05-27] 守护人体系 v1.3.1 部署脚本

将 v1.3.1 改造涉及的文件上传到远程服务器，并重新构建+启动 backend / h5-web 容器，
最后执行后端 pytest 验证 + curl 健康检查。
"""

import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

# v1.3.1 涉及文件
FILES_TO_UPLOAD = [
    # 后端
    ("backend/app/api/guardian_system_v13.py",
     f"{REMOTE_BASE}/backend/app/api/guardian_system_v13.py"),
    ("backend/app/api/family_management.py",
     f"{REMOTE_BASE}/backend/app/api/family_management.py"),
    ("backend/tests/test_guardian_system_v131.py",
     f"{REMOTE_BASE}/backend/tests/test_guardian_system_v131.py"),
    # H5 前端
    ("h5-web/src/app/health-profile/i-guard/page.tsx",
     f"{REMOTE_BASE}/h5-web/src/app/health-profile/i-guard/page.tsx"),
    ("h5-web/src/app/health-profile/v13/page.tsx",
     f"{REMOTE_BASE}/h5-web/src/app/health-profile/v13/page.tsx"),
    # 小程序
    ("miniprogram/pages/family-guardian-list/index.wxml",
     f"{REMOTE_BASE}/miniprogram/pages/family-guardian-list/index.wxml"),
    ("miniprogram/pages/health-profile/index.wxml",
     f"{REMOTE_BASE}/miniprogram/pages/health-profile/index.wxml"),
    # Flutter
    ("flutter_app/lib/screens/health/health_profile_screen.dart",
     f"{REMOTE_BASE}/flutter_app/lib/screens/health/health_profile_screen.dart"),
]


def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return client


def run(client, cmd, timeout=300, log=True):
    if log:
        print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if log:
        if out.strip():
            print(out)
        if err.strip():
            print(f"[stderr] {err}")
    return exit_status, out, err


def mkdir_p(sftp, path):
    parts = path.replace("\\", "/").split("/")
    cur = ""
    for p in parts[:-1]:
        if not p:
            cur = "/"
            continue
        cur = cur.rstrip("/") + "/" + p if cur else p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass


def upload_files(client):
    sftp = client.open_sftp()
    try:
        for local_rel, remote in FILES_TO_UPLOAD:
            local = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
            if not os.path.isfile(local):
                print(f"[SKIP missing] {local}")
                continue
            print(f"[UPLOAD] {local_rel} -> {remote}")
            mkdir_p(sftp, remote)
            sftp.put(local, remote)
    finally:
        sftp.close()


def main():
    print(f"[1/7] SSH 连接到 {HOST} ...")
    client = ssh_connect()

    print(f"[2/7] 检查远程项目目录 {REMOTE_BASE}")
    rc, out, err = run(client, f"ls -la {REMOTE_BASE} | head -10")
    if rc != 0:
        print("远程目录不存在，停止部署")
        sys.exit(1)

    print("[3/7] 上传 v1.3.1 涉及的文件 ...")
    upload_files(client)

    print("[4/7] 在远程执行后端 pytest v1.3.1 验证 ...")
    test_cmd = (
        f"cd {REMOTE_BASE} && "
        f"docker compose exec -T backend python -m pytest "
        f"tests/test_guardian_system_v131.py -v 2>&1 | tail -80"
    )
    rc, out, err = run(client, test_cmd, timeout=600)
    pytest_passed = " passed" in out and " failed" not in out.split("=========================")[-1]
    print(f"[4/7] pytest 结果：{'PASS' if pytest_passed else 'CHECK_NEEDED'}")

    print("[5/7] 重新构建 backend + h5-web 容器 ...")
    rc, out, err = run(
        client,
        f"cd {REMOTE_BASE} && docker compose build backend h5-web 2>&1 | tail -40",
        timeout=1200,
    )

    print("[6/7] 启动容器 ...")
    rc, out, err = run(
        client,
        f"cd {REMOTE_BASE} && docker compose up -d backend h5-web 2>&1 | tail -20",
        timeout=300,
    )
    time.sleep(10)

    print("[7/7] 验证容器健康 + 关键 URL ...")
    run(client, f"cd {REMOTE_BASE} && docker compose ps | head -10")
    run(
        client,
        f"curl -s -o /dev/null -w 'i-guard HTTP %{{http_code}}\\n' "
        f"https://{HOST}/autodev/{DEPLOY_ID}/h5/health-profile/i-guard",
    )
    run(
        client,
        f"curl -s -o /dev/null -w 'v13 redirect HTTP %{{http_code}}\\n' "
        f"https://{HOST}/autodev/{DEPLOY_ID}/h5/health-profile/v13",
    )
    run(
        client,
        f"curl -s -o /dev/null -w 'api family/list HTTP %{{http_code}}\\n' "
        f"https://{HOST}/autodev/{DEPLOY_ID}/api/guardian/v13/family/list",
    )

    client.close()
    print("\n=== v1.3.1 部署完成 ===")


if __name__ == "__main__":
    main()
