"""[PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 补传后端业务代码（reverse_guardian / schemas / models / schema_sync）。"""
import sys
import os
import paramiko
sys.path.insert(0, ".")
from deploy._sshlib import HOST, USER, PASSWORD, run  # noqa

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
CONT = f"{DEPLOY_ID}-backend"

LOCAL_FILES = [
    ("backend/app/api/reverse_guardian.py",
     f"{PROJ}/backend/app/api/reverse_guardian.py"),
    ("backend/app/schemas/reverse_guardian.py",
     f"{PROJ}/backend/app/schemas/reverse_guardian.py"),
    ("backend/app/models/models.py",
     f"{PROJ}/backend/app/models/models.py"),
    ("backend/app/services/schema_sync.py",
     f"{PROJ}/backend/app/services/schema_sync.py"),
]


def upload(local, remote):
    print(f"upload {local} -> {remote}")
    t = paramiko.Transport((HOST, 22))
    t.connect(username=USER, password=PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(t)
    try:
        sftp.put(local, remote)
        print(f"  ok, size = {os.path.getsize(local)}")
    finally:
        sftp.close()
        t.close()


def step(title, cmd, timeout=900):
    print(f"\n===== {title} =====", flush=True)
    code, out, err = run(cmd, timeout=timeout)
    if out:
        print(out[-3000:])
    if err:
        print("--- STDERR ---")
        print(err[-1500:])
    print(f"[exit={code}]", flush=True)
    return code, out, err


print("===== 0. 上传后端业务文件 =====", flush=True)
for local, remote in LOCAL_FILES:
    upload(local, remote)

# 同时 docker cp 进 backend 容器（因为该项目 backend image 是 COPY 进来的，
# 直接 cp 比 rebuild 更快）
step("1. docker cp 业务文件入容器",
     " && ".join(
         f"docker cp {PROJ}/backend/{p} {CONT}:/app/{p}"
         for p in [
             "app/api/reverse_guardian.py",
             "app/schemas/reverse_guardian.py",
             "app/models/models.py",
             "app/services/schema_sync.py",
         ]
     ),
     timeout=60)

# 同步 cp 测试文件（防止下次 rebuild 丢失）
step("1b. docker cp 测试文件入容器",
     f"docker cp {PROJ}/backend/tests/test_guardian_card_optim_v1_20260602.py {CONT}:/app/tests/test_guardian_card_optim_v1_20260602.py",
     timeout=60)

step("2. 重启 backend（含 schema_sync）",
     f"docker compose -f {PROJ}/docker-compose.yml restart backend 2>&1 | tail -5",
     timeout=120)

step("3. 等待 backend 启动完成",
     f"sleep 12 && docker logs --tail 25 {CONT} 2>&1 | tail -25",
     timeout=60)

step("4. 验证 reverse_guardian 已含 guardian_name",
     f"docker exec {CONT} grep -c 'guardian_name' /app/app/api/reverse_guardian.py",
     timeout=30)

print("\n===== 后端补丁部署完成 =====", flush=True)
