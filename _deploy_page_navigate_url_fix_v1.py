"""[PRD-PAGE-NAVIGATE-EXTERNAL-URL-FIX-V1 2026-05-19] 自动化部署脚本

部署内容：
- admin-web/src/app/(admin)/function-buttons/page.tsx（F1 + F2 修复）
- h5-web/src/app/(ai-chat)/ai-home/page.tsx（F3 兜底）
- backend/tests/test_page_navigate_external_url_fix_v1_20260519.py（新增回归测试）

执行步骤：
1. 上传 backend 测试文件 → docker cp 进 backend 容器（不重启 backend，本次未改后端业务代码）
2. 上传 admin-web 改动 → 重建 admin-web 镜像 → 启动
3. 上传 h5-web 改动 → 重建 h5-web 镜像 → 启动
4. smoke：admin-web / h5-web 主页 HTTP 状态
5. 远端 pytest 仅跑本次新增测试文件
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
    "backend/tests/test_page_navigate_external_url_fix_v1_20260519.py",
]
ADMIN_FILES = [
    "admin-web/src/app/(admin)/function-buttons/page.tsx",
]
H5_FILES = [
    "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
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

    # 1) Backend tests
    print("\n=== Phase 1: Backend tests ===")
    backend_tar = make_tar(BACKEND_FILES)
    print(f"backend tar size = {len(backend_tar)/1024:.1f} KiB")
    upload_bytes(cli, backend_tar, f"{REMOTE_BASE}/_pnurl_backend.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _pnurl_backend.tar.gz")
    for f in BACKEND_FILES:
        code, out, _ = ssh_exec(
            cli,
            f"docker cp {REMOTE_BASE}/{f} {backend_container}:/app/{f.replace('backend/', '')}",
            quiet=True,
        )
        if code != 0:
            print(f"[WARN] docker cp failed for {f}")

    # 2) Admin-web
    print("\n=== Phase 2: Admin-web rebuild ===")
    admin_tar = make_tar(ADMIN_FILES)
    print(f"admin tar size = {len(admin_tar)/1024:.1f} KiB")
    upload_bytes(cli, admin_tar, f"{REMOTE_BASE}/_pnurl_admin.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _pnurl_admin.tar.gz")
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -n 30",
        timeout=900,
    )
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml up -d admin-web 2>&1 | tail -n 20",
        timeout=180,
    )

    # 3) H5-web
    print("\n=== Phase 3: H5-web rebuild ===")
    h5_tar = make_tar(H5_FILES)
    print(f"h5 tar size = {len(h5_tar)/1024:.1f} KiB")
    upload_bytes(cli, h5_tar, f"{REMOTE_BASE}/_pnurl_h5.tar.gz")
    ssh_exec(cli, f"cd {REMOTE_BASE} && tar -xzf _pnurl_h5.tar.gz")
    code, out, err = ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -n 30",
        timeout=1800,
    )
    if code != 0:
        print("[deploy] h5 build failed")
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -n 20",
        timeout=180,
    )

    # 4) Smoke
    print("\n=== Phase 4: Smoke ===")
    print("[deploy] waiting 10s for nginx to pick up ...")
    time.sleep(10)
    smoke_urls = [
        f"{BASE_URL}/api/openapi.json",
        f"{BASE_URL}/admin/function-buttons",
        f"{BASE_URL}/ai-home",
        f"{BASE_URL}/api/function-buttons?position=grid",
    ]
    for url in smoke_urls:
        code, out, _ = ssh_exec(
            cli, f"curl -sk -o /dev/null -w '%{{http_code}}' '{url}'", quiet=True
        )
        print(f"  GET {url} => HTTP {out.strip()}")

    # 5) Remote pytest
    print("\n=== Phase 5: Remote pytest ===")
    code, out, err = ssh_exec(
        cli,
        f"docker exec {backend_container} bash -lc "
        f"'cd /app && python -m pytest tests/test_page_navigate_external_url_fix_v1_20260519.py -v 2>&1 | tail -n 120'",
        timeout=300,
    )

    cli.close()
    print("\n[deploy] done.")


if __name__ == "__main__":
    main()
