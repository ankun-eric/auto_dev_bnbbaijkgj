import paramiko

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=120):
    print(f"CMD: {cmd[:120]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out:
        print(f"OUT: {out[:500]}")
    if err and len(err) > 5:
        print(f"ERR: {err[:500]}")
    return out, err, code

# Check daemon config
print("=== Check docker config ===")
out, err, code = run("sudo cat /etc/docker/daemon.json")
print(f"code={code}")

# Try to pull nginx:alpine directly with registry mirror
print("\n=== Pull nginx:alpine with full mirror path ===")
out, err, code = run("sudo docker pull nginx:alpine 2>&1", timeout=120)
if code != 0:
    print("Direct pull failed, trying mirror...")
    out, err, code = run("sudo docker pull registry.cn-hangzhou.aliyuncs.com/library/nginx:alpine 2>&1", timeout=120)
    if code == 0:
        run("sudo docker tag registry.cn-hangzhou.aliyuncs.com/library/nginx:alpine nginx:alpine")
        print("Tagged as nginx:alpine")

# Verify nginx image
print("\n=== Verify nginx image ===")
out, err, code = run("sudo docker images nginx:alpine --format '{{.Repository}}:{{.Tag}} {{.Size}}'")
print(out)

# Check docker info for registry mirrors
print("\n=== Docker registry mirrors ===")
out, err, code = run("sudo docker info 2>&1 | grep -A5 'Registry Mirrors'")
print(out)

client.close()
