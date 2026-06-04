"""快速重传 + 重跑测试"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BE = f"{DEPLOY_ID}-backend"
PD = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    ("backend/app/api/guardian_system_v13.py",
     f"{PD}/backend/app/api/guardian_system_v13.py",
     "/app/app/api/guardian_system_v13.py"),
    ("backend/tests/test_guardian_bugfix_v1_20260529.py",
     f"{PD}/backend/tests/test_guardian_bugfix_v1_20260529.py",
     "/app/tests/test_guardian_bugfix_v1_20260529.py"),
]

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=60,
            look_for_keys=False, allow_agent=False)

sftp = cli.open_sftp()
for local, host, container in FILES:
    print(f"upload {local}")
    sftp.put(local, host)
sftp.close()

def run(cmd, timeout=300):
    print(f"\n$ {cmd[:200]}")
    _, stdout, _ = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    print(out[-6000:])
    print(f"[rc={rc}]")
    return rc

for local, host, container in FILES:
    run(f"docker cp {host} {BE}:{container}")

run(f"docker restart {BE}")
import time; time.sleep(8)

run(f"docker exec {BE} sh -c 'cd /app && python -m pytest "
    f"tests/test_guardian_bugfix_v1_20260529.py -v --tb=short --no-header -W ignore 2>&1 | tail -50'",
    timeout=600)
cli.close()
