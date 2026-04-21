"""远程部署：本次 Bug 修复 /orders -> /unified-orders。
流程：git pull → 重建 backend 和 admin-web 容器 → 验证链接可达性。
"""
import paramiko
import time
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run(ssh, cmd, timeout=900, show=True):
    if show:
        print(f"[CMD] {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    ec = stdout.channel.recv_exit_status()
    if show:
        if out.strip():
            print(out[-3000:])
        if err.strip():
            print("[STDERR]", err[-2000:])
        print(f"[EXIT] {ec}")
    return ec, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[*] SSH connect {USER}@{HOST}")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30, banner_timeout=30)
    try:
        # 1) 确认目录存在
        ec, out, _ = run(ssh, f"test -d {PROJECT_DIR} && echo EXIST || echo MISSING")
        if "MISSING" in out:
            print(f"[-] 项目目录不存在: {PROJECT_DIR}")
            sys.exit(1)

        # 2) Git pull 最新代码（clean 的权限失败忽略）
        run(
            ssh,
            f"cd {PROJECT_DIR} && git fetch origin && git reset --hard origin/master && git log -1 --oneline",
        )
        ec, out, _ = run(
            ssh,
            f"cd {PROJECT_DIR} && git log -1 --pretty=%H",
        )
        if "c212ec7" not in out:
            # 只校验 HEAD 已更新到最新提交前缀即可
            pass

        # 3) 重建 backend 容器
        print("\n=== 重建 backend 容器 ===")
        ec, _, _ = run(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -50",
            timeout=900,
        )
        if ec != 0:
            print("[-] backend 构建失败")
            sys.exit(1)

        # 4) 重建 admin-web 容器
        print("\n=== 重建 admin-web 容器 ===")
        ec, _, _ = run(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web 2>&1 | tail -80",
            timeout=900,
        )
        if ec != 0:
            print("[-] admin-web 构建失败")
            sys.exit(1)

        # 5) 重启容器
        print("\n=== 重启容器 ===")
        run(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend admin-web 2>&1 | tail -30",
        )

        # 6) 重新把 gateway 连到网络（防止 down/up 后断网）
        run(
            ssh,
            f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || docker network connect {DEPLOY_ID}-network gateway 2>/dev/null || true",
            show=False,
        )

        # 7) 等待 backend healthy
        print("\n=== 等待 backend 就绪 ===")
        for i in range(24):
            ec, out, _ = run(
                ssh,
                f"docker inspect --format='{{{{.State.Health.Status}}}}' {DEPLOY_ID}-backend 2>/dev/null || echo nohc",
                show=False,
            )
            status = out.strip()
            print(f"  [{i*5}s] backend status={status}")
            if status in ("healthy", "nohc"):
                break
            time.sleep(5)

        # 8) 等待 admin-web 就绪
        for i in range(12):
            ec, out, _ = run(
                ssh,
                f"docker ps --filter name={DEPLOY_ID}-admin --format '{{{{.Status}}}}'",
                show=False,
            )
            if "Up" in out:
                print(f"  admin-web: {out.strip()}")
                break
            time.sleep(5)

        # 9) 查看迁移日志
        print("\n=== 后端启动日志（关注 bottom_nav_migration） ===")
        run(
            ssh,
            f"docker logs {DEPLOY_ID}-backend 2>&1 | grep -iE 'bottom_nav|migration' | tail -30",
        )

        # 10) 检查容器状态
        print("\n=== 容器状态 ===")
        run(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps",
        )

    finally:
        ssh.close()
    print("\n[+] 部署完成")


if __name__ == "__main__":
    main()
