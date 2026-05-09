# -*- coding: utf-8 -*-
"""[Bug-433 增量] 服务器拉最新代码 + 仅重建 backend 容器（h5 未改）。"""
import paramiko, sys, time

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

    def run(cmd, timeout=600):
        print(f"\n$ {cmd}", flush=True)
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out); sys.stdout.flush()
        if err:
            sys.stderr.write(err); sys.stderr.flush()
        return stdout.channel.recv_exit_status()

    if run(f"cd {PROJECT_DIR} && git fetch --all --prune") != 0:
        return 1
    if run(f"cd {PROJECT_DIR} && git reset --hard origin/master") != 0:
        return 2
    if run(f"cd {PROJECT_DIR} && docker compose build backend") != 0:
        return 3
    if run(f"cd {PROJECT_DIR} && docker compose up -d backend") != 0:
        return 4

    print("[*] 等待 backend 健康", flush=True)
    for i in range(30):
        time.sleep(3)
        rc = run(f"curl -s -o /dev/null -w '%{{http_code}}' {BASE}/api/health && echo", timeout=15)
        # 直接判断 200，但 run 里没拿到 stdout 字符串，简化处理：再 stat 一次
        time.sleep(0.5)
        # 直接用一次 SSH 命令拿状态
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
