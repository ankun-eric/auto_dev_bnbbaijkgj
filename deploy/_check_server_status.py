"""检查服务器当前部署状态"""
from __future__ import annotations
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"


def run(cli: paramiko.SSHClient, cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def main() -> None:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        print("=== docker ps (项目相关) ===")
        rc, o, e = run(cli, f"sudo docker ps --format '{{{{.Names}}}} | {{{{.Status}}}}' | grep {DEPLOY_ID} || true")
        print(o, e)
        print("=== 后端是否包含 prd469_health_v5 ===")
        rc, o, e = run(cli, f"ls -la {REMOTE_PROJ}/backend/app/api/prd469_health_v5.py 2>&1 || echo MISSING")
        print(o, e)
        rc, o, e = run(cli, f"grep -n 'prd469_health_v5' {REMOTE_PROJ}/backend/app/main.py 2>&1 | head -5")
        print(o, e)
        rc, o, e = run(cli, f"grep -n 'medical-record\\|hero_metrics' {REMOTE_PROJ}/backend/app/api/prd469_health_v5.py 2>&1 | head -10")
        print(o, e)
        print("=== 后端容器内 routes ===")
        be_name = f"{DEPLOY_ID}-backend"
        rc, o, e = run(cli, f"sudo docker exec {be_name} grep -n 'prd469_health_v5\\|prd469.router' /app/app/main.py 2>&1 | head -10")
        print(o, e)
        rc, o, e = run(cli, f"sudo docker exec {be_name} ls /app/app/api/prd469_health_v5.py 2>&1")
        print(o, e)
        rc, o, e = run(cli, f"sudo docker logs --tail=20 {be_name} 2>&1 | tail -30")
        print("--- backend logs tail ---")
        print(o, e)
        print("=== git 仓库状态 ===")
        rc, o, e = run(cli, f"cd {REMOTE_PROJ} && git log --oneline -5 2>&1 || echo NO_GIT")
        print(o, e)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
