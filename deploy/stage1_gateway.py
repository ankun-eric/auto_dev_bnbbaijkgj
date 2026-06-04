import paramiko

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

print("=== gateway config ===")
cmd = f"cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf 2>/dev/null || echo 'FILE_NOT_FOUND'"
out, err, code = run_ssh(HOST, PORT, USER, PASS, cmd)
print(out)
if err:
    print(f"[stderr] {err}")

print("\n=== docker-compose.prod.yml ===")
cmd = f"cat /home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml"
out, err, code = run_ssh(HOST, PORT, USER, PASS, cmd)
print(out)
if err:
    print(f"[stderr] {err}")

print("\n=== gateway-routes.conf ===")
cmd = f"cat /home/ubuntu/{DEPLOY_ID}/gateway-routes.conf"
out, err, code = run_ssh(HOST, PORT, USER, PASS, cmd)
print(out)
if err:
    print(f"[stderr] {err}")
