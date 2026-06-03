"""[PRD-INVITE-FAMILY-CARD-V1 2026-05-30] 邀请家人入口卡片部署脚本

部署：
- h5-web 4 个文件 → 远程目录 + docker compose build h5-web + up -d
- backend 1 个测试文件 → docker cp 进容器 + 容器内 pytest
"""
import paramiko
import os
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    # (local_path, remote_path)
    ("h5-web/src/app/member-center/components/InviteFamilyCard.tsx",
     f"{REMOTE_BASE}/h5-web/src/app/member-center/components/InviteFamilyCard.tsx"),
    ("h5-web/src/app/member-center/page.tsx",
     f"{REMOTE_BASE}/h5-web/src/app/member-center/page.tsx"),
    ("h5-web/src/lib/__tests__/run_invite_card_test.mjs",
     f"{REMOTE_BASE}/h5-web/src/lib/__tests__/run_invite_card_test.mjs"),
    ("backend/tests/test_invite_family_card_v1_20260530.py",
     f"{REMOTE_BASE}/backend/tests/test_invite_family_card_v1_20260530.py"),
]


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, 22, USER, PWD, timeout=30)
    sftp = ssh.open_sftp()

    print("== 1. 上传文件 ==")
    for lp, rp in FILES:
        if not os.path.exists(lp):
            print(f"  ! 跳过（本地不存在）: {lp}")
            continue
        # 确保远程目录存在
        rdir = os.path.dirname(rp).replace("\\", "/")
        ssh.exec_command(f"mkdir -p {rdir}")[1].read()
        sftp.put(lp, rp)
        size = os.path.getsize(lp)
        print(f"  ✔ {lp} ({size} bytes) → {rp}")
    sftp.close()

    def run(cmd, timeout=600):
        print(f"\n$ {cmd}")
        i, o, e = ssh.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", errors="replace")
        err = e.read().decode("utf-8", errors="replace")
        if out:
            tail = out[-3000:]
            print(tail)
        if err:
            print("STDERR:", err[-2000:])
        return out, err

    print("\n== 2. 复制 backend 测试文件到容器 ==")
    run(f"docker cp {REMOTE_BASE}/backend/tests/test_invite_family_card_v1_20260530.py {DEPLOY_ID}-backend:/app/tests/")

    print("\n== 3. 容器内跑后端测试 ==")
    run(f"docker exec {DEPLOY_ID}-backend bash -lc 'cd /app && python -m pytest tests/test_invite_family_card_v1_20260530.py tests/test_member_family_member_v11_20260530.py -v 2>&1 | tail -40'", timeout=300)

    print("\n== 4. 重建 h5-web ==")
    run(f"cd {REMOTE_BASE} && docker compose build h5-web 2>&1 | tail -20", timeout=900)
    run(f"cd {REMOTE_BASE} && docker compose up -d --force-recreate --no-deps h5-web 2>&1 | tail -10", timeout=180)
    time.sleep(8)

    print("\n== 5. 检查容器状态 ==")
    run(f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n== 6. HTTPS smoke ==")
    base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    for path in ["/member-center/", "/health-profile/my-guardians/invite/", "/api/health"]:
        run(f"curl -sk -o /dev/null -w 'HTTP %{{http_code}}  %{{time_total}}s  {path}\\n' {base_url}{path}")

    print("\n== 7. h5 chunk grep 验证邀请卡片关键文案 ==")
    run(
        f"docker exec {DEPLOY_ID}-h5 bash -lc 'cd /app/.next/static/chunks && "
        f"(grep -l \"invite-family-card\\|邀请家人，共享健康守护\\|可管理 .* 位家人\" *.js 2>/dev/null | head -5; "
        f"echo ----; "
        f"grep -h \"邀请家人，共享健康守护\\|可管理.*位家人\\|不限家人数\\|已达上限，请\" *.js 2>/dev/null | head -3)'"
    )

    ssh.close()
    print("\n== 部署完毕 ==")


if __name__ == "__main__":
    main()
