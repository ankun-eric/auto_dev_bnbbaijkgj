# -*- coding: utf-8 -*-
"""部署：删除家庭成员卡点提示修复（仅后端单服务重建）"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"


def run(cli, cmd, timeout=1200):
    print(f"\n$ {cmd}", flush=True)
    chan = cli.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    buf = b""
    while True:
        if chan.recv_ready():
            buf += chan.recv(65536)
        if chan.exit_status_ready() and not chan.recv_ready():
            break
    while chan.recv_ready():
        buf += chan.recv(65536)
    rc = chan.recv_exit_status()
    chan.close()
    print(buf.decode("utf-8", "ignore"), flush=True)
    print(f"[rc={rc}]", flush=True)
    return rc, buf.decode("utf-8", "ignore")


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username=USER, password=PWD, timeout=30)
    print("SSH connected", flush=True)

    run(cli, f"cd {PROJ} && git fetch origin master 2>&1 | tail -3; git reset --hard origin/master 2>&1 | tail -2; git log -1 --oneline")

    run(cli, f"cd {PROJ} && BC=$(git log -1 --format=%H); (grep -q '^BUILD_COMMIT=' .env 2>/dev/null && sed -i \"s|^BUILD_COMMIT=.*|BUILD_COMMIT=$BC|\" .env) || echo \"BUILD_COMMIT=$BC\" >> .env; echo BUILD_COMMIT=$BC")

    run(cli, f"cd {PROJ} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -20", timeout=1500)
    run(cli, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -12")
    run(cli, f"sleep 10; cd {PROJ} && docker compose -f docker-compose.prod.yml ps")

    rc, gw = run(cli, "docker ps --format '{{.Names}}' | grep -iE 'gateway' | head -1")
    gw = gw.strip()
    print("gateway:", repr(gw), flush=True)
    if gw:
        run(cli, f"docker network connect {DEPLOY_ID}-network {gw} 2>/dev/null; docker exec {gw} nginx -s reload 2>&1; echo reloaded")

    run(cli, f"curl -s -o /dev/null -w 'health=%{{http_code}}\\n' https://{HOST}/autodev/{DEPLOY_ID}/api/health")
    run(cli, f"curl -s -o /dev/null -w 'root=%{{http_code}}\\n' https://{HOST}/autodev/{DEPLOY_ID}/")
    run(cli, f"curl -s -o /dev/null -w 'archive_list=%{{http_code}}\\n' https://{HOST}/autodev/{DEPLOY_ID}/health-profile/archive-list")

    cli.close()
    print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
