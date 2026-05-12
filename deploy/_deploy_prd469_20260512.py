"""[PRD-469 (2026-05-12)] 部署脚本 — 健康档案 v2 优化（对齐 v5 设计稿）

后端改动：
  - backend/app/models/models.py（patch）— 新增 MedicationLibrary / HealthInfoExtra /
    HealthEvent / DeviceBinding / ReminderSetting 5 张表
  - backend/app/api/prd469_health_v5.py（新增）— PRD-469 完整 API
  - backend/app/data/medication_seeds.py（新增）— 药品库种子数据（200+ 条）
  - backend/app/data/__init__.py（新增）— 包标记
  - backend/app/init_data.py（patch）— 自动初始化药品库
  - backend/app/main.py（patch）— 注册 prd469_health_v5 路由

前端改动（H5）：
  - h5-web/src/app/health-profile-v2/page.tsx（重写）— 对齐 v5
  - h5-web/src/app/health-profile/page.tsx（重写）— 旧路由 404
  - h5-web/src/components/health-profile-v5/*.tsx（新增）— 5 个 v5 组件
  - h5-web/src/app/health-plan/medications/page.tsx（patch）— 修复 Bug
  - h5-web/src/app/health-plan/medications/add/page.tsx（patch）— 药品库联想 + 修复 Bug
  - h5-web/src/app/family/page.tsx（patch）— 跳转改 v2
  - h5-web/src/app/family-auth/page.tsx（patch）— 跳转改 v2
  - h5-web/src/app/points/page.tsx（patch）— 跳转改 v2
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = Path(__file__).resolve().parent.parent

FILES = [
    # 后端
    ("backend/app/models/models.py", f"{REMOTE_PROJ}/backend/app/models/models.py"),
    ("backend/app/api/prd469_health_v5.py", f"{REMOTE_PROJ}/backend/app/api/prd469_health_v5.py"),
    ("backend/app/data/__init__.py", f"{REMOTE_PROJ}/backend/app/data/__init__.py"),
    ("backend/app/data/medication_seeds.py", f"{REMOTE_PROJ}/backend/app/data/medication_seeds.py"),
    ("backend/app/init_data.py", f"{REMOTE_PROJ}/backend/app/init_data.py"),
    ("backend/app/main.py", f"{REMOTE_PROJ}/backend/app/main.py"),
    # 前端 H5 主页
    ("h5-web/src/app/health-profile-v2/page.tsx", f"{REMOTE_PROJ}/h5-web/src/app/health-profile-v2/page.tsx"),
    ("h5-web/src/app/health-profile/page.tsx", f"{REMOTE_PROJ}/h5-web/src/app/health-profile/page.tsx"),
    # 前端 H5 组件
    ("h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx"),
    ("h5-web/src/components/health-profile-v5/DeviceListBlock.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/health-profile-v5/DeviceListBlock.tsx"),
    ("h5-web/src/components/health-profile-v5/HealthInfoBlock.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/health-profile-v5/HealthInfoBlock.tsx"),
    ("h5-web/src/components/health-profile-v5/CareReminderBlock.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/health-profile-v5/CareReminderBlock.tsx"),
    ("h5-web/src/components/health-profile-v5/HealthEventsBlock.tsx",
     f"{REMOTE_PROJ}/h5-web/src/components/health-profile-v5/HealthEventsBlock.tsx"),
    # 前端 H5 用药计划
    ("h5-web/src/app/health-plan/medications/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/health-plan/medications/page.tsx"),
    ("h5-web/src/app/health-plan/medications/add/page.tsx",
     f"{REMOTE_PROJ}/h5-web/src/app/health-plan/medications/add/page.tsx"),
    # 前端 H5 跳转修正
    ("h5-web/src/app/family/page.tsx", f"{REMOTE_PROJ}/h5-web/src/app/family/page.tsx"),
    ("h5-web/src/app/family-auth/page.tsx", f"{REMOTE_PROJ}/h5-web/src/app/family-auth/page.tsx"),
    ("h5-web/src/app/points/page.tsx", f"{REMOTE_PROJ}/h5-web/src/app/points/page.tsx"),
    # 测试
    ("backend/tests/test_prd469_health_v5.py", f"{REMOTE_PROJ}/backend/tests/test_prd469_health_v5.py"),
]


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 600):
    print(f"[REMOTE] $ {cmd[:200]}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:])
    if err.strip():
        print(f"[STDERR] {err[-2000:]}")
    return rc, out, err


def upload_files(cli: paramiko.SSHClient) -> None:
    sftp = cli.open_sftp()
    for local_rel, remote in FILES:
        local_path = LOCAL_ROOT / local_rel
        if not local_path.exists():
            print(f"[SKIP] local missing: {local_path}")
            continue
        remote_dir = remote.rsplit("/", 1)[0]
        cli.exec_command(f"mkdir -p {remote_dir}")
        sftp.put(str(local_path), remote)
        print(f"[UPLOAD] {local_rel} -> {remote}")
    sftp.close()


def main() -> int:
    cli = ssh_connect()
    try:
        run(cli, f"test -d {REMOTE_PROJ} && echo OK || echo MISSING")
        upload_files(cli)

        # ─── 源码标记校验 ───
        markers = [
            (f"{REMOTE_PROJ}/backend/app/api/prd469_health_v5.py", "PRD-469"),
            (f"{REMOTE_PROJ}/backend/app/api/prd469_health_v5.py", "medication-library"),
            (f"{REMOTE_PROJ}/backend/app/main.py", "prd469_health_v5"),
            (f"{REMOTE_PROJ}/backend/app/init_data.py", "_init_medication_library_prd469"),
            (f"{REMOTE_PROJ}/h5-web/src/app/health-profile-v2/page.tsx", "PRD-469"),
            (f"{REMOTE_PROJ}/h5-web/src/app/health-profile-v2/page.tsx", "prd469-sticky-tabs"),
            (f"{REMOTE_PROJ}/h5-web/src/app/health-profile/page.tsx", "PRD-469 M1"),
            (f"{REMOTE_PROJ}/h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx", "PRD-469 M3"),
            (f"{REMOTE_PROJ}/h5-web/src/app/health-plan/medications/add/page.tsx", "PRD-469 M5"),
        ]
        for path, mark in markers:
            _, out, _ = run(cli, f"grep -c '{mark}' {path}")
            v = (out or "0").strip().splitlines()[-1] if out else "0"
            print(f"[VERIFY] {path} <- '{mark}' = {v}")

        # ─── 构建并启动 backend + h5-web ───
        run(cli, f"cd {REMOTE_PROJ} && docker compose build backend h5-web", timeout=3600)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d backend h5-web", timeout=600)

        time.sleep(20)

        for _ in range(48):
            _, out_b, _ = run(cli, f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-backend 2>/dev/null || echo NONE")
            _, out_h, _ = run(cli, f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-h5 2>/dev/null || echo NONE")
            if (out_b or "").strip() == "running" and (out_h or "").strip() == "running":
                break
            time.sleep(5)

        # ─── smoke 关键路由 ───
        bad = []
        urls = [
            ("/health-profile-v2", "FE"),
            ("/health-profile", "FE_404"),  # 期望 404
            ("/api/prd469/family-member/relation-options", "API_OPEN"),  # 公开 API 期望 200
            ("/api/prd469/medication-library/search?kw=阿", "API_OPEN"),
            ("/api/prd469/device/list", "API_401"),  # 需登录 -> 401
        ]
        for path, kind in urls:
            _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE_URL}{path}")
            code = (out or "").strip()
            print(f"[SMOKE] {path} -> {code}")
            if kind == "FE":
                if not (code.startswith("2") or code.startswith("3")):
                    bad.append((path, code, "FE_UNREACHABLE"))
            elif kind == "FE_404":
                if code != "404":
                    bad.append((path, code, "EXPECT_404"))
            elif kind == "API_OPEN":
                if code != "200":
                    bad.append((path, code, "EXPECT_200"))
            elif kind == "API_401":
                if code == "500":
                    bad.append((path, code, "BACKEND_500"))
                elif code not in {"401", "403", "422"}:
                    bad.append((path, code, "UNEXPECTED_API"))

        # ─── 运行 pytest ───
        rc_test, out_test, _ = run(
            cli,
            f"docker exec {DEPLOY_ID}-backend bash -lc 'cd /app && python -m pytest tests/test_prd469_health_v5.py --tb=short -q 2>&1 | tail -80'",
            timeout=900,
        )

        print(f"[SUMMARY] failed urls = {bad}")
        print(f"[SUMMARY] pytest rc = {rc_test}")
        return 0 if not bad and rc_test == 0 else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
