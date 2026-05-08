"""强制重启 backend，让其重新接入 docker 网络。"""
import paramiko, sys, time

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run(cmd, timeout=600):
    print(f"\n>>> {cmd}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"[stderr]\n{err}")
    print(f"[exit={code}]")
    return code, out, err


try:
    # 1. 看 db 容器健康
    run(f"docker ps -a --filter 'name={DEPLOY_ID}' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

    # 2. 看 db 是否在 backend 同一网络
    run(f"docker inspect {DEPLOY_ID}-db --format '{{{{json .NetworkSettings.Networks}}}}'")

    # 3. 看 backend 网络
    run(f"docker inspect {DEPLOY_ID}-backend --format '{{{{json .NetworkSettings.Networks}}}}'")

    # 4. 完整 down + up
    run(f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml down 2>&1 | tail -10")
    time.sleep(3)
    run(f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1 | tail -20")

    print("\n等待启动 30 秒...")
    time.sleep(30)

    run(f"docker ps --filter 'name={DEPLOY_ID}' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

    for i in range(8):
        code, out, _ = run(
            f"curl -s -o /dev/null -w '%{{http_code}}' 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health'"
        )
        if out.strip() == "200":
            print(f"  health: 200 OK after {i+1} probe")
            break
        time.sleep(5)
finally:
    cli.close()
