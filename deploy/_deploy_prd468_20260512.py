"""[PRD-468 (2026-05-12)] 部署脚本 — 健康档案改版（含漏打卡代为提醒最小版本）

后端改动：
  - backend/app/models/health_v3.py（新增）— HealthMetricRecord / DeviceBinding 模型
  - backend/app/schemas/health_v3.py（新增）— Pydantic Schemas
  - backend/app/api/health_profile_v3.py（新增）— 10 个 API 端点
  - backend/app/tasks/medication_miss_check.py（新增）— 漏打卡扫描任务
  - backend/app/tasks/__init__.py（patch）— 注册新任务模块
  - backend/app/main.py（patch）— 新表迁移 + API 路由注册
  - backend/app/services/notification_scheduler.py（patch）— 注册漏打卡 10min 扫描

前端改动（H5）：
  - h5-web/src/app/health-profile-v2/page.tsx（新增）— 改版主页面
  - h5-web/src/app/health-metric/[type]/page.tsx（新增）— 指标详情页

部署流程：
  1. SFTP 上传所有新增/修改文件
  2. docker compose build backend + h5-web
  3. docker compose up -d backend h5-web
  4. 等容器健康，curl 验证关键路由 + 源码标记
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
    # 后端 - 模型 / Schema / API / 任务
    ("backend/app/models/health_v3.py", f"{REMOTE_PROJ}/backend/app/models/health_v3.py"),
    ("backend/app/schemas/health_v3.py", f"{REMOTE_PROJ}/backend/app/schemas/health_v3.py"),
    ("backend/app/api/health_profile_v3.py", f"{REMOTE_PROJ}/backend/app/api/health_profile_v3.py"),
    ("backend/app/tasks/medication_miss_check.py", f"{REMOTE_PROJ}/backend/app/tasks/medication_miss_check.py"),
    ("backend/app/tasks/__init__.py", f"{REMOTE_PROJ}/backend/app/tasks/__init__.py"),
    # 后端 - 入口与调度器
    ("backend/app/main.py", f"{REMOTE_PROJ}/backend/app/main.py"),
    ("backend/app/services/notification_scheduler.py", f"{REMOTE_PROJ}/backend/app/services/notification_scheduler.py"),
    # 前端 H5 - 改版主页 + 指标详情页
    ("h5-web/src/app/health-profile-v2/page.tsx", f"{REMOTE_PROJ}/h5-web/src/app/health-profile-v2/page.tsx"),
    ("h5-web/src/app/health-metric/[type]/page.tsx", f"{REMOTE_PROJ}/h5-web/src/app/health-metric/[type]/page.tsx"),
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
            (f"{REMOTE_PROJ}/backend/app/api/health_profile_v3.py", "PRD-468"),
            (f"{REMOTE_PROJ}/backend/app/api/health_profile_v3.py", "today-metrics"),
            (f"{REMOTE_PROJ}/backend/app/api/health_profile_v3.py", "device_binding".replace("_", "")),  # any check
            (f"{REMOTE_PROJ}/backend/app/tasks/medication_miss_check.py", "PRD-468"),
            (f"{REMOTE_PROJ}/backend/app/main.py", "_migrate_prd468_health_v3"),
            (f"{REMOTE_PROJ}/backend/app/main.py", "health_profile_v3"),
            (f"{REMOTE_PROJ}/backend/app/services/notification_scheduler.py", "miss_check_medication_reminders"),
            (f"{REMOTE_PROJ}/h5-web/src/app/health-profile-v2/page.tsx", "PRD-468"),
            (f"{REMOTE_PROJ}/h5-web/src/app/health-profile-v2/page.tsx", "prd468-sticky-tabs"),
            (f"{REMOTE_PROJ}/h5-web/src/app/health-metric/\\[type\\]/page.tsx", "PRD-468"),
        ]
        for path, mark in markers:
            _, out, _ = run(cli, f"grep -c '{mark}' {path}")
            v = (out or "0").strip().splitlines()[-1] if out else "0"
            print(f"[VERIFY] {path} <- '{mark}' = {v}")

        # ─── 构建并启动 backend + h5-web ───
        run(cli, f"cd {REMOTE_PROJ} && docker compose build backend h5-web", timeout=3600)
        run(cli, f"cd {REMOTE_PROJ} && docker compose up -d backend h5-web", timeout=600)

        time.sleep(20)

        # 等待 backend 与 h5 容器健康
        for _ in range(48):
            _, out_b, _ = run(cli, f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-backend 2>/dev/null || echo NONE")
            _, out_h, _ = run(cli, f"docker inspect -f '{{{{.State.Status}}}}' {DEPLOY_ID}-h5 2>/dev/null || echo NONE")
            if (out_b or "").strip() == "running" and (out_h or "").strip() == "running":
                break
            time.sleep(5)

        # ─── smoke：关键路由可达性 ───
        bad = []
        urls = [
            ("/health-profile-v2", "FE"),
            ("/health-metric/blood_pressure", "FE"),
            ("/health-metric/blood_glucose", "FE"),
            ("/api/health-profile-v3/devices", "API_401"),  # 期望未授权 401
            ("/api/health-profile-v3/1/today-metrics", "API_401"),
        ]
        for path, kind in urls:
            _, out, _ = run(cli, f"curl -k -s -o /dev/null -w '%{{http_code}}' {BASE_URL}{path}")
            code = (out or "").strip()
            print(f"[SMOKE] {path} -> {code}")
            if kind == "FE":
                if not (code.startswith("2") or code.startswith("3")):
                    bad.append((path, code, "FE_UNREACHABLE"))
            elif kind == "API_401":
                if code == "500":
                    bad.append((path, code, "BACKEND_500"))
                elif code not in {"401", "403", "422"}:
                    bad.append((path, code, "UNEXPECTED_API"))

        print(f"[SUMMARY] failed urls = {bad}")
        return 0 if not bad else 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
