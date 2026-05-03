"""验证服务器部署，包括 backend 健康 + pytest 跑通。"""
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"


def run(client, cmd, timeout=300):
    print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    return rc, out, err


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    # 等容器
    print("=== Wait backend up ===")
    for i in range(20):
        rc, out, _ = run(cli, f"docker ps --filter name={DEPLOY_ID}-backend --format '{{{{.Status}}}}'")
        if "Up" in out:
            print(f"backend container status: {out.strip()}")
            break
        time.sleep(3)

    print("\n=== Backend health (inside) ===")
    run(cli, f"docker exec {DEPLOY_ID}-backend curl -s -o /dev/null -w '%{{http_code}}\\n' http://localhost:8000/api/health")
    run(cli, f"docker exec {DEPLOY_ID}-backend curl -s http://localhost:8000/api/pay/available-methods?platform=app")

    print("\n=== /api/docs from outside ===")
    run(cli, f'curl -s -o /dev/null -w "%{{http_code}}\\n" https://{HOST}/autodev/{DEPLOY_ID}/api/docs')

    print("\n=== Install pytest in backend container & run tests ===")
    run(cli,
        f"docker exec {DEPLOY_ID}-backend pip install --quiet pytest pytest-asyncio aiosqlite httpx",
        timeout=180,
    )
    run(cli,
        f"docker exec -w /app -e PYTEST_CURRENT_TEST=1 {DEPLOY_ID}-backend python -m pytest tests/test_payment_config_v1.py -v",
        timeout=300,
    )

    print("\n=== Logs (last 30) ===")
    run(cli, f"docker logs --tail=30 {DEPLOY_ID}-backend")

    cli.close()


if __name__ == "__main__":
    main()
