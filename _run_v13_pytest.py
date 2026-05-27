"""在远程运行 v13 后端测试"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

_, o, e = c.exec_command(
    f"cd {REMOTE_BASE} && docker compose exec -T backend "
    f"python -m pytest tests/test_guardian_system_v13.py -v 2>&1 | tail -120",
    timeout=300,
)
rc = o.channel.recv_exit_status()
print(o.read().decode("utf-8", "replace"))
er = e.read().decode("utf-8", "replace")
if er.strip():
    print("[stderr]", er)
print(f"\n[exit={rc}]")
c.close()
