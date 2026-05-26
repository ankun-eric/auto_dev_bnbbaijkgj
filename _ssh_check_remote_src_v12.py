"""检查远程 h5-web/admin-web 的关键源码状态是否已是新版"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ROOT = f"/home/ubuntu/{TOKEN}"

CMDS = [
    f"ls -la {ROOT}/h5-web/src/app/health-profile/",
    f"ls -la {ROOT}/h5-web/src/app/health-profile/i-guard/ 2>/dev/null",
    f"ls -la {ROOT}/h5-web/src/app/guardian-system/ 2>/dev/null || echo 'NO guardian-system'",
    f"ls -la {ROOT}/h5-web/src/app/health-profile/v13/ 2>/dev/null || echo 'NO v13'",
    f"grep -c '体验全新' {ROOT}/h5-web/src/app/health-profile/i-guard/page.tsx 2>/dev/null || echo 'i-guard NO file'",
    f"grep -c '待确认转让' {ROOT}/h5-web/src/app/health-profile/i-guard/page.tsx 2>/dev/null",
    f"cd {ROOT} && git log --oneline -5 2>/dev/null",
    f"cd {ROOT} && git status --short 2>/dev/null | head -20",
    f"cat {ROOT}/h5-web/Dockerfile",
    f"cat {ROOT}/admin-web/Dockerfile",
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    for c in CMDS:
        print("\n==== CMD:", c[:160])
        si, so, se = cli.exec_command(c, timeout=60)
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
