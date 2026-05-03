"""Deep probe: figure out exact serving path. Use ssh to grep nginx config 
for routes referencing miniprogram_*.zip or any catch-all."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd: str) -> str:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[:5000])
    if err:
        print("[stderr]", err[:500])
    return out


run(f"docker exec gateway cat /etc/nginx/conf.d/routes/{UUID}.conf")
run(f"docker exec gateway find / -path /proc -prune -o -name 'miniprogram_20260503_212049_9128.zip' -print 2>/dev/null | head -10")
run(f"docker exec gateway sh -c 'ls -la /var/www/autodev/{UUID}/ 2>/dev/null'")
run(f"docker inspect gateway --format '{{{{json .Mounts}}}}'")

ssh.close()
