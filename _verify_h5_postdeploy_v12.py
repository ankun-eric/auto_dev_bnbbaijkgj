"""部署后立刻验证 H5：i-guard 页面已是新版"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{TOKEN}"

CMDS = [
    f"docker ps --format '{{{{.Names}}}} {{{{.Status}}}} {{{{.Image}}}}' | grep -E '{TOKEN}-(h5|admin|backend)'",
    f"curl -k -L -s -o /tmp/_iguard.html -w 'iguard_status=%{{http_code}}\\n' {BASE}/health-profile/i-guard",
    f"wc -l /tmp/_iguard.html",
    f"grep -c '待确认转让' /tmp/_iguard.html || true",
    f"grep -c '体验全新' /tmp/_iguard.html || true",
    f"grep -o '守护中\\|待守护' /tmp/_iguard.html | sort -u || true",
    # 进一步通过 mobile UA 看 / SSR 输出
    f"curl -k -L -s -H 'User-Agent: Mozilla/5.0 (iPhone)' -o /tmp/_root.html -w 'root_status=%{{http_code}}\\n' {BASE}/",
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
