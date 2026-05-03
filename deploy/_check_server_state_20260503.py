"""快速检查服务器当前部署状态：HEAD commit、容器状态、关键 URL"""
from __future__ import annotations
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def run(ssh, cmd, timeout=120):
    print(f">>> {cmd[:200]}")
    _, so, se = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    o = so.read().decode("utf-8", "ignore")
    e = se.read().decode("utf-8", "ignore")
    rc = so.channel.recv_exit_status()
    if o.strip():
        print(o.rstrip()[-3000:])
    if e.strip():
        print(f"[stderr] {e.rstrip()[-1500:]}")
    print(f"<<< exit={rc}\n")
    return rc, o, e


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        run(ssh, f"cd {PROJ_DIR} && git log -1 --format='%H %s' 2>&1")
        run(ssh, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Image}}}}'")
        run(ssh, f"ls -la {PROJ_DIR}/downloads/ 2>&1 | tail -20 || echo 'no downloads dir'")
        # 验证关键 URL
        urls = [
            "/api/health",
            "/api/cards",
            "/api/admin/cards/dashboard/summary",
            "/cards",
            "/cards/wallet",
            "/admin/product-system/cards/dashboard",
        ]
        print("=== URL 检查 ===")
        for p in urls:
            cmd = f"curl -ksL -o /dev/null -w '%{{http_code}}' --max-time 10 '{BASE_URL}{p}'"
            _, so, _ = ssh.exec_command(cmd, timeout=20)
            print(f"  {p}: {so.read().decode('utf-8','ignore').strip()}")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
