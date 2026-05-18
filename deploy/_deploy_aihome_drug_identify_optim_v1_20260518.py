"""[PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 2026-05-18] ai-home 拍照识药功能优化 部署脚本

改动范围：
- 后端：/api/medication-reminder/today 新增 consultant_id 入参（按咨询人筛选）
- H5-web：
  - DrugIdentifyCard 4 按钮等大等宽 4 等分 + 用药提醒按钮（红点 / 置灰 / 抽屉）
  - 分阶段渐进淡入（基础信息 → 用法用量 → 安全提示 → 个性化风险）
  - 单区块失败兜底 + 整次重试（复用原图）
  - 咨询人切换 = 启动新会话；AI 回答中禁用切换器 + loading 小图标
  - 候选列表当前咨询人置灰 + (当前) 标注
  - ReminderDrawer 支持 consultantId 入参，与顶部铃铛 100% 等价
- 后端新增 pytest 用例：test_aihome_drug_identify_optim_v1_20260518.py
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
    # 后端：medication-reminder 路由新增 consultant_id 入参
    ("backend/app/api/medication_reminder.py",
     "backend/app/api/medication_reminder.py"),
    # 后端测试
    ("backend/tests/test_aihome_drug_identify_optim_v1_20260518.py",
     "backend/tests/test_aihome_drug_identify_optim_v1_20260518.py"),
    # H5-web 改动
    ("h5-web/src/app/(ai-chat)/ai-home/components/DrugIdentifyCard.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/components/DrugIdentifyCard.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    ("h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
     "h5-web/src/components/ai-chat/ConsultTargetPicker.tsx"),
    ("h5-web/src/components/ai-chat/ReminderDrawer.tsx",
     "h5-web/src/components/ai-chat/ReminderDrawer.tsx"),
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

        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1", ignore_err=True, show=False)
        print("compose files:", out.strip())
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"

        # 同步 backend 文件到 backend 容器并重启
        print("\n--- 同步 backend 改动到容器 ---")
        run(
            client,
            f"docker cp {PROJ_DIR}/backend/app/api/medication_reminder.py "
            f"{backend_container}:/app/app/api/medication_reminder.py 2>&1",
            ignore_err=True,
        )
        run(
            client,
            f"docker cp {PROJ_DIR}/backend/tests/test_aihome_drug_identify_optim_v1_20260518.py "
            f"{backend_container}:/app/tests/test_aihome_drug_identify_optim_v1_20260518.py 2>&1",
            ignore_err=True,
        )
        print("\n--- 重启 backend 容器（PID 1 热生效改动） ---")
        run(client, f"docker restart {backend_container} 2>&1 | tail -5", ignore_err=True, timeout=120)

        # 等 backend 启动
        print("\n--- 等待 backend 就绪 ---")
        for i in range(40):
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' http://127.0.0.1:8000/api/openapi.json || echo fail",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 3}s] backend openapi: {s}")
            if s == "200":
                print("  backend ready.")
                break
            time.sleep(3)

        # 重建 h5-web
        print("\n--- rebuild h5-web ---")
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} stop h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f h5-web 2>&1 | tail -3", ignore_err=True)
        print("Building h5-web (5-10 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} build h5-web 2>&1 | tail -100", timeout=1800)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d h5-web 2>&1 | tail -10")

        # 等 h5-web
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
                    client,
                    f"docker logs --tail 40 {h5_container} 2>&1 | tail -25",
                    ignore_err=True, show=False,
                )
                if "Ready in" in out2 or "Local:" in out2 or "started server" in out2:
                    print("  h5-web ready.")
                    break
            time.sleep(5)

        # smoke
        print("\n--- smoke 测试 ---")
        for url in [
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/openapi.json",
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ai-home",
            # 不传 token 应 401，证明路由可达
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/medication-reminder/today?consultant_id=1",
        ]:
            rc, out, _ = run(client, f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}' || echo curl-fail",
                             ignore_err=True, show=False)
            print(f"  {url} -> {out.strip()}")

        # backend pytest（容器内运行）
        print("\n--- backend pytest（容器内） ---")
        run(
            client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_aihome_drug_identify_optim_v1_20260518.py -v --tb=short 2>&1 | tail -80",
            ignore_err=True,
            timeout=300,
        )

    finally:
        client.close()
        print("Done.")


if __name__ == "__main__":
    main()
