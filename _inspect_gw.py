import paramiko
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=20, look_for_keys=False, allow_agent=False)

def r(cmd, sudo=False):
    full = cmd
    if sudo:
        full = "echo 'Newbang888' | sudo -S bash -lc \"" + cmd.replace('"', '\\"') + "\""
    _, o, e = cli.exec_command(full, timeout=60)
    print("$", cmd[:200])
    print(o.read().decode(errors='replace')[:5000])
    err = e.read().decode(errors='replace')
    if err.strip() and "sudo" not in err[:50]:
        print("[err]", err[:500])
    print("---")

r("docker exec gateway-nginx ls /etc/nginx/conf.d/", sudo=True)
r("docker exec gateway-nginx cat /etc/nginx/nginx.conf | head -120", sudo=True)
r("docker exec gateway-nginx cat /etc/nginx/conf.d/default.conf | head -200", sudo=True)
r("docker exec gateway-nginx ls /etc/nginx/conf.d/autodev/ 2>/dev/null | head -30", sudo=True)
r("docker exec gateway-nginx find /etc/nginx -name '*6b099ed3*' 2>/dev/null", sudo=True)
r("docker inspect gateway-nginx --format '{{json .Mounts}}'", sudo=True)
cli.close()
