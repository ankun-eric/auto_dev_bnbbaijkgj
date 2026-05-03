"""Inspect gateway nginx config to figure out how to expose the zip."""
import paramiko, time

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30, allow_agent=False, look_for_keys=False)


def run(cmd):
    si, so, se = cli.exec_command(cmd, timeout=60)
    out = so.read().decode("utf-8", errors="replace")
    err = se.read().decode("utf-8", errors="replace")
    return so.channel.recv_exit_status(), out, err


for cmd in [
    "ls /home/ubuntu/gateway/",
    "ls /home/ubuntu/gateway/conf.d/",
    "ls /home/ubuntu/gateway/conf.d/gateway-routes/",
    "cat /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf",
    "echo '------apk------'",
    "cat /home/ubuntu/gateway/conf.d/gateway-routes/6b099ed3-7175-4a78-91f4-44570c84ed27-apk.conf",
    "echo '------docker compose for gateway------'",
    "ls /home/ubuntu/gateway/",
    "cat /home/ubuntu/gateway/docker-compose.yml 2>/dev/null || cat /home/ubuntu/gateway/docker-compose.yaml 2>/dev/null",
    "echo '------docker ps gateway------'",
    "docker inspect gateway 2>/dev/null | grep -E '(Source|Destination|Mounts)' | head -40",
]:
    rc, out, err = run(cmd)
    print(f"\n$ {cmd}")
    print(out)
    if err.strip():
        print("STDERR:", err)

cli.close()
