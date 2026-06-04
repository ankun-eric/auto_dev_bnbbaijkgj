import paramiko
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=20, look_for_keys=False, allow_agent=False)

def r(cmd, sudo=False):
    full = cmd
    if sudo:
        full = "echo 'Newbang888' | sudo -S bash -lc \"" + cmd.replace('"', '\\"') + "\""
    _, o, e = cli.exec_command(full, timeout=60)
    print("$", cmd)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err.strip():
        print("[err]", err[:500])
    print("---")

r("ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram/ 2>&1 | head -20")
r("docker ps --format '{{.Names}}' | head -20", sudo=True)
r("docker ps --format '{{.Names}}' | grep -i nginx", sudo=True)
r("docker ps --format '{{.Names}}' | grep -i gateway", sudo=True)
# nginx 容器配置
r("docker exec autodev-gateway-nginx cat /etc/nginx/conf.d/default.conf 2>&1 | head -100 || true", sudo=True)

# look at file mount paths in docker-compose
r("cat /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.yml | head -120")
cli.close()
