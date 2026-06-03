"""仅重传 backend 文件并 restart backend 容器（因只改了 home_safety_v1.py 的路由路径）。"""
import os
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

FILES = [
    "backend/app/api/home_safety_v1.py",
    "backend/tests/test_home_safety_v1.py",
]


def run(c, cmd, t=300):
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print("[err]", err)


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = c.open_sftp()
    for rel in FILES:
        local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
        remote = f"{REMOTE_BASE}/{rel}"
        print(f"[UPLOAD] {rel}")
        sftp.put(local, remote)
    sftp.close()
    run(c, f"cd {REMOTE_BASE} && docker compose restart backend 2>&1 | tail -10")
    time.sleep(6)
    run(c, f"cd {REMOTE_BASE} && docker compose ps")
    c.close()


if __name__ == "__main__":
    main()
