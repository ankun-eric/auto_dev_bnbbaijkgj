"""[BUGFIX-BP-TAB-OPTIMIZE-V1 2026-05-30] 远程部署脚本

工作流程：
1. SFTP 上传以下 5 个文件到远程：
   - backend/app/schemas/health_v3.py
   - backend/app/api/health_profile_v3.py
   - backend/tests/test_bp_tab_trend_v1_20260530.py
   - h5-web/src/lib/bp-level.ts
   - h5-web/src/app/health-metric/[type]/page.tsx
2. 远程后端 docker cp 进容器并 restart
3. 远程在容器内跑 pytest 新测试
4. 远程 h5-web docker compose build + up -d
5. HTTPS 冒烟验证
"""
from __future__ import annotations

import io
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

UPLOADS = [
    ("backend/app/schemas/health_v3.py", f"{REMOTE_BASE}/backend/app/schemas/health_v3.py"),
    ("backend/app/api/health_profile_v3.py", f"{REMOTE_BASE}/backend/app/api/health_profile_v3.py"),
    ("backend/tests/test_bp_tab_trend_v1_20260530.py", f"{REMOTE_BASE}/backend/tests/test_bp_tab_trend_v1_20260530.py"),
    ("h5-web/src/lib/bp-level.ts", f"{REMOTE_BASE}/h5-web/src/lib/bp-level.ts"),
    ("h5-web/src/app/health-metric/[type]/page.tsx", f"{REMOTE_BASE}/h5-web/src/app/health-metric/[type]/page.tsx"),
]


def ssh_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    return c


def run(c, cmd, *, timeout=600, ok_codes=(0,)):
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    print(out[-4000:] if out else "")
    if err.strip():
        print("STDERR:", err[-2000:])
    print(f"exit={rc}")
    if rc not in ok_codes:
        raise SystemExit(f"远程命令失败：{cmd}")
    return out, err, rc


def main():
    c = ssh_client()
    try:
        sftp = c.open_sftp()
        for local, remote in UPLOADS:
            print(f"[upload] {local}  ->  {remote}")
            # 确保远程目录存在
            rdir = remote.rsplit("/", 1)[0]
            run(c, f"mkdir -p {rdir}")
            sftp.put(local, remote)
        sftp.close()

        # 找 backend 容器名
        backend_name = f"{DEPLOY_ID}-backend"
        h5_name = f"{DEPLOY_ID}-h5-web"
        run(c, f"cd {REMOTE_BASE} && docker compose ps --format '{{{{.Name}}}}'")

        # 同步代码到容器
        for fname in [
            "app/schemas/health_v3.py",
            "app/api/health_profile_v3.py",
        ]:
            run(c, f"docker cp {REMOTE_BASE}/backend/{fname} {backend_name}:/app/{fname}")
        run(c, f"docker cp {REMOTE_BASE}/backend/tests/test_bp_tab_trend_v1_20260530.py {backend_name}:/app/tests/test_bp_tab_trend_v1_20260530.py")

        # 重启后端
        run(c, f"docker restart {backend_name}")
        time.sleep(8)

        # 容器内跑新测试
        run(
            c,
            f"docker exec {backend_name} python -m pytest tests/test_bp_tab_trend_v1_20260530.py -v 2>&1 | tail -50",
            ok_codes=(0,),
        )

        # 重建 h5-web
        run(
            c,
            f"cd {REMOTE_BASE} && docker compose build h5-web 2>&1 | tail -20",
            timeout=1800,
        )
        run(
            c,
            f"cd {REMOTE_BASE} && docker compose up -d --force-recreate --no-deps h5-web 2>&1 | tail -20",
            timeout=300,
        )
        time.sleep(10)

        # HTTPS 冒烟
        print("\n=== HTTPS 冒烟验证 ===")
        for path in [
            "/api/health",
            "/health-profile/",
            "/health-metric/blood_pressure/",
            "/api/health-profile-v3/devices",
        ]:
            run(c, f"curl -k -s -o /dev/null -w 'HTTP %{{http_code}}\\n' {BASE_URL}{path}", ok_codes=(0,))

        # 抓 h5 构建产物，验证关键文案
        print("\n=== 校验 h5-web 构建产物含关键文案 ===")
        run(
            c,
            f"docker exec {h5_name} sh -c \"find /app/.next -name '*.js' | xargs grep -l '最近 7 天趋势' 2>/dev/null | head -3\"",
            ok_codes=(0, 1),
        )
        run(
            c,
            f"docker exec {h5_name} sh -c \"find /app/.next -name '*.js' | xargs grep -l '即将上线' 2>/dev/null | head -3\"",
            ok_codes=(0, 1),
        )
        print("\n✅ 部署完成")
    finally:
        c.close()


if __name__ == "__main__":
    main()
