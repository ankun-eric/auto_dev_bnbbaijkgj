"""[PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 远程部署脚本：H5 镜像重建 + 容器重启。

部署唯一标识：6b099ed3-7175-4a78-91f4-44570c84ed27
基础URL：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27
"""
from __future__ import annotations
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run(client, cmd, timeout=600):
    print(f"\n>>> {cmd}\n", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out, flush=True)
    if err:
        print("STDERR:", err, flush=True)
    print(f"<<< exit_code={rc}", flush=True)
    return rc, out, err


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)

    # 1) 探测项目目录
    rc, out, _ = run(cli, f"ls -la {PROJECT_DIR}/ 2>&1 | head -n 40")
    if rc != 0:
        print("项目目录不存在，退出")
        cli.close()
        sys.exit(1)

    # 2) git pull —— 把本次提交的代码同步到服务器（本地未必先推送，所以这里先尝试）
    run(cli, f"cd {PROJECT_DIR} && git status 2>&1 | head -n 40")
    rc, out, _ = run(cli, f"cd {PROJECT_DIR} && git fetch --all 2>&1 | tail -n 20")
    rc, out, _ = run(cli, f"cd {PROJECT_DIR} && git reset --hard origin/master 2>&1 | tail -n 5")

    # 3) 显示当前 docker-compose 服务
    run(cli, f"cd {PROJECT_DIR} && docker compose ps 2>&1 || docker-compose ps 2>&1")

    # 4) 重新构建 H5 frontend 镜像并启动
    rc, out, err = run(
        cli,
        f"cd {PROJECT_DIR} && docker compose build frontend 2>&1 | tail -n 60",
        timeout=900,
    )
    if rc != 0:
        rc, out, err = run(
            cli,
            f"cd {PROJECT_DIR} && docker-compose build frontend 2>&1 | tail -n 60",
            timeout=900,
        )

    rc, _, _ = run(cli, f"cd {PROJECT_DIR} && docker compose up -d frontend 2>&1 | tail -n 30")
    if rc != 0:
        run(cli, f"cd {PROJECT_DIR} && docker-compose up -d frontend 2>&1 | tail -n 30")

    time.sleep(5)
    run(cli, f"cd {PROJECT_DIR} && docker compose ps 2>&1 || docker-compose ps 2>&1")

    # 5) 检查访问
    run(cli, f"curl -sSI -o /dev/null -w '%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ ")
    run(cli, f"curl -sSI -o /dev/null -w '%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile 2>&1 | tail -n 3")

    cli.close()


if __name__ == "__main__":
    main()
