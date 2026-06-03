"""重建 backend 容器并验证代码已上线"""
import paramiko
import time

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{DEPLOY_ID}'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd, timeout=600):
    print(f">>> {cmd[:180]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-2500:])
    if err:
        print(f"STDERR: {err[-1500:]}")
    print(f"[exit={code}]")
    return out, err, code


# 重建 backend 容器（image 含最新代码）
run(f'cd {PROJECT_DIR} && docker compose build backend 2>&1 | tail -20', timeout=900)
run(f'cd {PROJECT_DIR} && docker compose up -d backend 2>&1 | tail -10')

print("\n等待 backend 启动...")
for i in range(30):
    out, _, _ = run(f'docker logs --tail 3 {DEPLOY_ID}-backend 2>&1 | tail -3')
    if 'Application startup complete' in out or 'Uvicorn running' in out:
        break
    time.sleep(3)

# 验证 BUGFIX 标记
print("\n=== 验证 BUGFIX 标记 ===")
run(f'docker exec {DEPLOY_ID}-backend grep -c "BUGFIX-MY-GUARDIAN-CARD-2-20260528" /app/app/api/guardian_system_v13.py')

# 健康检查
print("\n=== 健康检查 ===")
run(f'curl -s -o /dev/null -w "%{{http_code}}\\n" http://localhost/autodev/{DEPLOY_ID}/api/guardian/v13/family/list')
run(f'curl -s -o /dev/null -w "%{{http_code}}\\n" http://localhost/autodev/{DEPLOY_ID}/health-profile/i-guard')
run(f'curl -sk -o /dev/null -w "%{{http_code}}\\n" https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile/i-guard')

# 再跑一次测试
print("\n=== 重跑测试 ===")
out, _, code = run(
    f'docker exec {DEPLOY_ID}-backend bash -lc "cd /app && python -m pytest tests/test_my_guardian_card_bugfix2_20260528.py -v --tb=short 2>&1 | tail -15"',
    timeout=300,
)

ssh.close()
