"""[PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 远程部署脚本：H5 镜像重建 + 容器重启。

部署唯一标识：6b099ed3-7175-4a78-91f4-44570c84ed27
基础URL：https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com
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

    # 2) git pull —— 重试拉取最新提交
    for attempt in range(1, 4):
        rc, out, _ = run(
            cli,
            f"cd {PROJECT_DIR} && git -c http.lowSpeedLimit=0 -c http.lowSpeedTime=0 fetch --all --prune 2>&1 | tail -n 20",
            timeout=300,
        )
        if "fatal" not in out.lower() and "unable to access" not in out.lower():
            break
        print(f"== git fetch 第 {attempt} 次失败，10s 后重试 ==", flush=True)
        time.sleep(10)
    run(cli, f"cd {PROJECT_DIR} && git reset --hard origin/master 2>&1 | tail -n 5")
    run(cli, f"cd {PROJECT_DIR} && git log -1 --oneline 2>&1")

    # 3) 显示当前 docker-compose 服务
    run(cli, f"cd {PROJECT_DIR} && docker compose ps 2>&1 || docker-compose ps 2>&1")

    # 4) 重新构建 H5 镜像（服务名为 h5-web）并启动
    rc, out, err = run(
        cli,
        f"cd {PROJECT_DIR} && docker compose build --no-cache h5-web 2>&1 | tail -n 80",
        timeout=1500,
    )

    rc, _, _ = run(cli, f"cd {PROJECT_DIR} && docker compose up -d h5-web 2>&1 | tail -n 30")

    time.sleep(8)
    run(cli, f"cd {PROJECT_DIR} && docker compose ps 2>&1 || docker-compose ps 2>&1")

    # 5) 检查访问
    run(cli, f"curl -sSI -o /dev/null -w '%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ ")
    run(cli, f"curl -sSI -o /dev/null -w '%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile 2>&1 | tail -n 3")

    cli.close()


if __name__ == "__main__":
    main()
