import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def run_ssh(host, port, username, password, command, timeout=30):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=username, password=password, timeout=15)
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    exit_code = stdout.channel.recv_exit_status()
    client.close()
    return out, err, exit_code

print("=== 容器状态 ===")
out, err, code = run_ssh(HOST, PORT, USER, PASS,
    f"docker ps -a --filter 'name={DEPLOY_ID}-' --format '{{{{.Names}}}}\t{{{{.Image}}}}\t{{{{.Status}}}}'")
print(out)

print("\n=== 镜像列表 ===")
out, err, code = run_ssh(HOST, PORT, USER, PASS,
    f"docker images --filter 'reference=*{DEPLOY_ID}*' --format '{{{{.Repository}}}}:{{{{.Tag}}}}\t{{{{.Size}}}}'")
print(out)

print("\n=== Docker网络 ===")
out, err, code = run_ssh(HOST, PORT, USER, PASS,
    f"docker network ls --filter 'name={DEPLOY_ID}-' --format '{{{{.Name}}}}'")
print(out)

print("\n=== Gateway配置 ===")
out, err, code = run_ssh(HOST, PORT, USER, PASS,
    f"cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf")
print(out)
