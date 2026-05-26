"""通过容器内 chunks 文件验证 i-guard 新版关键词"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"

CMDS = [
    # 在 H5 容器内查 i-guard 相关 chunk 文件
    f"docker exec {TOKEN}-h5 sh -c 'ls /app/.next/static/chunks/app/health-profile/i-guard/ 2>/dev/null'",
    f"docker exec {TOKEN}-h5 sh -c 'ls /app/.next/static/chunks/app/health-profile/ 2>/dev/null'",
    f"docker exec {TOKEN}-h5 sh -c 'find /app/.next -name \"*.js\" | head -10'",
    # 全文搜「待确认转让」
    f"docker exec {TOKEN}-h5 sh -c 'grep -rl \"待确认转让\" /app/.next 2>/dev/null | head -5'",
    f"docker exec {TOKEN}-h5 sh -c 'grep -rl \"体验全新\" /app/.next 2>/dev/null | head -5; echo END'",
    # 看 server.js render 后看 server/app/health-profile/i-guard.html
    f"docker exec {TOKEN}-h5 sh -c 'grep -c \"待确认转让\" /app/.next/server/app/health-profile/i-guard.html 2>/dev/null; echo ---; grep -c \"体验全新\" /app/.next/server/app/health-profile/i-guard.html 2>/dev/null'",
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    for c in CMDS:
        print("\n==== CMD:", c[:200])
        si, so, se = cli.exec_command(c, timeout=30)
        out = so.read().decode("utf-8", errors="ignore")
        err = se.read().decode("utf-8", errors="ignore")
        if out.strip():
            print(out)
        if err.strip():
            print("--stderr--")
            print(err)
    cli.close()


if __name__ == "__main__":
    main()
