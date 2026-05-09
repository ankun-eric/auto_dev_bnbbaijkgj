# -*- coding: utf-8 -*-
"""[Bug-433 增量] 用 SFTP 直接上传 chat.py 到服务器（避开服务器 -> GitHub 网络问题）。"""
import paramiko, sys, time, os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)

    sftp = ssh.open_sftp()
    local = "backend/app/api/chat.py"
    remote = f"{PROJECT_DIR}/backend/app/api/chat.py"
    print(f"sftp put {local} -> {remote}", flush=True)
    sftp.put(local, remote)
    sftp.close()

    def run(cmd, timeout=900):
        print(f"\n$ {cmd}", flush=True)
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out); sys.stdout.flush()
        if err:
            sys.stderr.write(err); sys.stderr.flush()
        return stdout.channel.recv_exit_status()

    if run(f"cd {PROJECT_DIR} && docker compose build backend") != 0:
        return 3
    if run(f"cd {PROJECT_DIR} && docker compose up -d backend") != 0:
        return 4

    print("[*] 等待 backend 健康", flush=True)
    for i in range(30):
        time.sleep(3)
        stdin, stdout, stderr = ssh.exec_command(f"curl -s -o /dev/null -w '%{{http_code}}' {BASE}/api/health", timeout=15)
        code = stdout.read().decode("utf-8", errors="replace").strip()
        print(f"  [t+{(i+1)*3}s] /api/health -> {code}", flush=True)
        if code == "200":
            ssh.close()
            return 0
    ssh.close()
    return 5


if __name__ == "__main__":
    sys.exit(main())
