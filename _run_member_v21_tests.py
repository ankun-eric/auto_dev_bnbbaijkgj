"""Run the new test_home_safety_member_v21.py inside the backend container."""
import paramiko
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST="newbb.test.bangbangvip.com"
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username='ubuntu',password='Newbang888',timeout=60)

print("=== Run new tests ===")
si,so,se=c.exec_command(
    f"docker exec {DEPLOY_ID}-backend python -m pytest tests/test_home_safety_member_v21.py -x -v --tb=short 2>&1 | tail -200",
    timeout=600,
)
print(so.read().decode("utf-8","replace"))
print(se.read().decode("utf-8","replace"))
print(f"exit={so.channel.recv_exit_status()}")
c.close()
