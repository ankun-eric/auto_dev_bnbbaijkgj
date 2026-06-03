"""通过 docker-compose 重建管理后台镜像并重启容器。"""
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    return c


def run(c, cmd, timeout=1500):
    print(f"$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out[-6000:]:
        print(out[-6000:])
    if err[-2000:]:
        print("STDERR:", err[-2000:])
    print(f"(rc={rc})\n")
    return rc, out, err


def main():
    c = conn()
    proj = f"/home/ubuntu/{DEPLOY_ID}"
    # 查看 docker-compose service 名
    run(c, f"grep -E 'service|container_name|admin' {proj}/docker-compose.prod.yml | head -40")

    # rebuild admin-web only
    rc, out, _ = run(
        c,
        f"cd {proj} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -50",
        timeout=1500,
    )

    run(
        c,
        f"cd {proj} && docker compose -f docker-compose.prod.yml up -d --no-deps admin-web 2>&1 | tail -20",
        timeout=120,
    )
    time.sleep(10)
    run(c, f"docker ps --filter name={DEPLOY_ID}-admin --format '{{{{.Status}}}}'")
    run(c, f"docker logs --tail 20 {DEPLOY_ID}-admin 2>&1 | tail -20")
    # 测试 HTTP 入口
    base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    run(c, f"curl -skL -o /dev/null -w 'admin %{{http_code}}\\n' '{base_url}/admin/login'")


if __name__ == "__main__":
    main()
