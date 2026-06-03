"""[BUG_FIX-FAMILY-NICKNAME-NOTNULL-20260530] 远程部署 + 验证脚本

流程：
1. 探测服务器项目部署目录
2. 上传 backend 和 h5-web 改动文件
3. 重建 backend 与 h5-web 容器
4. 在 backend 容器内跑 pytest 验证修复
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}"

# 改动文件相对路径
CHANGED_BACKEND_FILES = [
    "backend/app/models/models.py",
    "backend/app/api/auth.py",
    "backend/app/api/family.py",
    "backend/app/services/family_self_backfill_migration.py",
    "backend/app/services/family_member_nickname_cleanup_migration.py",
    "backend/app/main.py",
    "backend/tests/test_family_nickname_notnull_20260530.py",
]

CHANGED_H5_FILES = [
    "h5-web/src/app/health-profile/archive-list/page.tsx",
]

LOCAL_ROOT = Path(__file__).resolve().parent


def make_ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(SSH_HOST, username=SSH_USER, password=SSH_PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def upload_file(sftp: paramiko.SFTPClient, local: str, remote: str) -> None:
    # 自动创建远端目录
    parts = remote.split("/")
    cur = ""
    for p in parts[1:-1]:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except Exception:
                pass
    sftp.put(local, remote)


def find_project_dir(cli: paramiko.SSHClient) -> str:
    """探测服务器上本项目的部署目录。优先含 docker-compose.yml 且 container 含 PROJECT_ID 的目录。"""
    # 通过 docker 反查 backend 容器挂载推断
    rc, out, err = run(
        cli,
        f"docker inspect {PROJECT_ID}-backend --format '{{{{ range .Mounts }}}}{{{{ .Source }}}}|{{{{ .Destination }}}}\\n{{{{ end }}}}' 2>/dev/null || true",
    )
    print("[probe] backend mounts:", out.strip())

    rc, out, err = run(
        cli,
        f"docker inspect {PROJECT_ID}-backend --format '{{{{ .Config.Labels }}}}' 2>/dev/null || true",
    )
    print("[probe] backend labels:", out.strip())

    # 通过 docker compose label com.docker.compose.project.working_dir 找
    rc, out, err = run(
        cli,
        f"docker inspect {PROJECT_ID}-backend --format '{{{{ index .Config.Labels \"com.docker.compose.project.working_dir\" }}}}' 2>/dev/null || true",
    )
    workdir = out.strip()
    if workdir and workdir != "<no value>":
        print(f"[probe] found compose working_dir={workdir}")
        return workdir

    # 兜底：常见路径
    candidates = [
        f"/home/ubuntu/autodev/{PROJECT_ID}",
        f"/home/ubuntu/{PROJECT_ID}",
        f"/opt/autodev/{PROJECT_ID}",
        f"/srv/autodev/{PROJECT_ID}",
    ]
    for c in candidates:
        rc, out, err = run(cli, f"test -f {c}/docker-compose.yml && echo OK || echo NO")
        if "OK" in out:
            print(f"[probe] found via candidate: {c}")
            return c

    # 大范围搜索
    rc, out, err = run(
        cli,
        f"sudo -n find / -maxdepth 6 -name docker-compose.yml -type f 2>/dev/null | xargs grep -l '{PROJECT_ID}' 2>/dev/null | head -5",
    )
    if out.strip():
        first = out.strip().splitlines()[0]
        d = os.path.dirname(first)
        print(f"[probe] found via find: {d}")
        return d

    raise RuntimeError("无法定位项目部署目录")


def main():
    cli = make_ssh()
    try:
        print("=" * 60)
        print("[Step 1] 探测项目目录")
        proj_dir = find_project_dir(cli)
        print(f"项目目录：{proj_dir}")

        print("=" * 60)
        print("[Step 2] 上传后端 + H5 改动文件")
        sftp = cli.open_sftp()
        for rel in CHANGED_BACKEND_FILES + CHANGED_H5_FILES:
            local = str(LOCAL_ROOT / rel)
            if not os.path.exists(local):
                print(f"  跳过不存在的文件：{rel}")
                continue
            remote = f"{proj_dir}/{rel}".replace("\\", "/")
            print(f"  上传 {rel} -> {remote}")
            upload_file(sftp, local, remote)
        sftp.close()

        print("=" * 60)
        print("[Step 3] 备份数据库（family_members + 相关表）")
        backup_name = f"/tmp/family_members_clean_{int(time.time())}.sql"
        rc, out, err = run(
            cli,
            f"docker exec {PROJECT_ID}-db sh -c \"mysqldump -uroot -pbini_health_2026 bini_health "
            "family_members health_profiles family_invitations family_management "
            "blood_pressure_records glucose_records medical_reports tcm_records "
            "medicine_recognition devices reminders alert_notifications "
            f"\" > {backup_name} 2>/dev/null && ls -la {backup_name}",
            timeout=120,
        )
        print(f"备份结果：rc={rc}")
        print(out[-500:] if out else "")
        if err:
            print("stderr:", err[-300:])

        print("=" * 60)
        print("[Step 4] 重建 backend 容器（应用代码 + 触发清理迁移）")
        rc, out, err = run(
            cli,
            f"cd {proj_dir} && docker compose up -d --build backend 2>&1 | tail -50",
            timeout=600,
        )
        print(f"rc={rc}")
        print(out[-1500:])
        if err:
            print("stderr:", err[-500:])

        print("=" * 60)
        print("[Step 5] 重建 h5-web 容器")
        rc, out, err = run(
            cli,
            f"cd {proj_dir} && docker compose up -d --build h5-web 2>&1 | tail -50",
            timeout=900,
        )
        print(f"rc={rc}")
        print(out[-1500:])
        if err:
            print("stderr:", err[-500:])

        print("=" * 60)
        print("[Step 6] 等待 backend 启动 + 查启动迁移日志")
        time.sleep(15)
        rc, out, err = run(
            cli,
            f"docker logs --tail 200 {PROJECT_ID}-backend 2>&1 | "
            "grep -E 'family_member_nickname_cleanup|family_self_backfill|Uvicorn running|Application startup complete'",
        )
        print(out or "(no matches)")

        print("=" * 60)
        print("[Step 7] 校验数据库已无空姓名脏数据 + nickname 列已 NOT NULL")
        rc, out, err = run(
            cli,
            f"docker exec {PROJECT_ID}-db mysql -uroot -pbini_health_2026 -N -e "
            "\"SELECT COUNT(*) FROM family_members WHERE nickname IS NULL OR TRIM(nickname)='';\" "
            "bini_health 2>/dev/null",
        )
        print(f"空姓名残留：{out.strip()}")

        rc, out, err = run(
            cli,
            f"docker exec {PROJECT_ID}-db mysql -uroot -pbini_health_2026 -N -e "
            "\"SHOW COLUMNS FROM family_members LIKE 'nickname';\" "
            "bini_health 2>/dev/null",
        )
        print(f"nickname 列定义：{out.strip()}")

        print("=" * 60)
        print("[Step 8] 在 backend 容器内执行新增测试用例")
        rc, out, err = run(
            cli,
            f"docker exec {PROJECT_ID}-backend sh -c "
            "'cd /app && python -m pytest tests/test_family_nickname_notnull_20260530.py -v --tb=short 2>&1' "
            "| tail -120",
            timeout=600,
        )
        print(out)
        if err:
            print("stderr:", err[-500:])

        print("=" * 60)
        print("[Step 9] 跑相关回归测试（family / health_archive 系列）")
        rc, out, err = run(
            cli,
            f"docker exec {PROJECT_ID}-backend sh -c "
            "'cd /app && python -m pytest tests/test_family.py tests/test_family_member_v2_20260518.py "
            "tests/test_health_archive_mgr_v1_20260529.py "
            "-v --tb=short 2>&1' | tail -150",
            timeout=600,
        )
        print(out[-3000:])

        print("=" * 60)
        print("[Step 10] 检查前端页面可达")
        rc, out, err = run(
            cli,
            f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' '{PROJECT_BASE_URL}/health-profile/archive-list'",
        )
        print(f"H5 archive-list 页面：{out.strip()}")

        rc, out, err = run(
            cli,
            f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' '{PROJECT_BASE_URL}/api/docs'",
        )
        print(f"后端 API docs：{out.strip()}")

    finally:
        cli.close()


if __name__ == "__main__":
    main()
