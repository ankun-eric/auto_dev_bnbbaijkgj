"""SSH 现场勘查：落实 H5/admin/gateway 容器信息（Bug 修复方案 - 阶段 0）"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"

CMDS = [
    "docker ps --format 'table {{.Names}}\\t{{.Image}}\\t{{.Ports}}\\t{{.Status}}'",
    "docker network ls",
    "docker ps --format '{{.Names}}' | grep -i " + TOKEN + " || true",
    "for c in $(docker ps -q --filter name=" + TOKEN + "); do "
    "  docker inspect -f '{{.Name}} | image={{.Config.Image}} | networks={{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}| ports={{range $p,$b := .HostConfig.PortBindings}}{{$p}}->{{(index $b 0).HostPort}} {{end}}' $c; "
    "done",
    "ls -la /home/ubuntu/projects/" + TOKEN + "/ 2>/dev/null || true",
    "find /home/ubuntu -maxdepth 4 -name 'docker-compose*.yml' 2>/dev/null | head -10",
    "find /home/ubuntu -maxdepth 5 -name 'Dockerfile' 2>/dev/null | grep -i " + TOKEN + " | head -20",
    "docker ps -a | grep -i gateway || true",
    "ls /home/ubuntu/projects/ 2>/dev/null | head -10",
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    for c in CMDS:
        print("\n==== CMD:", c[:160], ("..." if len(c) > 160 else ""))
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
