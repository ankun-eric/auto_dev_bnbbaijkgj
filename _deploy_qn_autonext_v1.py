"""[PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 自动下一步配置 + BUG-2 体质测评生成失败 修复部署

部署步骤：
1. 上传后端 + H5 + Admin Web 修改文件
2. docker cp 到 backend 容器（无需 build），重启触发迁移
3. 重建 H5 + Admin 镜像
4. smoke 测试关键 API
5. 远端 pytest 跑本次新增测试
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
    "backend/app/api/function_button.py",
    "backend/app/api/questionnaire.py",
    "backend/app/api/tcm.py",
    "backend/app/main.py",
    "backend/app/services/prd_questionnaire_autonext_v1_migration.py",
    "backend/tests/test_questionnaire_autonext_v1_20260520.py",
]
ADMIN_FILES = [
    "admin-web/src/app/(admin)/function-buttons/page.tsx",
]
H5_FILES = [
    "h5-web/src/components/ai-chat/QuestionnaireDrawer.tsx",
    "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
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

    backend_container = f"{DEPLOY_ID}-backend"

    # ── 1) Backend ─────────────────────────────────────────
    print("\n=== Phase 1: Backend ===")
    backend_tar = make_tar(BACKEND_FILES)
    print(f"backend tar size = {len(backend_tar)/1024:.1f} KiB")
    upload_bytes(cli, backend_tar, f"{REMOTE_BASE}/_autonext_backend.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _autonext_backend.tar.gz")
    # docker cp 到 backend 容器
    for f in BACKEND_FILES:
        in_container_path = "/app/" + f.replace("backend/", "")
        code, _, _ = ssh_exec(
            cli,
            f"docker cp {REMOTE_BASE}/{f} {backend_container}:{in_container_path}",
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
            f"docker logs --tail 80 {backend_container} 2>&1 | tail -n 80",
            quiet=True,
        )
        if "Application startup complete" in o or "Uvicorn running" in o:
            ready = True
            print(f"[deploy] backend ready after {(i+1)*3}s")
            print(o[-2500:])
            break
    if not ready:
        print("[deploy] backend not ready after 120s, continue anyway")

    # 显示迁移日志（关键）
    print("\n=== 迁移日志 ===")
    _, mout, _ = ssh_exec(
        cli,
        f"docker logs --tail 200 {backend_container} 2>&1 | "
        f"grep -E 'questionnaire_autonext_v1|presentation_container|auto_next' | tail -30",
        quiet=True,
    )
    print(mout or "(no migration log lines yet)")

    # ── 2) Admin-web ───────────────────────────────────────
    print("\n=== Phase 2: Admin-web ===")
    admin_tar = make_tar(ADMIN_FILES)
    print(f"admin tar size = {len(admin_tar)/1024:.1f} KiB")
    upload_bytes(cli, admin_tar, f"{REMOTE_BASE}/_autonext_admin.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _autonext_admin.tar.gz")
    code, out, err = ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -n 30",
        timeout=900,
    )
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml up -d admin-web 2>&1 | tail -n 20",
        timeout=180,
    )

    # ── 3) H5-web ──────────────────────────────────────────
    print("\n=== Phase 3: H5-web ===")
    h5_tar = make_tar(H5_FILES)
    print(f"h5 tar size = {len(h5_tar)/1024:.1f} KiB")
    upload_bytes(cli, h5_tar, f"{REMOTE_BASE}/_autonext_h5.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _autonext_h5.tar.gz")
    code, out, err = ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -n 30",
        timeout=1500,
    )
    if code != 0:
        print("[deploy] h5 build failed")
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -n 20",
        timeout=180,
    )

    # ── 4) Smoke ───────────────────────────────────────────
    print("\n=== Phase 4: Smoke ===")
    print("[deploy] waiting 10s for nginx ...")
    time.sleep(10)
    smoke_urls = [
        f"{BASE_URL}/api/openapi.json",
        f"{BASE_URL}/api/questionnaire/templates",
    ]
    for url in smoke_urls:
        code, out, _ = ssh_exec(
            cli, f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", quiet=True
        )
        print(f"  GET {url} => HTTP {out.strip()}")

    # 取一个 questionnaire 按钮的 render-meta，看 auto_next_enabled / questions_per_page 字段
    code, out, _ = ssh_exec(
        cli,
        f"docker exec {DEPLOY_ID}-db sh -c \"mysql -uroot -proot bini_health -N -e "
        f"\\\"SELECT id FROM chat_function_buttons WHERE ai_function_type='questionnaire' "
        f"AND questionnaire_template_id IS NOT NULL ORDER BY id ASC LIMIT 1;\\\"\" 2>/dev/null",
        quiet=True,
    )
    btn_id = (out or "").strip().split("\n")[-1].strip()
    if btn_id and btn_id.isdigit():
        url = f"{BASE_URL}/api/questionnaire/buttons/{btn_id}/render-meta"
        code, out, _ = ssh_exec(cli, f"curl -sk '{url}'", quiet=True)
        print(f"  GET render-meta(id={btn_id}) =>")
        print(out[:1500] if out else "(empty)")
    else:
        print("  no questionnaire button found")

    # 5) 远端 pytest
    print("\n=== Phase 5: Remote pytest ===")
    test_files = [
        "tests/test_questionnaire_autonext_v1_20260520.py",
    ]
    test_cmd = (
        f"docker exec {backend_container} sh -c "
        f"'cd /app && PYTHONPATH=/app python -m pytest -v "
        + " ".join(test_files) + " 2>&1 | tail -n 120'"
    )
    ssh_exec(cli, test_cmd, timeout=600)

    cli.close()
    print("\n[deploy] DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
