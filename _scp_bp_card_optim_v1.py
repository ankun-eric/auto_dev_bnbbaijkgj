"""[PRD-BP-CARD-OPTIMIZE-V1 2026-05-30] 用 SFTP 直接把改动文件上传到服务器，再重建 H5 镜像。"""
from __future__ import annotations
import os
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

# 本次改动需要同步的文件（相对项目根）
FILES = [
    "h5-web/src/app/health-metric/[type]/page.tsx",
    "h5-web/src/app/health-profile/page.tsx",
    "h5-web/src/lib/__tests__/run_bp_format_test.mjs",
    "backend/tests/test_bp_card_optimize_v1_20260530.py",
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    sftp = cli.open_sftp()

    def ensure_dir(path: str):
        parts = path.strip("/").split("/")
        cur = ""
        for p in parts:
            cur = cur + "/" + p
            try:
                sftp.stat(cur)
            except IOError:
                try:
                    sftp.mkdir(cur)
                except IOError:
                    pass

    for rel in FILES:
        local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(local):
            print(f"!! local missing: {local}")
            continue
        remote = f"{PROJECT_DIR}/{rel}"
        ensure_dir(os.path.dirname(remote))
        print(f"PUT {local} -> {remote}")
        sftp.put(local, remote)

    sftp.close()

    def run(cmd, timeout=600):
        print(f"\n>>> {cmd}")
        _, o, e = cli.exec_command(cmd, timeout=timeout, get_pty=True)
        out = o.read().decode(errors="replace")
        err = e.read().decode(errors="replace")
        rc = o.channel.recv_exit_status()
        if out:
            print(out)
        if err:
            print("STDERR:", err)
        print(f"<<< exit_code={rc}")
        return rc

    # 验证文件已同步
    run(f"grep -c 'PRD-BP-CARD-OPTIMIZE-V1' {PROJECT_DIR}/h5-web/src/app/health-metric/\\[type\\]/page.tsx")
    run(f"grep -c 'bp-action-row' {PROJECT_DIR}/h5-web/src/app/health-metric/\\[type\\]/page.tsx")
    run(f"grep -c 'bp-mini-capsule\\|bp-mini-time-source' {PROJECT_DIR}/h5-web/src/app/health-profile/page.tsx")

    # 重建 + 重启 h5 容器
    run(f"cd {PROJECT_DIR} && docker compose build --no-cache h5-web 2>&1 | tail -n 80", timeout=1500)
    run(f"cd {PROJECT_DIR} && docker compose up -d h5-web 2>&1 | tail -n 30")
    time.sleep(8)
    run(f"cd {PROJECT_DIR} && docker compose ps 2>&1 | tail -n 10")

    # 探测访问
    run(f"curl -sSI -o /dev/null -w 'home=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/")
    run(f"curl -sSI -o /dev/null -w 'health-profile=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile")
    run(f"curl -sSI -o /dev/null -w 'bp-detail=%{{http_code}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-metric/blood_pressure'")

    cli.close()


if __name__ == "__main__":
    main()
