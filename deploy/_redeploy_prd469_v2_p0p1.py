"""[PRD-469 v2 P0/P1] 重新部署脚本 - 同步本地最新代码到服务器并重启容器

针对本次发现的问题:
  - 服务器宿主和容器 main.py 都缺少 `prd469_health_v5` 路由注册
  - 导致所有 /api/prd469/* 返回 404
重新上传所有 PRD-469 相关文件 + 强制重建后端镜像 + 重启容器
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
BE = f"{DEPLOY_ID}-backend"
H5 = f"{DEPLOY_ID}-h5"

LOCAL_ROOT = Path(__file__).resolve().parent.parent

FILES = [
    # ===== 后端 =====
    ("backend/app/main.py", "backend/app/main.py"),
    ("backend/app/models/models.py", "backend/app/models/models.py"),
    ("backend/app/api/prd469_health_v5.py", "backend/app/api/prd469_health_v5.py"),
    ("backend/app/api/health_plan_v2.py", "backend/app/api/health_plan_v2.py"),
    ("backend/app/schemas/health_plan_v2.py", "backend/app/schemas/health_plan_v2.py"),
    ("backend/app/services/schema_sync.py", "backend/app/services/schema_sync.py"),
    ("backend/app/init_data.py", "backend/app/init_data.py"),
    ("backend/app/data/__init__.py", "backend/app/data/__init__.py"),
    ("backend/app/data/medication_seeds.py", "backend/app/data/medication_seeds.py"),
    ("backend/tests/test_prd469_health_v5.py", "backend/tests/test_prd469_health_v5.py"),
    # ===== H5 前端 =====
    ("h5-web/src/app/health-profile-v2/page.tsx", "h5-web/src/app/health-profile-v2/page.tsx"),
    ("h5-web/src/app/health-profile/page.tsx", "h5-web/src/app/health-profile/page.tsx"),
    ("h5-web/src/app/health-plan/medications/page.tsx", "h5-web/src/app/health-plan/medications/page.tsx"),
    ("h5-web/src/app/health-plan/medications/add/page.tsx", "h5-web/src/app/health-plan/medications/add/page.tsx"),
    ("h5-web/src/components/health-profile-v5/HealthInfoBlock.tsx", "h5-web/src/components/health-profile-v5/HealthInfoBlock.tsx"),
    ("h5-web/src/components/health-profile-v5/HealthEventsBlock.tsx", "h5-web/src/components/health-profile-v5/HealthEventsBlock.tsx"),
    ("h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx", "h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx"),
    ("h5-web/src/components/health-profile-v5/DeviceListBlock.tsx", "h5-web/src/components/health-profile-v5/DeviceListBlock.tsx"),
    ("h5-web/src/components/health-profile-v5/CareReminderBlock.tsx", "h5-web/src/components/health-profile-v5/CareReminderBlock.tsx"),
    ("h5-web/src/app/family/page.tsx", "h5-web/src/app/family/page.tsx"),
    ("h5-web/src/app/family-auth/page.tsx", "h5-web/src/app/family-auth/page.tsx"),
    ("h5-web/src/app/points/page.tsx", "h5-web/src/app/points/page.tsx"),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, timeout: int = 900, log_cmd: bool = True) -> tuple[int, str, str]:
    if log_cmd:
        short = cmd if len(cmd) <= 200 else cmd[:200] + "..."
        log(f"$ {short}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def main() -> int:
    cli = ssh_connect()
    try:
        # ===== Step 1: 通过 SFTP 上传文件 =====
        log("=== Step 1: 上传文件 ===")
        sftp = cli.open_sftp()
        try:
            for local_rel, remote_rel in FILES:
                local_path = LOCAL_ROOT / local_rel
                if not local_path.exists():
                    log(f"[WARN] 本地文件缺失: {local_rel}")
                    continue
                remote_path = f"{REMOTE_PROJ}/{remote_rel}"
                # 确保远端目录存在
                remote_dir = remote_path.rsplit("/", 1)[0]
                rc, _, _ = run(cli, f"mkdir -p {remote_dir}", log_cmd=False)
                sftp.put(str(local_path), remote_path)
                log(f"  uploaded {local_rel} -> {remote_path}")
        finally:
            sftp.close()

        # ===== Step 2: 校验关键文件包含必要标记 =====
        log("=== Step 2: 校验关键文件 ===")
        checks = [
            (f"{REMOTE_PROJ}/backend/app/main.py", "prd469_health_v5", "main.py 路由注册"),
            (f"{REMOTE_PROJ}/backend/app/api/prd469_health_v5.py", "/medical-record", "OCR 病历卡 API"),
            (f"{REMOTE_PROJ}/backend/app/api/prd469_health_v5.py", "hero_metrics", "Hero 四格指标"),
            (f"{REMOTE_PROJ}/backend/app/models/models.py", "frequency_per_day", "用药每日次数字段"),
            (f"{REMOTE_PROJ}/backend/app/models/models.py", "MedicalRecordCard", "病历卡表"),
            (f"{REMOTE_PROJ}/h5-web/src/app/health-plan/medications/add/page.tsx", "拍照识药", "拍照识药入口"),
            (f"{REMOTE_PROJ}/h5-web/src/app/health-profile-v2/page.tsx", "编辑基本信息", "Hero 编辑按钮"),
            (f"{REMOTE_PROJ}/h5-web/src/components/health-profile-v5/HealthInfoBlock.tsx", "家族病史", "家族病史编辑"),
            (f"{REMOTE_PROJ}/h5-web/src/components/health-profile-v5/HealthEventsBlock.tsx", "病历卡", "病历卡列表"),
        ]
        for path, mark, desc in checks:
            rc, o, e = run(cli, f"grep -q '{mark}' {path} && echo PASS || echo FAIL", log_cmd=False)
            status = "PASS" if "PASS" in o else "FAIL"
            log(f"  [{status}] {desc} ({mark} in {path.replace(REMOTE_PROJ, '')})")
            if status == "FAIL":
                log(f"[ERROR] 校验失败: {desc}")
                return 1

        # ===== Step 3: 重建后端镜像 + 重启容器 =====
        log("=== Step 3: 重建并重启后端 + h5 ===")
        rc, o, e = run(cli, f"cd {REMOTE_PROJ} && sudo docker compose build backend h5-web 2>&1 | tail -30", timeout=1200)
        log(o + e)
        if rc != 0:
            log("[ERROR] docker compose build 失败")
            return 1

        rc, o, e = run(cli, f"cd {REMOTE_PROJ} && sudo docker compose up -d backend h5-web", timeout=300)
        log(o + e)

        log("等待 25 秒服务启动...")
        time.sleep(25)

        # ===== Step 4: 校验容器内 main.py 包含 prd469 路由 =====
        log("=== Step 4: 校验容器内代码生效 ===")
        rc, o, e = run(cli, f"sudo docker exec {BE} grep -c 'prd469_health_v5' /app/app/main.py")
        log(f"容器 main.py 含 prd469_health_v5: {o.strip()} 次")
        if "0" in o.strip() or rc != 0:
            log("[ERROR] 容器内 main.py 未包含 prd469 路由")
            return 1

        # ===== Step 5: smoke test =====
        log("=== Step 5: 烟测核心 API ===")
        urls = [
            ("https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID + "/health-profile-v2/", "200"),
            ("https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID + "/api/prd469/family-member/relation-options", "200"),
            ("https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID + "/api/prd469/medication-library/search?kw=%E9%98%BF&limit=3", "200"),
            ("https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID + "/api/prd469/device/list", "401"),  # 鉴权
            ("https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID + "/api/prd469/medical-record/list", "401"),  # 鉴权
            ("https://newbb.test.bangbangvip.com/autodev/" + DEPLOY_ID + "/health-profile", "404"),
        ]
        all_ok = True
        for url, expected in urls:
            rc, o, e = run(cli, f'curl -sk -o /dev/null -w "%{{http_code}}" "{url}"', log_cmd=False)
            code = o.strip()
            ok = (code == expected)
            mark = "OK" if ok else "FAIL"
            log(f"  [{mark}] expect={expected} got={code} {url}")
            if not ok:
                all_ok = False
        if not all_ok:
            log("[ERROR] smoke test 未通过")
            return 2

        # ===== Step 6: 后端日志检查 =====
        log("=== Step 6: 后端日志尾部 ===")
        rc, o, e = run(cli, f"sudo docker logs --tail=15 {BE}", log_cmd=False)
        print(o)
        print(e)

        log("=== 部署成功 ===")
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
