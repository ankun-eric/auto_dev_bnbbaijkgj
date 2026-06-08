import paramiko, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30, banner_timeout=30)

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

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

print("=" * 60)
print("1. Docker 容器列表")
print("=" * 60)
run("docker ps --format '{{.Names}} | {{.Status}} | {{.Ports}}' 2>&1")

print("\n" + "=" * 60)
print("2. Backend 容器的 DATABASE_URL")
print("=" * 60)
run(f"docker exec {DEPLOY_ID}-backend env 2>&1 | grep -i database\|mysql\|db")

print("\n" + "=" * 60)
print("3. Backend 容器内直接获取 DATABASE_URL")
print("=" * 60)
run(f"docker exec {DEPLOY_ID}-backend python3 -c \"import os; print(os.environ.get('DATABASE_URL','NOT SET'))\" 2>&1")

print("\n" + "=" * 60)
print("4. 检查是否有独立 MySQL 容器")
print("=" * 60)
run("docker ps -a --format '{{.Names}} {{.Status}}' 2>&1 | grep -i mysql\|db\|mariadb")

print("\n" + "=" * 60)
print("5. docker-compose 中的 DB 配置")
print("=" * 60)
run(f"cat /home/ubuntu/{DEPLOY_ID}/deploy/docker-compose.prod.yml 2>&1 | grep -A15 '  db:' | head -20")

ssh.close()
print("\nDone!")
