"""[PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] 部署后重跑 pytest 验证"""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PASS, timeout=30,
            look_for_keys=False, allow_agent=False)

def run(cmd, sudo=False, t=300):
    full = cmd
    if sudo:
        full = f"echo '{PASS}' | sudo -S bash -lc '{cmd}'"
    _, sout, serr = cli.exec_command(full, timeout=t)
    out = sout.read().decode(errors='replace')
    err = serr.read().decode(errors='replace')
    rc = sout.channel.recv_exit_status()
    print(out[-4000:])
    if err.strip():
        print("[stderr]", err[-1500:])
    return rc

be = f"{DEPLOY_ID}-backend"
# 先复制最新文件（rebuild 后镜像内可能是旧版）
proj = f"/home/ubuntu/{DEPLOY_ID}"
files = [
    "app/api/member_center_v2.py",
    "app/models/membership_plan.py",
    "app/schemas/membership.py",
]
for f in files:
    run(f"docker cp {proj}/backend/{f} {be}:/app/{f}", sudo=True)
run(f"docker cp {proj}/backend/tests/test_health_archive_mgr_v1_20260529.py {be}:/app/tests/test_health_archive_mgr_v1_20260529.py", sudo=True)
run(f"docker restart {be}", sudo=True)

import time
print("waiting backend ready ...")
for i in range(40):
    rc = run(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost/autodev/{DEPLOY_ID}/api/health || true", sudo=True, t=10)
    time.sleep(1)
    if i > 5:
        break

# 跑 pytest（包含本次新增 + 既有相关测试）
rc = run(
    f"docker exec {be} python -m pytest "
    f"tests/test_health_archive_mgr_v1_20260529.py "
    f"tests/test_member_center_prd_v1_aligned.py "
    f"-v --tb=short",
    sudo=True, t=300
)
print(f"\npytest exit_code={rc}")
cli.close()
sys.exit(rc)
