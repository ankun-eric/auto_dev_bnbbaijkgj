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

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

print("=" * 60)
print("1. Backend 容器的 DATABASE_URL 环境变量")
print("=" * 60)
run(f"docker exec {DEPLOY_ID}-backend env | grep -i database\|mysql\|db 2>&1")

print("\n" + "=" * 60)
print("2. 从 backend 容器内测试数据库连接")
print("=" * 60)
run(f"docker exec {DEPLOY_ID}-backend python3 -c \"import os; print(os.environ.get('DATABASE_URL','NOT SET')[:150])\" 2>&1")

print("\n" + "=" * 60)
print("3. 检查 docker-compose 文件")
print("=" * 60)
run(f"ls -la /home/ubuntu/{DEPLOY_ID}/deploy/docker-compose.prod.yml 2>&1")
run(f"grep -A2 DATABASE_URL /home/ubuntu/{DEPLOY_ID}/deploy/docker-compose.prod.yml 2>&1")

print("\n" + "=" * 60)
print("4. 检查所有 Docker 网络和 MySQL 相关")
print("=" * 60)
run("docker network ls 2>&1")
run("docker ps -a --format '{{.Names}} {{.Status}}' 2>&1 | grep -i mysql\|db")

print("\n" + "=" * 60)
print("5. 尝试从宿主机直连腾讯云 CDB")
print("=" * 60)
run("which mysql 2>&1")
run("timeout 5 mysql -h gz-cdb-nniq1lmp.sql.tencentcdb.com -P 27082 -u root -pxiaokangaab -e 'SELECT 1' 2>&1 || echo 'TIMEOUT_OR_FAIL'")

print("\n" + "=" * 60)
print("6. 检查 DNS 解析")
print("=" * 60)
run("nslookup gz-cdb-nniq1lmp.sql.tencentcdb.com 2>&1 || host gz-cdb-nniq1lmp.sql.tencentcdb.com 2>&1")

ssh.close()
print("\nDone!")
