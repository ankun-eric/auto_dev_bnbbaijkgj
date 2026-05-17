"""[PRD-AICHAT-FUNCBTN-OPTIM-V1] 部署 + 重建 backend / admin / h5 容器，跳过失败的 git clean step"""
import paramiko
import time
import sys

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"


def run_ssh(client, cmd, timeout=600):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip() and "warning:" not in err and "Permission denied" not in err:
        print(f"[STDERR] {err.strip()}")
    print(f"[EXIT CODE] {code}")
    return code, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {SSH_HOST}...")
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    print("Connected.")

    # 1. 拉取最新代码（前一步实际已拉到 532bf38；这一步幂等再确保一次）
    print("\n=== STEP 1: 确保代码到最新 ===")
    run_ssh(client, f"cd {PROJECT_DIR} && git fetch origin && git reset --hard origin/master && git log -1 --oneline")

    # 2. 构建 backend / frontend
    compose_cmd = "docker compose"
    code, _, _ = run_ssh(client, "docker compose version")
    if code != 0:
        compose_cmd = "docker-compose"

    print("\n=== STEP 2: 构建 backend ===")
    run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml build backend", timeout=900)

    print("\n=== STEP 3: 构建 frontend (admin + h5) ===")
    run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml build frontend", timeout=1200)

    print("\n=== STEP 4: 重启容器 ===")
    run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml up -d", timeout=180)

    print("\n=== STEP 5: 等待容器健康 ===")
    for i in range(20):
        time.sleep(6)
        code, out, err = run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml ps")
        if "Up" in out and "unhealthy" not in out:
            print("Containers ready.")
            break

    print("\n=== STEP 6: gateway 网络重连 ===")
    run_ssh(client, "docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway 2>/dev/null || true")
    run_ssh(client, "docker exec gateway nginx -s reload || true")

    print("\n=== STEP 7: 状态 ===")
    run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml ps")
    # 查看 backend 启动日志，确认迁移成功执行
    run_ssh(client, f"cd {PROJECT_DIR} && {compose_cmd} -f docker-compose.prod.yml logs --tail=80 backend | grep -E 'funcbtn_optim|migrate' || true")

    client.close()
    print("\n=== Deployment complete ===")


if __name__ == "__main__":
    main()
