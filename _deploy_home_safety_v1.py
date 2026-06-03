"""
[PRD-HOME-SAFETY-V1 2026-05-27] 智能硬件绑定 · 居家安全设备 v1.0 部署脚本

变更的端：
- 后端 backend/app/api/home_safety_v1.py（新增）
- 后端 backend/app/main.py（注册 router）
- H5 h5-web/src/app/home-safety/page.tsx（新增）
- H5 h5-web/src/app/health-profile/page.tsx（新增入口卡片）
- Admin admin-web/src/app/(admin)/home-safety/page.tsx（新增）
- Admin admin-web/src/app/(admin)/layout.tsx（菜单注册）
- 后端测试 backend/tests/test_home_safety_v1.py（新增 12 用例）
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
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

FILES_TO_UPLOAD = [
    "backend/app/api/home_safety_v1.py",
    "backend/app/main.py",
    "backend/tests/test_home_safety_v1.py",
    "h5-web/src/app/home-safety/page.tsx",
    "h5-web/src/app/health-profile/page.tsx",
    "admin-web/src/app/(admin)/home-safety/page.tsx",
    "admin-web/src/app/(admin)/layout.tsx",
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
        for rel in FILES_TO_UPLOAD:
            local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
            remote = f"{REMOTE_BASE}/{rel}"
            if not os.path.isfile(local):
                print(f"[SKIP missing] {local}")
                continue
            print(f"[UPLOAD] {rel}")
            mkdir_p(sftp, remote)
            sftp.put(local, remote)
    finally:
        sftp.close()


def main():
    print(f"[1/8] SSH connect {HOST}")
    client = ssh_connect()

    print("[2/8] ls remote base")
    rc, out, err = run(client, f"ls -la {REMOTE_BASE} | head -8")
    if rc != 0:
        print("远程目录不存在")
        sys.exit(1)

    print("[3/8] upload changed files")
    upload_files(client)

    print("[4/8] rebuild backend container")
    run(client, f"cd {REMOTE_BASE} && docker compose build backend 2>&1 | tail -40", timeout=900)
    run(client, f"cd {REMOTE_BASE} && docker compose up -d backend 2>&1 | tail -10", timeout=300)
    time.sleep(8)

    print("[5/8] rebuild h5-web container")
    run(client, f"cd {REMOTE_BASE} && docker compose build h5-web 2>&1 | tail -40", timeout=900)
    run(client, f"cd {REMOTE_BASE} && docker compose up -d h5-web 2>&1 | tail -10", timeout=300)
    time.sleep(10)

    print("[6/8] rebuild admin-web container")
    run(client, f"cd {REMOTE_BASE} && docker compose build admin-web 2>&1 | tail -40", timeout=900)
    run(client, f"cd {REMOTE_BASE} && docker compose up -d admin-web 2>&1 | tail -10", timeout=300)
    time.sleep(8)

    print("[7/8] docker compose ps")
    run(client, f"cd {REMOTE_BASE} && docker compose ps")

    print("[8/8] HTTP smoke")
    urls = [
        f"{BASE_URL}/api/admin/home_safety/dict/device_types",
        f"{BASE_URL}/api/home_safety/devices",
        f"{BASE_URL}/api/admin/home_safety/callback_config",
        f"{BASE_URL}/callback/home_safety/alarm",  # POST 接口，GET 也会返回 405
        f"{BASE_URL}/home-safety/",  # H5 主页
        f"{BASE_URL}/health-profile/",  # H5 健康档案
    ]
    for u in urls:
        run(client, f"curl -s -o /dev/null -w '%{{http_code}}  {u}\\n' '{u}'")

    client.close()
    print("\n=== 部署完成 ===")
    print(f"H5 居家安全设备：{BASE_URL}/home-safety/")
    print(f"Admin 后台菜单：{BASE_URL}/admin/home-safety/")


if __name__ == "__main__":
    main()
