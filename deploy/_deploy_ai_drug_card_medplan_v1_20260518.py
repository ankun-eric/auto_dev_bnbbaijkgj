"""[PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 部署脚本

直接 SFTP 上传变更文件到服务器项目目录（避开本地 git push 网络问题），
然后 docker compose 重建 backend + h5-web。
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"

# 本地变更文件 -> 服务器相对路径
FILES = [
    ("backend/app/api/health_plan_v2.py", "backend/app/api/health_plan_v2.py"),
    ("backend/app/models/models.py", "backend/app/models/models.py"),
    ("backend/app/schemas/health_plan_v2.py", "backend/app/schemas/health_plan_v2.py"),
    ("backend/app/services/schema_sync.py", "backend/app/services/schema_sync.py"),
    ("backend/tests/test_ai_drug_card_medplan_v1_20260518.py", "backend/tests/test_ai_drug_card_medplan_v1_20260518.py"),
    ("h5-web/src/app/(ai-chat)/ai-home/components/AddMedicationDrawer.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/components/AddMedicationDrawer.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/components/DrugIdentifyCard.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/components/DrugIdentifyCard.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/components/ViewMedicationPlansDrawer.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/components/ViewMedicationPlansDrawer.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    ("h5-web/src/components/medication/MedicationFormPanel.tsx",
     "h5-web/src/components/medication/MedicationFormPanel.tsx"),
]


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
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
            # 确保远程目录存在
            run(client, f"mkdir -p '{os.path.dirname(remote_abs)}'", show=False)
            print(f"  upload: {local_rel} -> {remote_abs}")
            sftp.put(local_abs, remote_abs)
        sftp.close()

        backend_container = f"{DEPLOY_ID}-backend"
        h5_container = f"{DEPLOY_ID}-h5-web"

        # 检查 compose 文件名
        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1", ignore_err=True, show=False)
        print("compose files:", out.strip())
        compose_file = "docker-compose.prod.yml"
        if "docker-compose.prod.yml" not in out:
            compose_file = "docker-compose.yml"

        # 重建 backend（不重新 build 镜像，直接用 docker cp 把变更 .py 拷贝进容器并重启）
        print("\n--- 同步 backend .py 到容器 ---")
        py_files = [r for _, r in FILES if r.startswith("backend/") and r.endswith(".py")]
        for rp in py_files:
            inner = rp.replace("backend/", "/app/", 1)
            run(client, f"docker cp {PROJ_DIR}/{rp} {backend_container}:{inner} 2>&1", ignore_err=True)
        print("\n--- restart backend ---")
        run(client, f"docker restart {backend_container} 2>&1 | tail -3", ignore_err=True)

        # 重建 h5-web（变更包括 page.tsx 与新组件，必须重新 build）
        print("\n--- rebuild h5-web ---")
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} stop h5-web 2>&1 | tail -3", ignore_err=True)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f h5-web 2>&1 | tail -3", ignore_err=True)
        print("Building h5-web (3-8 min)...")
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} build h5-web 2>&1 | tail -60", timeout=1800)
        run(client, f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d h5-web 2>&1 | tail -10")

        # 等 backend 健康
        print("\n--- 等待 backend 就绪 ---")
        for i in range(36):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}' "
                + backend_container + " 2>&1",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i+1)*5}s] backend: {s}")
            running = s.startswith("running|")
            health = s.split("|", 1)[1] if "|" in s else ""
            if running and (health == "" or health == "healthy"):
                print("  backend ready.")
                break
            time.sleep(5)

        # 等 h5-web
        print("\n--- 等待 h5-web 就绪 ---")
        for i in range(60):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}' " + h5_container + " 2>&1",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i+1)*5}s] h5-web: {s}")
            if s == "running":
                # 进一步：等到容器内 next 已启动 listen 端口
                rc2, out2, _ = run(
                    client,
                    f"docker logs --tail 30 {h5_container} 2>&1 | tail -20",
                    ignore_err=True, show=False,
                )
                if "Ready in" in out2 or "Local:" in out2 or "started server" in out2:
                    print("  h5-web ready.")
                    break
            time.sleep(5)

        # smoke
        print("\n--- smoke 测试 ---")
        for url in [
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/openapi.json",
            f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ai-home",
        ]:
            rc, out, _ = run(client, f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}' || echo curl-fail",
                             ignore_err=True, show=False)
            print(f"  {url} -> {out.strip()}")

    finally:
        client.close()
        print("Done.")


if __name__ == "__main__":
    main()
