import paramiko

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=30):
    print(f"  CMD: {cmd[:140]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out:
        print(f"  OUT: {out[:500]}")
    if err and len(err) > 5:
        print(f"  ERR: {err[:300]}")
    return out, err, code

# Check acme.sh exists
print("=== 检查 acme.sh ===")
run("ls -la ~/.acme.sh/acme.sh 2>&1")

# Check if already installed
run("~/.acme.sh/acme.sh --version 2>&1")

# Check certificate list
print("\n=== 证书列表 ===")
run("~/.acme.sh/acme.sh --list 2>&1")

# Check SSL dir
print("\n=== SSL目录 ===")
run("ls -la /home/ubuntu/gateway/ssl/")

# Check crontab
print("\n=== Crontab ===")
run("crontab -l 2>/dev/null | head -5 || echo 'no crontab'")

client.close()
