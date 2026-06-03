"""[PRD-HEALTH-METRIC-CARD-UNIFY-V1] 在远程后端容器执行单元测试。"""
import paramiko
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
PROJECT = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

cmd = f"""BC=$(docker ps -qf 'name=6b099ed3.*backend')
docker cp {PROJECT}/backend/tests/test_health_metric_card_unify_v1_20260531.py $BC:/app/tests/test_health_metric_card_unify_v1_20260531.py
docker exec $BC sh -c "cd /app && pip install pytest pytest-asyncio aiosqlite httpx -q 2>&1 | tail -3 && python -m pytest tests/test_health_metric_card_unify_v1_20260531.py -q --no-header 2>&1 | tail -25"
"""
stdin, stdout, stderr = cli.exec_command(cmd, timeout=300)
print(stdout.read().decode('utf-8', 'replace'))
e = stderr.read().decode('utf-8', 'replace')
if e.strip(): print("STDERR:", e[-1000:])
cli.close()
