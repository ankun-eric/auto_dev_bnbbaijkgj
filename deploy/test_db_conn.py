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
        print(out.strip()[:2000])
    if err.strip():
        print('[STDERR]')
        print(err.strip()[:1000])
    sys.stdout.flush()
    return out, err

# Test with correct password xiaokang989aab
print("=" * 60)
print("1. 测试正确密码连接")
print("=" * 60)
run("timeout 10 mysql -h gz-cdb-nniq1lmp.sql.tencentcdb.com -P 27082 -u root -pxiaokang989aab -e 'SELECT 1 AS test, VERSION() AS ver' 2>&1")

print("\n" + "=" * 60)
print("2. 列出所有数据库")
print("=" * 60)
run("timeout 10 mysql -h gz-cdb-nniq1lmp.sql.tencentcdb.com -P 27082 -u root -pxiaokang989aab -e 'SHOW DATABASES' 2>&1")

ssh.close()
print("\nDone!")
