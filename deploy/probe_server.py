"""Probe server for noob-deploy stage 1.5 details."""
import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def run_cmd(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd[:80]}")
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(f"EXIT: {exit_status}")
    if out:
        print(out[:1500])
    if err:
        print("STDERR:", err[:500])
    return out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=15)
print("Connected to", HOST)

run_cmd(ssh, "hostname")
run_cmd(ssh, "docker ps --filter name=gateway-nginx --format '{{.Names}} {{.Status}}'")
run_cmd(ssh, "docker exec gateway-nginx grep -n 'include.*conf' /etc/nginx/nginx.conf")
run_cmd(ssh, "docker exec gateway-nginx cat /etc/nginx/conf.d/" + DEPLOY_ID + ".server")
run_cmd(ssh, "docker exec gateway-nginx ls /etc/nginx/ssl/")
run_cmd(ssh, "docker ps -a --filter name=" + DEPLOY_ID)

ssh.close()
print("\nDONE")
