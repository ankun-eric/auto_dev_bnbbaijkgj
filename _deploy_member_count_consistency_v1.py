"""[PRD-MEMBER-COUNT-CONSISTENCY-V1 2026-05-31] 部署脚本

将后端 + H5 变更同步到远程服务器，并重启对应容器。
小程序无需服务端部署，仅打包供下载。
"""
import os
import subprocess
import sys
import time

SSH_HOST = "ubuntu@newbb.test.bangbangvip.com"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_PREFIX = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(cmd, check=True, timeout=600):
    print(f"\n$ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if r.stdout:
        print(r.stdout[-4000:])
    if r.stderr:
        print("STDERR:", r.stderr[-2000:])
    if check and r.returncode != 0:
        sys.exit(r.returncode)
    return r


def sshcmd(remote_cmd):
    return f'ssh -o StrictHostKeyChecking=no {SSH_HOST} "{remote_cmd}"'


def scp(local, remote):
    return f'scp -o StrictHostKeyChecking=no -r "{local}" {SSH_HOST}:{remote}'


def main():
    # 1) 后端
    print("=" * 60)
    print("Step 1: 打包后端")
    print("=" * 60)
    backend_files = [
        "backend/app/api/family_member_v2.py",
        "backend/app/api/member_center_v2.py",
        "backend/tests/test_member_count_consistency_v1_20260531.py",
    ]
    be_tar = "_mcc_be.tar.gz"
    if os.path.exists(be_tar):
        os.remove(be_tar)
    run(f"tar czf {be_tar} " + " ".join(backend_files))

    run(scp(be_tar, f"{REMOTE_DIR}/"))
    run(sshcmd(f"cd {REMOTE_DIR} && tar xzf {be_tar}"))
    run(sshcmd(f"docker restart {PROJECT_PREFIX}-backend"))
    time.sleep(15)

    health_url = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health"
    for i in range(20):
        r = run(f'curl -k -s -o /dev/null -w "%{{http_code}}" {health_url}', check=False, timeout=30)
        code = (r.stdout or "").strip()
        print(f"backend health #{i+1}: {code}")
        if code == "200":
            break
        time.sleep(3)

    # 2) H5
    print("=" * 60)
    print("Step 2: 打包并重建 H5")
    print("=" * 60)
    h5_files = [
        "h5-web/src/app/member-center/page.tsx",
        "h5-web/src/app/member-center/components/MonthlyQuotaCard.tsx",
        "h5-web/src/app/health-profile/page.tsx",
    ]
    h5_tar = "_mcc_h5.tar.gz"
    if os.path.exists(h5_tar):
        os.remove(h5_tar)
    run(f"tar czf {h5_tar} " + " ".join(h5_files))
    run(scp(h5_tar, f"{REMOTE_DIR}/"))
    run(sshcmd(f"cd {REMOTE_DIR} && tar xzf {h5_tar}"))

    print("\nStep 3: 重建 H5 容器")
    run(sshcmd(f"cd {REMOTE_DIR} && docker compose up -d --build h5-web 2>&1 | tail -80"), timeout=1200)
    time.sleep(20)

    h5_url = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/member-center"
    for i in range(30):
        r = run(f'curl -k -s -o /dev/null -w "%{{http_code}}" {h5_url}', check=False, timeout=30)
        code = (r.stdout or "").strip()
        print(f"h5 check #{i+1}: {code}")
        if code in ("200", "302", "307"):
            break
        time.sleep(5)

    print("\n=== 部署完成 ===")


if __name__ == "__main__":
    main()
