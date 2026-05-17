"""[PRD-MED-PLAN-OPTIM-V1] 服务器 git fetch 拉到的是旧 commit，强制重拉并重新构建"""
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY = "gateway"
GIT_BRANCH = "master"
TARGET_COMMIT = "e2c575e"  # 本次本地推送的 commit 前缀


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:])
    if show and err.strip():
        print("STDERR:", err[-1500:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting...")
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30,
                   allow_agent=False, look_for_keys=False)
    try:
        # 强制 fetch + reset，最多 5 次
        success = False
        for attempt in range(1, 6):
            run(client, f"cd {PROJ_DIR} && git fetch origin {GIT_BRANCH} --no-tags 2>&1 | tail -8",
                timeout=300, ignore_err=True)
            rc, out, _ = run(client, f"cd {PROJ_DIR} && git rev-parse origin/{GIT_BRANCH}",
                             ignore_err=True, show=False)
            print(f"  origin/{GIT_BRANCH} = {out.strip()}")
            if out.strip().startswith(TARGET_COMMIT):
                print(f"  fetch ok (attempt {attempt})")
                success = True
                break
            print(f"  expected commit starting with {TARGET_COMMIT}, retrying...")
            time.sleep(8 * attempt)
        if not success:
            print("WARN: 多次 fetch 仍未获取最新 commit，使用 SFTP 兜底...")
            # SFTP 兜底：上传关键文件
            sftp = client.open_sftp()
            files = [
                "backend/app/api/health_plan_v2.py",
                "h5-web/src/components/medication/MedicationFormPanel.tsx",
                "h5-web/src/components/medication/MedicalAdviceTip.tsx",
                "h5-web/src/components/medication/CycleDrawer.tsx",
                "h5-web/src/app/(ai-chat)/ai-home/medication-plans/page.tsx",
                "miniprogram/pages/health-plan/medication-form/index.wxml",
                "miniprogram/pages/health-plan/medication-form/index.wxss",
                "miniprogram/pages/health-plan/medication-form/index.js",
                "miniprogram/pages/health-plan/medications/index.wxml",
                "miniprogram/pages/health-plan/medications/index.wxss",
                "miniprogram/pages/health-plan/medications/index.js",
                "backend/tests/test_med_plan_optim_v1_20260517.py",
            ]
            import os
            for f in files:
                local = os.path.join(".", f.replace("/", os.sep))
                remote = f"{PROJ_DIR}/{f}"
                # 确保远程目录存在
                rdir = "/".join(remote.split("/")[:-1])
                run(client, f"mkdir -p '{rdir}'", ignore_err=True, show=False)
                print(f"  SFTP -> {f}")
                sftp.put(local, remote)
            sftp.close()
        else:
            run(client, f"cd {PROJ_DIR} && git reset --hard origin/{GIT_BRANCH} 2>&1 | tail -5")
        run(client, f"cd {PROJ_DIR} && git log -1 --oneline")

        backend_container = f"{DEPLOY_ID}-backend"
        # 重建 backend（确保新代码生效）
        print("Building backend ...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -20",
            timeout=900)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1 | tail -10")

        print("Building h5-web ...")
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -20",
            timeout=1800)
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate h5-web 2>&1 | tail -10")

        # 等待
        time.sleep(8)

        # reload gateway
        run(client, f"docker exec {GATEWAY} nginx -s reload 2>&1", ignore_err=True)

        # 验证 h5 是否含有新文案
        print("\n--- 验证 h5-web 渲染包含新内容 ---")
        base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
        run(client, f"curl -sk '{base}/ai-home/medication-plans/new/' | grep -o '用药请遵循医嘱' | head -3",
            ignore_err=True)
        run(client, f"curl -sk '{base}/ai-home/medication-plans/new/' | grep -o '\\#0EA5E9' | head -3",
            ignore_err=True)

        # 状态
        run(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        # smoke
        print("\n--- smoke ---")
        for path in ["/ai-home", "/ai-home/medication-plans", "/ai-home/medication-plans/new",
                     "/api/health-plan/medications", "/api/medication-library/suggest?q=ab"]:
            url = base + path
            run(client, f"curl -sk -o /dev/null -w 'HTTP %{{http_code}} -> {path}\\n' '{url}'",
                ignore_err=True)
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
