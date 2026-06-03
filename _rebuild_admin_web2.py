"""重建管理后台前端：在 admin 容器内（用 sh，不用 bash）rebuild Next.js。"""
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


def run(c, cmd, timeout=1200):
    print(f"$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out[-4000:]:
        print(out[-4000:])
    if err[-2000:]:
        print("STDERR:", err[-2000:])
    print(f"(rc={rc})\n")
    return rc, out, err


def main():
    c = conn()
    proj = f"/home/ubuntu/{DEPLOY_ID}"

    # 转义 docker cp 中的括号
    src = f"{proj}/admin-web/src/app/\\(admin\\)/home-safety/page.tsx"
    dst = f"{DEPLOY_ID}-admin:/app/src/app/\\(admin\\)/home-safety/page.tsx"
    # docker cp 不支持 shell globbing；尝试用引号路径
    run(c, f"""docker cp "{proj}/admin-web/src/app/(admin)/home-safety/page.tsx" "{DEPLOY_ID}-admin:/app/src/app/(admin)/home-safety/page.tsx" """)

    # 检查容器内可用的 shell
    run(c, f"docker exec {DEPLOY_ID}-admin sh -c 'which sh node npm npx; ls /app | head -30'")

    # 检查 Next.js 项目结构（standalone 模式只会有 .next/standalone）
    run(c, f"docker exec {DEPLOY_ID}-admin sh -c 'ls /app/.next 2>&1 | head -20; echo ---; ls /app/server.js 2>&1'")

    # 容器内 rebuild
    print("=== rebuild ===")
    rc, out, _ = run(
        c,
        f"docker exec {DEPLOY_ID}-admin sh -c 'cd /app && npm run build 2>&1 | tail -40'",
        timeout=1200,
    )

    # standalone 模式：build 后需要把 src 文件复制到 standalone 输出
    # 但通常 standalone 直接读取打包后的 .next/server.js，所以 rebuild 后会自动用
    print("=== check server file ===")
    run(c, f"docker exec {DEPLOY_ID}-admin sh -c 'ls -la /app/.next/standalone 2>&1 | head; ls /app/.next/server 2>&1 | head'")

    # 重启
    run(c, f"docker restart {DEPLOY_ID}-admin")
    time.sleep(10)
    run(c, f"docker logs --tail 30 {DEPLOY_ID}-admin 2>&1 | tail -30")


if __name__ == "__main__":
    main()
