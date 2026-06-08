"""SSH to server and update git code."""
import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

def run(ssh, cmd, timeout=120):
    print(f"\n>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    ec = stdout.channel.recv_exit_status()
    if out:
        print(out[:3000])
    if err:
        print("ERR:", err[:500])
    print(f"RC={ec}")
    return ec, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print(f"Connecting to {HOST}...")
ssh.connect(HOST, PORT, USER, PASSWORD, timeout=30)
print("Connected!")

# Test
run(ssh, "hostname")
run(ssh, "pwd")
run(ssh, f"ls -la {PROJECT_DIR}/.git")

# Git update
run(ssh, f"cd {PROJECT_DIR} && git fetch --depth 1 origin master", timeout=180)
run(ssh, f"cd {PROJECT_DIR} && git reset --hard origin/master", timeout=60)
run(ssh, f"cd {PROJECT_DIR} && git log --oneline -3")

ssh.close()
print("Done!")
