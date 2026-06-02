"""[PRD-TA-GUARDIAN-CARD-V1 2026-06-02] 部署「健康档案 TA 守护人卡片」改造。

本次变更：
- 后端: backend/app/api/guardian_system_v12.py（all-guardians 接口新增 max_guardians 字段）
- 后端测试: backend/tests/test_ta_guardian_card_v1_20260602.py（新增）
- 前端 H5: h5-web/src/app/health-profile/page.tsx（点击修复 + 统计修正 + 标题修改）

流程：直接 SCP 上传变更文件到容器内 → 重启 backend → 重建 h5-web → reload gateway
"""
import sys
import os
import paramiko
sys.path.insert(0, ".")
from deploy._sshlib import HOST, USER, PASSWORD, run  # noqa

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
GW = "gateway-nginx"

LOCAL_FILES = [
    ("backend/app/api/guardian_system_v12.py", f"{PROJ}/backend/app/api/guardian_system_v12.py"),
    ("backend/tests/test_ta_guardian_card_v1_20260602.py", f"{PROJ}/backend/tests/test_ta_guardian_card_v1_20260602.py"),
    ("h5-web/src/app/health-profile/page.tsx", f"{PROJ}/h5-web/src/app/health-profile/page.tsx"),
]


def step(title, cmd, timeout=900):
    print(f"\n===== {title} =====")
    code, out, err = run(cmd, timeout=timeout)
    print(out[-4000:] if out else "")
    if err:
        print("--- STDERR ---")
        print(err[-2000:])
    print(f"[exit={code}]")
    return code, out, err


def upload(local, remote):
    print(f"upload {local} -> {remote}")
    t = paramiko.Transport((HOST, 22))
    t.connect(username=USER, password=PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(t)
    try:
        sftp.put(local, remote)
        print("  ok, size =", os.path.getsize(local))
    finally:
        sftp.close()
        t.close()


print("===== 0. 上传变更文件 =====")
for local, remote in LOCAL_FILES:
    upload(local, remote)

# 1. 重启 backend（python 代码改动，无需 rebuild image，volume 不挂源码所以需 docker cp）
# 实际项目 backend Dockerfile 是把源码 COPY 进镜像，因此需要 rebuild backend 才能生效。
step("1. 重建 backend 镜像", (
    f"cd {PROJ} && docker compose build --no-cache backend 2>&1 | tail -15"
), timeout=900)

step("2. 启动 backend", (
    f"cd {PROJ} && docker compose up -d backend 2>&1 | tail -10"
), timeout=180)

# 3. 重建 h5-web
step("3. 重建 h5-web 容器（--no-cache）", (
    f"cd {PROJ} && docker compose build --no-cache h5-web 2>&1 | tail -25"
), timeout=1800)

step("4. 启动 h5-web", (
    f"cd {PROJ} && docker compose up -d h5-web 2>&1 | tail -10"
), timeout=300)

# 5. 等待状态
step("5. 容器状态", (
    f"sleep 8 && docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}"
), timeout=60)

# 6. 重连 gateway
step("6. gateway 重连项目网络", (
    f"docker network connect {DEPLOY_ID}-network {GW} 2>/dev/null; "
    f"docker network inspect {DEPLOY_ID}-network --format "
    f"'{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'"
), timeout=60)

# 7. reload gateway
step("7. gateway reload", (
    f"docker exec {GW} nginx -t 2>&1 && docker exec {GW} nginx -s reload 2>&1 && echo RELOAD_OK"
), timeout=60)

print("\n部署脚本执行完毕。")
