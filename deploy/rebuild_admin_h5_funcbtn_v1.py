"""[PRD-AICHAT-FUNCBTN-OPTIM-V1] 单独重建 admin-web 与 h5-web 容器"""
import paramiko
import time

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"


def run_ssh(client, cmd, timeout=1200):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip())
    if err.strip() and "warning:" not in err:
        print(f"[STDERR] {err.strip()[:500]}")
    print(f"[EXIT CODE] {code}")
    return code, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)

    # 列出所有 docker compose service
    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml config --services")

    # 重建 admin-web + h5-web
    print("\n=== 重建 admin-web ===")
    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web", timeout=900)

    print("\n=== 重建 h5-web ===")
    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web", timeout=1200)

    print("\n=== 重启 ===")
    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d admin-web h5-web", timeout=180)

    time.sleep(15)

    print("\n=== gateway 重连 + reload ===")
    run_ssh(client, "docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway 2>/dev/null || true")
    run_ssh(client, "docker exec gateway nginx -s reload || true")

    run_ssh(client, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps")

    client.close()


if __name__ == "__main__":
    main()
