"""[PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 部署「守护卡片优化」改造。

变更：
- 后端测试: backend/tests/test_guardian_card_optim_v1_20260602.py（新增）
- H5 前端:
  - h5-web/src/app/family-guardian-list/[targetId]/page.tsx（统一二次确认文案）
  - h5-web/src/app/health-profile/my-guardians/page.tsx（解除确认文案 + 查看邀请码按钮）
  - h5-web/src/app/health-profile/my-guardians/invite/page.tsx（名字必填 + 升级提示 + 查看模式）
- 小程序:
  - miniprogram/pages/family-guardian-list/detail.js（统一文案）
  - miniprogram/pages/my-guardians/{index.js,index.wxml,index.wxss}（pending 列表 + 查看邀请码 + 文案）
  - miniprogram/pages/reverse-invite/{index.js,index.wxml,index.wxss}（关系+名字 + 升级提示 + 查看模式）

流程：上传源码 → rebuild backend & h5-web → 重启
"""
import sys
import os
import paramiko
sys.path.insert(0, ".")
from deploy._sshlib import HOST, USER, PASSWORD, run  # noqa

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_FILES = [
    # 后端：仅新增测试文件（业务代码本次未改）
    ("backend/tests/test_guardian_card_optim_v1_20260602.py",
     f"{PROJ}/backend/tests/test_guardian_card_optim_v1_20260602.py"),
    # H5
    ("h5-web/src/app/family-guardian-list/[targetId]/page.tsx",
     f"{PROJ}/h5-web/src/app/family-guardian-list/[targetId]/page.tsx"),
    ("h5-web/src/app/health-profile/my-guardians/page.tsx",
     f"{PROJ}/h5-web/src/app/health-profile/my-guardians/page.tsx"),
    ("h5-web/src/app/health-profile/my-guardians/invite/page.tsx",
     f"{PROJ}/h5-web/src/app/health-profile/my-guardians/invite/page.tsx"),
    # 小程序
    ("miniprogram/pages/family-guardian-list/detail.js",
     f"{PROJ}/miniprogram/pages/family-guardian-list/detail.js"),
    ("miniprogram/pages/my-guardians/index.js",
     f"{PROJ}/miniprogram/pages/my-guardians/index.js"),
    ("miniprogram/pages/my-guardians/index.wxml",
     f"{PROJ}/miniprogram/pages/my-guardians/index.wxml"),
    ("miniprogram/pages/my-guardians/index.wxss",
     f"{PROJ}/miniprogram/pages/my-guardians/index.wxss"),
    ("miniprogram/pages/reverse-invite/index.js",
     f"{PROJ}/miniprogram/pages/reverse-invite/index.js"),
    ("miniprogram/pages/reverse-invite/index.wxml",
     f"{PROJ}/miniprogram/pages/reverse-invite/index.wxml"),
    ("miniprogram/pages/reverse-invite/index.wxss",
     f"{PROJ}/miniprogram/pages/reverse-invite/index.wxss"),
]


def step(title, cmd, timeout=900):
    print(f"\n===== {title} =====", flush=True)
    code, out, err = run(cmd, timeout=timeout)
    if out:
        print(out[-4000:])
    if err:
        print("--- STDERR ---")
        print(err[-2000:])
    print(f"[exit={code}]", flush=True)
    return code, out, err


def upload(local, remote):
    print(f"upload {local} -> {remote}", flush=True)
    t = paramiko.Transport((HOST, 22))
    t.connect(username=USER, password=PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(t)
    try:
        # 确保远端目录存在
        rdir = remote.rsplit("/", 1)[0]
        run(f"mkdir -p '{rdir}'", timeout=30)
        sftp.put(local, remote)
        print(f"  ok, size = {os.path.getsize(local)}")
    finally:
        sftp.close()
        t.close()


print("===== 0. 上传变更文件 =====", flush=True)
for local, remote in LOCAL_FILES:
    upload(local, remote)

# 后端业务代码本次未改，但 schema 会自动同步 guardian_name 字段；只需重启 backend 即可
step("1. 重启 backend（让自动 schema_sync 跑一次）",
     f"cd {PROJ} && docker compose restart backend 2>&1 | tail -10",
     timeout=180)

step("2. 等待 backend 健康",
     f"sleep 10 && docker logs --tail 30 {DEPLOY_ID}-backend 2>&1 | tail -30",
     timeout=60)

# h5 next.js rebuild
step("3. 重建 h5-web（--no-cache）",
     f"cd {PROJ} && docker compose build --no-cache h5-web 2>&1 | tail -25",
     timeout=1800)

step("4. 启动 h5-web",
     f"cd {PROJ} && docker compose up -d h5-web 2>&1 | tail -10",
     timeout=300)

step("5. 等待容器状态",
     f"sleep 6 && docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}",
     timeout=60)

# 健康验证
step("6. backend /docs",
     f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost/autodev/{DEPLOY_ID}/api/docs || true",
     timeout=30)

print("\n===== 部署完成 =====", flush=True)
