"""[PRD-QUESTIONNAIRE-DRAWER-V1.2 / PRD-TCM-CONSTITUTION-36Q-V1 2026-05-20] 部署脚本

部署内容（核心改动）：
后端：
- backend/app/models/models.py（新增 3 个字段）
- backend/app/schemas/function_button.py（pre_card_icon / pre_card_icon_type）
- backend/app/schemas/tcm.py（constitution_scores / option_index）
- backend/app/api/tcm.py（接入王琦公式 + constitution_scores 入库）
- backend/app/api/questionnaire.py（render-meta 补齐引导卡片字段）
- backend/app/services/constitution_score.py（新建：王琦本地公式）
- backend/app/services/prd_questionnaire_drawer_v1_migration.py（扩展 v1.2）
- backend/tests/test_constitution_score.py（新建：5 个单测用例 + 确定性）

Admin：
- admin-web/src/app/(admin)/function-buttons/page.tsx（卡片图标三选一）

H5：
- h5-web/src/app/tcm/page.tsx（拉取 36 题）

小程序：
- miniprogram/pages/tcm/index.js（拉取 36 题）

Flutter：
- flutter_app/lib/services/api_service.dart（新增 getTcmQuestions）
- flutter_app/lib/screens/health/tcm_screen.dart（拉取 36 题 + option_index）
"""
import io
import os
import sys
import tarfile
import time

try:
    import paramiko
except ImportError:
    print("paramiko not installed; pip install paramiko")
    sys.exit(1)

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/{USER}/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

BACKEND_FILES = [
    "backend/app/models/models.py",
    "backend/app/schemas/function_button.py",
    "backend/app/schemas/tcm.py",
    "backend/app/api/tcm.py",
    "backend/app/api/questionnaire.py",
    "backend/app/services/constitution_score.py",
    "backend/app/services/prd_questionnaire_drawer_v1_migration.py",
    "backend/tests/test_constitution_score.py",
]
ADMIN_FILES = [
    "admin-web/src/app/(admin)/function-buttons/page.tsx",
]
H5_FILES = [
    "h5-web/src/app/tcm/page.tsx",
]


def ssh_exec(cli, cmd, timeout=900, quiet=False):
    if not quiet:
        print(f"$ {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out and not quiet:
        print(out)
    if err and not quiet:
        print("[stderr]", err)
    return code, out, err


def make_tar(items):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for rel in items:
            local = os.path.join(LOCAL_ROOT, rel)
            if not os.path.exists(local):
                print(f"[WARN] missing {local}")
                continue
            tf.add(local, arcname=rel)
    buf.seek(0)
    return buf.read()


def upload_bytes(cli, data, remote_path):
    sftp = cli.open_sftp()
    try:
        with sftp.open(remote_path, "wb") as f:
            f.write(data)
    finally:
        sftp.close()


def main():
    print(f"[deploy] connecting {HOST} ...")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    print("[deploy] connected.")

    # 1) Backend
    print("\n=== Phase 1: Backend ===")
    backend_tar = make_tar(BACKEND_FILES)
    print(f"backend tar size = {len(backend_tar)/1024:.1f} KiB")
    upload_bytes(cli, backend_tar, f"{REMOTE_BASE}/_drawer_v12_backend.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _drawer_v12_backend.tar.gz")
    backend_container = f"{DEPLOY_ID}-backend"
    for f in BACKEND_FILES:
        # backend/xxx -> /app/xxx
        target_in = f.replace("backend/", "")
        # mkdir -p container 内的父目录
        parent = os.path.dirname(target_in)
        if parent:
            ssh_exec(
                cli,
                f"docker exec {backend_container} mkdir -p /app/{parent}",
                quiet=True,
            )
        code, out, _ = ssh_exec(
            cli,
            f"docker cp {REMOTE_BASE}/{f} {backend_container}:/app/{target_in}",
            quiet=True,
        )
        if code != 0:
            print(f"[WARN] docker cp failed for {f}")
    ssh_exec(cli, f"docker restart {backend_container}", timeout=120)
    print("[deploy] waiting backend ready ...")
    ready = False
    for i in range(40):
        time.sleep(3)
        c, o, _ = ssh_exec(
            cli,
            f"docker logs --tail 30 {backend_container} 2>&1 | tail -n 30",
            quiet=True,
        )
        if "Application startup complete" in o or "Uvicorn running" in o:
            ready = True
            print(f"[deploy] backend ready after {(i+1)*3}s")
            print(o[-2000:])
            break
    if not ready:
        print("[deploy] backend not ready after 120s, fetching logs")
        ssh_exec(cli, f"docker logs --tail 80 {backend_container} 2>&1 | tail -n 80")

    # 验证迁移日志
    print("[deploy] migration log tail:")
    ssh_exec(
        cli,
        f"docker logs {backend_container} 2>&1 | grep -E 'questionnaire_drawer|migrate' | tail -n 30",
    )

    # 2) Admin-web
    print("\n=== Phase 2: Admin-web ===")
    admin_tar = make_tar(ADMIN_FILES)
    print(f"admin tar size = {len(admin_tar)/1024:.1f} KiB")
    upload_bytes(cli, admin_tar, f"{REMOTE_BASE}/_drawer_v12_admin.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _drawer_v12_admin.tar.gz")
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -n 30",
        timeout=900,
    )
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml up -d admin-web 2>&1 | tail -n 30",
        timeout=180,
    )

    # 3) H5-web
    print("\n=== Phase 3: H5-web ===")
    h5_tar = make_tar(H5_FILES)
    print(f"h5 tar size = {len(h5_tar)/1024:.1f} KiB")
    upload_bytes(cli, h5_tar, f"{REMOTE_BASE}/_drawer_v12_h5.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _drawer_v12_h5.tar.gz")
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -n 30",
        timeout=1500,
    )
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -n 30",
        timeout=180,
    )

    # 4) Smoke test
    print("\n=== Phase 4: Smoke ===")
    time.sleep(8)
    smoke_urls = [
        f"{BASE_URL}/api/openapi.json",
        f"{BASE_URL}/api/tcm/questions",
        f"{BASE_URL}/api/questionnaire/templates",
    ]
    for url in smoke_urls:
        code, out, _ = ssh_exec(
            cli, f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", quiet=True
        )
        print(f"  GET {url} => HTTP {out.strip()}")

    # 验证 questions 接口返回 36 题 + is_reverse_score 字段
    code, out, _ = ssh_exec(
        cli,
        f"curl -sk '{BASE_URL}/api/tcm/questions' | python3 -c "
        "\"import json,sys;d=json.load(sys.stdin);"
        "items=d.get('items',[]);"
        "print('count=', len(items));"
        "rev=[i for i in items if i.get('is_reverse_score')];"
        "print('reverse_count=', len(rev));"
        "print('reverse_order_nums=', sorted([i.get('order_num') for i in rev]))\"",
        quiet=False,
    )

    # 5) Remote pytest
    print("\n=== Phase 5: Remote pytest (constitution_score) ===")
    ssh_exec(
        cli,
        f"docker exec {backend_container} bash -lc "
        f"'cd /app && python -m pytest tests/test_constitution_score.py -v 2>&1 | tail -n 40'",
        timeout=300,
    )

    cli.close()
    print("\n[deploy] done.")


if __name__ == "__main__":
    main()
