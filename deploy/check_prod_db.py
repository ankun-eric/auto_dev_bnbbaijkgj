import paramiko, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('chat.benne-ai.com', port=22, username='ubuntu', password='Benne-ai@#', timeout=30, banner_timeout=30)

def run(cmd, timeout=30):
    print(f'\n[CMD] {cmd[:300]}')
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip():
        print('[STDOUT]')
        print(out.strip()[:3000])
    if err.strip():
        print('[STDERR]')
        print(err.strip()[:1000])
    sys.stdout.flush()
    return out, err

print("=" * 60)
print("1. 基础信息")
print("=" * 60)
run("whoami")
run("hostname")
run("uname -a")

print("\n" + "=" * 60)
print("2. Docker 容器列表")
print("=" * 60)
run("docker ps --format '{{.Names}} | {{.Status}} | {{.Ports}}' 2>&1")

print("\n" + "=" * 60)
print("3. MySQL 容器详情")
print("=" * 60)
run("docker ps --filter name=db --format '{{.Names}}' 2>&1")

ssh.close()
print("\nDone!")
