"""SSH 现场勘查 2：gateway nginx 配置 & 容器内部端口 & Dockerfile 内容"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"

CMDS = [
    # gateway 容器内 nginx 配置
    "docker exec gateway sh -c 'ls /etc/nginx/conf.d/ 2>/dev/null; ls /etc/nginx/sites-enabled/ 2>/dev/null'",
    "docker exec gateway sh -c 'cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -200'",
    "docker exec gateway sh -c \"grep -rln '" + TOKEN + "' /etc/nginx/ 2>/dev/null\"",
    "docker exec gateway sh -c \"grep -A 60 '" + TOKEN + "' /etc/nginx/nginx.conf 2>/dev/null | head -120\"",
    # H5 容器内部
    "docker exec " + TOKEN + "-h5 sh -c 'ls; cat package.json 2>/dev/null | head -40'",
    "docker exec " + TOKEN + "-h5 sh -c 'ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null'",
    # admin 容器内部
    "docker exec " + TOKEN + "-admin sh -c 'ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null'",
    # 项目目录
    "ls -la /home/ubuntu/" + TOKEN + "/",
    "cat /home/ubuntu/" + TOKEN + "/docker-compose.yml 2>/dev/null | head -120",
    "cat /home/ubuntu/" + TOKEN + "/h5-web/Dockerfile 2>/dev/null | head -60",
    "cat /home/ubuntu/" + TOKEN + "/admin-web/Dockerfile 2>/dev/null | head -60",
    # gateway 容器宿主端口与路径映射  
    "docker exec gateway sh -c \"nginx -T 2>/dev/null | grep -B1 -A3 '" + TOKEN + "' | head -120\"",
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
