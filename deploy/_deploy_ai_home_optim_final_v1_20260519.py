"""[PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] ai-home 首页优化（最终版）部署脚本

改动范围：
- 后端：
  - 新增 medication_today_v1.py：/api/medication/today /api/medication/plans/exists
  - main.py 注册新 router
- H5（h5-web）：
  - 新增 components/MedicationCardButtons.tsx：2x2 胶囊按钮组件
  - components/DrugIdentifyCard.tsx：识药卡片底部使用新 4 按钮（加入用药计划/查看用药计划/今日用药/重新拍照）
  - app/(ai-chat)/ai-home/page.tsx：
      · 汉堡三横线改为"右-全-左"错落感
      · 汉堡与"小康"文字视觉中线对齐
      · DrugIdentifyCard 新 props: hasTodayMedication / loadingTodayMedication
      · 「查看用药计划」 → 跳转 /ai-home/medication-plans?tab=in_progress
      · 「今日用药」打卡抽屉沿用 ReminderDrawer
      · 加入用药计划保存成功后弹 1.5s Toast
  - components/ai-chat/ReminderBellButton.tsx：
      · 初始位置改为 viewport 50% 垂直正中 + 靠右
      · 拖动后位置持久化到 localStorage（bini.ai-home.bell.position）
      · 横竖屏切换边界保护
- 后端 pytest：test_ai_home_optim_final_v1_20260519.py 10 用例本地全部通过
"""
from __future__ import annotations

import os
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    # 后端
    ("backend/app/api/medication_today_v1.py",
     "backend/app/api/medication_today_v1.py"),
    ("backend/app/main.py", "backend/app/main.py"),
    ("backend/tests/test_ai_home_optim_final_v1_20260519.py",
     "backend/tests/test_ai_home_optim_final_v1_20260519.py"),
    # H5 - 新组件
    ("h5-web/src/app/(ai-chat)/ai-home/components/MedicationCardButtons.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/components/MedicationCardButtons.tsx"),
    # H5 - 改造组件
    ("h5-web/src/app/(ai-chat)/ai-home/components/DrugIdentifyCard.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/components/DrugIdentifyCard.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    ("h5-web/src/components/ai-chat/ReminderBellButton.tsx",
     "h5-web/src/components/ai-chat/ReminderBellButton.tsx"),
]


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:], flush=True)
    if show and err.strip():
        print("STDERR:", err[-1500:], flush=True)
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    print(f"Local base: {base}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    print("Connected.")

    try:
        sftp = client.open_sftp()
        for local_rel, remote_rel in FILES:
            local_abs = os.path.join(base, local_rel.replace("/", os.sep))
            if not os.path.exists(local_abs):
                print(f"  [SKIP] missing local: {local_abs}")
                continue
            remote_abs = f"{PROJ_DIR}/{remote_rel}"
            run(client, f"mkdir -p '{os.path.dirname(remote_abs)}'", show=False)
            print(f"  upload: {local_rel} -> {remote_abs}")
            sftp.put(local_abs, remote_abs)
        sftp.close()

        backend_container = f"{DEPLOY_ID}-backend"
        h5_container = f"{DEPLOY_ID}-h5"

        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1",
                         ignore_err=True, show=False)
        print("compose files:", out.strip())
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"

        # 同步 backend 改动
        print("\n--- 同步 backend 改动到容器 ---")
        for p in [
            "backend/app/api/medication_today_v1.py:/app/app/api/medication_today_v1.py",
            "backend/app/main.py:/app/app/main.py",
            "backend/tests/test_ai_home_optim_final_v1_20260519.py:/app/tests/test_ai_home_optim_final_v1_20260519.py",
        ]:
            local_p, container_p = p.split(":", 1)
            run(
                client,
                f"docker cp {PROJ_DIR}/{local_p} {backend_container}:{container_p} 2>&1",
                ignore_err=True,
                show=False,
            )

        print("\n--- 重启 backend ---")
        run(client, f"docker restart {backend_container} 2>&1 | tail -5",
            ignore_err=True, timeout=120)

        print("\n--- 等待 backend 就绪 ---")
        for i in range(40):
            rc, out, _ = run(
                client,
                "curl -ks -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/openapi.json || echo fail",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 3}s] backend openapi: {s}")
            if s == "200":
                break
            time.sleep(3)

        # rebuild h5-web
        print("\n--- rebuild h5-web ---")
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} stop h5-web 2>&1 | tail -3",
            ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f h5-web 2>&1 | tail -3",
            ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} build h5-web 2>&1 | tail -100",
            timeout=1800)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d h5-web 2>&1 | tail -10")

        print("\n--- 等待 h5-web 就绪 ---")
        for i in range(80):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}' " + h5_container + " 2>&1",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 5}s] h5-web: {s}")
            if s == "running":
                rc2, out2, _ = run(
                    client, f"docker logs --tail 40 {h5_container} 2>&1 | tail -25",
                    ignore_err=True, show=False,
                )
                if "Ready in" in out2 or "Local:" in out2 or "started server" in out2:
                    break
            time.sleep(5)

        # smoke
        print("\n--- smoke ---")
        for url in [
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/openapi.json",
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ai-home",
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ai-home/medication-plans?tab=in_progress",
            # 未鉴权应 401（路由可达）
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/medication/today",
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/medication/plans/exists?medName=test",
        ]:
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}' || echo curl-fail",
                ignore_err=True, show=False,
            )
            print(f"  {url} -> {out.strip()}")

        # backend pytest
        print("\n--- backend pytest（容器内） ---")
        run(
            client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_ai_home_optim_final_v1_20260519.py -v --tb=short 2>&1 | tail -80",
            ignore_err=True,
            timeout=300,
        )

    finally:
        client.close()
        print("Done.")


if __name__ == "__main__":
    main()
