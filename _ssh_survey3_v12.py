"""SSH 现场勘查 3：nginx 配置内容 + gateway 网络成员"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"

CMDS = [
    "docker exec gateway cat /etc/nginx/conf.d/" + TOKEN + ".conf",
    "docker network inspect gateway-network --format '{{range .Containers}}{{.Name}}\\n{{end}}'",
    "docker network inspect " + TOKEN + "-network --format '{{range .Containers}}{{.Name}}\\n{{end}}'",
    # gateway connect to project network?
    "docker inspect gateway --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'",
    "ls /home/ubuntu/" + TOKEN + "/docker-compose.yml /home/ubuntu/" + TOKEN + "/docker-compose.prod.yml 2>/dev/null",
    "ls /home/ubuntu/" + TOKEN + "/deploy/ 2>/dev/null | grep -iE 'compose|deploy_msg' | head -10",
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
