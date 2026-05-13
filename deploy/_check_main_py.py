"""检查服务器和容器中 main.py 的差异"""
from __future__ import annotations
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BE = f"{DEPLOY_ID}-backend"


def run(cli, cmd, timeout: int = 60):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        print("=== 宿主 main.py md5 ===")
        rc, o, e = run(cli, f"md5sum {REMOTE_PROJ}/backend/app/main.py")
        print(o, e)
        print("=== 容器 main.py md5 ===")
        rc, o, e = run(cli, f"sudo docker exec {BE} md5sum /app/app/main.py")
        print(o, e)
        print("=== 宿主 main.py grep prd469 ===")
        rc, o, e = run(cli, f"grep -n 'prd469' {REMOTE_PROJ}/backend/app/main.py")
        print(o, e)
        print("=== 容器 main.py grep prd469 ===")
        rc, o, e = run(cli, f"sudo docker exec {BE} grep -n 'prd469' /app/app/main.py")
        print(o, e)
        print("=== 容器 main.py grep include_router (前30行) ===")
        rc, o, e = run(cli, f"sudo docker exec {BE} grep -n 'include_router' /app/app/main.py | head -50")
        print(o, e)
        print("=== docker-compose.yml backend volume mounts ===")
        rc, o, e = run(cli, f"grep -A 20 'backend:' {REMOTE_PROJ}/docker-compose.yml | head -30")
        print(o, e)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
