"""验证生产服务器上的 backend 代码是否包含本次 bugfix"""
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

# 验证容器内代码是否含本次的 BUGFIX-MY-GUARDIAN-CARD-2 标记
cmd = f'docker exec {DEPLOY_ID}-backend grep -c "BUGFIX-MY-GUARDIAN-CARD-2-20260528" /app/app/api/guardian_system_v13.py'
_, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
print(f"容器内 BUGFIX 标记行数: {out}")
print(f"stderr: {err}")

# 重跑测试确认仍通过
cmd2 = f'docker exec {DEPLOY_ID}-backend bash -lc "cd /app && python -m pytest tests/test_my_guardian_card_bugfix2_20260528.py -v --tb=short 2>&1 | tail -15"'
_, stdout, _ = ssh.exec_command(cmd2)
print(stdout.read().decode())

ssh.close()
