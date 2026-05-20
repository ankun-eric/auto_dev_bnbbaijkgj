"""[PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 自动化部署脚本

部署内容：
- backend/app/models/models.py
- backend/app/schemas/function_button.py
- backend/app/schemas/questionnaire.py
- backend/app/api/function_button.py
- backend/app/api/questionnaire.py
- backend/app/api/health_self_check.py（仅 deprecation 注释）
- backend/app/main.py
- backend/app/services/prd_questionnaire_drawer_v1_migration.py（新增）
- backend/tests/test_questionnaire_drawer_v1_20260519.py（新增）
- admin-web/src/app/(admin)/function-buttons/page.tsx
- admin-web/src/app/(admin)/questionnaire-templates/page.tsx
- h5-web/src/app/(ai-chat)/ai-home/page.tsx
- h5-web/src/components/ai-chat/QuestionnaireDrawer.tsx（新增）
- h5-web/src/components/ai-chat/QuestionnaireResultCard.tsx（新增）

执行步骤：
1. tar 上传所有改动 → 解包覆盖
2. 重启 backend → 等待 ready → 看启动期迁移日志
3. 重建 admin-web 镜像（按需）
4. 重建 h5-web 镜像
5. smoke test：openapi.json / /api/questionnaire/templates / render-meta 路由可达性
6. 远端 pytest 仅跑本次新增的测试文件
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
    "backend/app/schemas/questionnaire.py",
    "backend/app/api/function_button.py",
    "backend/app/api/questionnaire.py",
    "backend/app/api/health_self_check.py",
    "backend/app/main.py",
    "backend/app/services/prd_questionnaire_drawer_v1_migration.py",
    "backend/tests/test_questionnaire_drawer_v1_20260519.py",
]
ADMIN_FILES = [
    "admin-web/src/app/(admin)/function-buttons/page.tsx",
    "admin-web/src/app/(admin)/questionnaire-templates/page.tsx",
]
H5_FILES = [
    "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    "h5-web/src/components/ai-chat/QuestionnaireDrawer.tsx",
    "h5-web/src/components/ai-chat/QuestionnaireResultCard.tsx",
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
    upload_bytes(cli, backend_tar, f"{REMOTE_BASE}/_qn_drawer_backend.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _qn_drawer_backend.tar.gz")
    # docker cp 到 backend 容器（在容器里手动重启，避免重建镜像）
    backend_container = f"{DEPLOY_ID}-backend"
    for f in BACKEND_FILES:
        code, out, _ = ssh_exec(
            cli,
            f"docker cp {REMOTE_BASE}/{f} {backend_container}:/app/{f.replace('backend/', '')}",
            quiet=True,
        )
        if code != 0:
            print(f"[WARN] docker cp failed for {f}")
    ssh_exec(cli, f"docker restart {backend_container}", timeout=120)
    # 等待 ready
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
            print(o[-1500:])
            break
    if not ready:
        print("[deploy] backend not ready after 120s, continue anyway")

    # 2) Admin-web
    print("\n=== Phase 2: Admin-web ===")
    admin_tar = make_tar(ADMIN_FILES)
    print(f"admin tar size = {len(admin_tar)/1024:.1f} KiB")
    upload_bytes(cli, admin_tar, f"{REMOTE_BASE}/_qn_drawer_admin.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _qn_drawer_admin.tar.gz")
    code, out, err = ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -n 50",
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
    upload_bytes(cli, h5_tar, f"{REMOTE_BASE}/_qn_drawer_h5.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _qn_drawer_h5.tar.gz")
    code, out, err = ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -n 50",
        timeout=1500,
    )
    if code != 0:
        print("[deploy] h5 build failed")
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -n 30",
        timeout=180,
    )

    # 4) Wait services & smoke test
    print("\n=== Phase 4: Smoke ===")
    print("[deploy] waiting 8s for nginx to pick up ...")
    time.sleep(8)
    # 内部 curl，确保走容器网络
    smoke_urls = [
        f"{BASE_URL}/api/openapi.json",
        f"{BASE_URL}/api/questionnaire/templates",
    ]
    for url in smoke_urls:
        code, out, _ = ssh_exec(
            cli, f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", quiet=True
        )
        print(f"  GET {url} => HTTP {out.strip()}")

    # render-meta：先取一个 questionnaire 类型按钮 ID
    code, out, _ = ssh_exec(
        cli,
        f"docker exec {DEPLOY_ID}-mysql mysql -uroot -p888888 bini_health "
        f"-Nse \"SELECT id FROM chat_function_buttons "
        f"WHERE ai_function_type='questionnaire' ORDER BY id LIMIT 1\" 2>/dev/null",
        quiet=True,
    )
    btn_id = (out or "").strip().splitlines()[-1].strip() if out else ""
    if btn_id and btn_id.isdigit():
        code, out, _ = ssh_exec(
            cli,
            f"curl -sk -o /dev/null -w '%{{http_code}}' "
            f"'{BASE_URL}/api/questionnaire/buttons/{btn_id}/render-meta'",
            quiet=True,
        )
        print(f"  GET render-meta(btn={btn_id}) => HTTP {out.strip()}")
    else:
        print("  (no questionnaire button found yet; skip render-meta smoke)")

    # 5) Remote pytest
    print("\n=== Phase 5: Remote pytest ===")
    code, out, err = ssh_exec(
        cli,
        f"docker exec {backend_container} bash -lc "
        f"'cd /app && python -m pytest tests/test_questionnaire_drawer_v1_20260519.py -v 2>&1 | tail -n 60'",
        timeout=300,
    )

    cli.close()
    print("\n[deploy] done.")


if __name__ == "__main__":
    main()
