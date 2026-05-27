"""
[PRD-HOME-SAFETY-V1 BUGFIX 2026-05-27] 居家安全设备 v1.0 三 Bug 合并修复部署脚本

变更：
- 后端 backend/app/api/home_safety_v1.py: 时间字段附 'Z' 后缀（UTC 明示）+ callback_config 增加 updated_at 字段
- 后端 backend/tests/test_home_safety_v1.py: 新增 3 个时间字段断言用例
- Admin admin-web/src/app/(admin)/home-safety/page.tsx: 时间列 render formatDateTime + 表格 scroll x
- Admin admin-web/src/lib/datetime.ts: 新增（dayjs UTC -> 北京时间）
- H5 h5-web/src/app/home-safety/page.tsx: 修复响应体取值层级 + 时间格式化 + 加日志
- H5 h5-web/src/lib/datetime.ts: 新增（dayjs UTC -> 北京时间）
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
    "backend/tests/test_home_safety_v1.py",
    "h5-web/src/app/home-safety/page.tsx",
    "h5-web/src/lib/datetime.ts",
    "admin-web/src/app/(admin)/home-safety/page.tsx",
    "admin-web/src/lib/datetime.ts",
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
    print(f"[1/7] SSH connect {HOST}")
    client = ssh_connect()

    print("[2/7] upload changed files")
    upload_files(client)

    print("[3/7] restart backend (no rebuild needed - python hot reload via container restart)")
    # backend 是 python 文件，重启容器即可加载新代码
    run(client, f"cd {REMOTE_BASE} && docker compose restart backend 2>&1 | tail -10", timeout=120)
    time.sleep(8)

    print("[4/7] rebuild h5-web container")
    run(client, f"cd {REMOTE_BASE} && docker compose build h5-web 2>&1 | tail -30", timeout=900)
    run(client, f"cd {REMOTE_BASE} && docker compose up -d h5-web 2>&1 | tail -10", timeout=300)
    time.sleep(10)

    print("[5/7] rebuild admin-web container")
    run(client, f"cd {REMOTE_BASE} && docker compose build admin-web 2>&1 | tail -30", timeout=900)
    run(client, f"cd {REMOTE_BASE} && docker compose up -d admin-web 2>&1 | tail -10", timeout=300)
    time.sleep(8)

    print("[6/7] docker compose ps")
    run(client, f"cd {REMOTE_BASE} && docker compose ps")

    print("[7/7] HTTP smoke")
    urls = [
        f"{BASE_URL}/api/admin/home_safety/dict/device_types",
        f"{BASE_URL}/api/home_safety/devices",
        f"{BASE_URL}/api/admin/home_safety/callback_config",
        f"{BASE_URL}/home-safety/",
        f"{BASE_URL}/admin/home-safety",
    ]
    for u in urls:
        run(client, f"curl -s -o /dev/null -w '%{{http_code}}  {u}\\n' '{u}'")

    client.close()
    print("\n=== BUGFIX 部署完成 ===")


if __name__ == "__main__":
    main()
