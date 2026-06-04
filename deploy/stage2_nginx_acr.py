import paramiko

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"

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

# First login to ACR
print("=== Login ACR ===")
run(f"sudo docker login --username=ankun888 --password=xiaobai888 {ACR}")

# Try ACR base namespace
print("\n=== Try ACR noob_doker_base ===")
out, err, code = run(f"sudo docker pull {ACR}/noob_doker_base/nginx:alpine 2>&1", timeout=120)
if code == 0:
    run(f"sudo docker tag {ACR}/noob_doker_base/nginx:alpine nginx:alpine")
    print("Pulled from ACR base!")
else:
    # Try pulling from test env server
    print("\n=== Try direct pull with different mirror ===")
    # Configure a working mirror
    daemon = '{"registry-mirrors": ["https://docker.m.daocloud.io", "https://dockerproxy.com"],"log-driver":"json-file","log-opts":{"max-size":"10m","max-file":"3"}}'
    escaped = daemon.replace('"', '\\"')
    run(f"echo '{escaped}' | sudo tee /etc/docker/daemon.json")
    run("sudo systemctl restart docker")
    import time
    time.sleep(3)
    
    out, err, code = run("sudo docker pull nginx:alpine 2>&1", timeout=120)
    if code == 0:
        print("Pulled nginx:alpine successfully!")
    else:
        # Last resort: pull from test env and push to ACR
        print("All direct pulls failed. Need to get nginx from test env...")

client.close()
