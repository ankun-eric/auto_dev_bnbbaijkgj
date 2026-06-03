"""重建管理后台前端，使报文类型列等变更生效。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    return c


def run(c, cmd, timeout=900):
    print(f"$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out[-3000:]:
        print(out[-3000:])
    if err[-2000:]:
        print("STDERR:", err[-2000:])
    print(f"(rc={rc})\n")
    return rc, out, err


def main():
    c = conn()
    proj = f"/home/ubuntu/{DEPLOY_ID}"
    # 复制最新文件到 admin 容器
    run(c, f"docker cp {proj}/admin-web/src/app/(admin)/home-safety/page.tsx {DEPLOY_ID}-admin:/app/src/app/(admin)/home-safety/page.tsx")
    # admin 容器是 Next.js standalone 或 dev 模式？先看是否需要重新构建
    run(c, f"docker exec {DEPLOY_ID}-admin ls /app/.next/standalone 2>&1 | head -5 || true")
    # 检查启动命令
    run(c, f"docker inspect {DEPLOY_ID}-admin --format '{{{{.Config.Cmd}}}} {{{{.Config.Entrypoint}}}}'")
    # 简单做法：在容器内 rebuild
    rc, out, _ = run(
        c,
        f"docker exec {DEPLOY_ID}-admin bash -lc "
        f"'cd /app && (npm run build 2>&1 || yarn build 2>&1) | tail -40'",
        timeout=900,
    )
    # 重启
    run(c, f"docker restart {DEPLOY_ID}-admin")
    import time
    time.sleep(8)
    run(c, f"docker ps --filter name={DEPLOY_ID}-admin --format '{{{{.Status}}}}'")
    # 验证 URL
    base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    run(c, f"curl -sk -o /dev/null -w 'admin-home %{{http_code}}\\n' '{base_url}/admin/home-safety'")
    run(c, f"curl -sk -o /dev/null -w 'admin-login %{{http_code}}\\n' '{base_url}/admin/login'")


if __name__ == "__main__":
    main()
