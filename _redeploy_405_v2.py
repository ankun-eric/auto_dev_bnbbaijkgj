import paramiko, os, time
LOCAL = os.path.dirname(os.path.abspath(__file__))
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT = f"/home/ubuntu/{DEPLOY}"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = ssh.open_sftp()

for p in ["backend/app/models/models.py", "backend/app/api/ai_home_config.py", "backend/app/schemas/ai_home_config.py"]:
    sftp.put(os.path.join(LOCAL, p), f"{PROJECT}/{p}")
    print("uploaded", p)
sftp.close()

def run(cmd, timeout=300):
    print(f"$ {cmd}", flush=True)
    _, out, _ = ssh.exec_command(cmd, timeout=timeout)
    print(out.read().decode("utf-8", "ignore"), flush=True)

backend = f"{DEPLOY}-backend"
run(f"docker cp {PROJECT}/backend/app/models/models.py {backend}:/app/app/models/models.py")
run(f"docker cp {PROJECT}/backend/app/api/ai_home_config.py {backend}:/app/app/api/ai_home_config.py")
run(f"docker cp {PROJECT}/backend/app/schemas/ai_home_config.py {backend}:/app/app/schemas/ai_home_config.py")
run(f"docker restart {backend}")
time.sleep(8)
run(f"docker exec {backend} python -m pytest tests/test_ai_home_config.py -v --tb=short 2>&1 | tail -50", timeout=300)
ssh.close()
print("DONE")
