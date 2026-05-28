"""[PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 部署脚本

只动 4 个文件：
- backend/app/api/home_safety_v1.py            → docker cp 到 backend
- backend/app/services/schema_sync.py          → docker cp 到 backend
- backend/tests/test_home_safety_v1.py         → docker cp 到 backend /app/tests/
- backend/tests/test_home_safety_v2.py         → docker cp 到 backend /app/tests/
- backend/tests/test_home_safety_v2_revision.py→ docker cp 到 backend /app/tests/
- backend/tests/test_home_safety_gwid_ephone_v1.py → docker cp 到 backend /app/tests/
- h5-web/src/app/home-safety/page.tsx          → 需要 rebuild h5-web 镜像
- admin-web/src/app/(admin)/home-safety/page.tsx → 需要 rebuild admin-web 镜像

策略：
1) backend 走 docker cp 热更 + docker restart（最快）
2) h5-web / admin-web 走 docker compose build + up -d（Next.js standalone）
3) 部署后跑 pytest 做回归
"""
from __future__ import annotations
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_FILES = [
    # (local, remote_dest_on_host, container_dest_in_container, container_name)
    ("backend/app/api/home_safety_v1.py",
     f"{PROJECT_DIR}/backend/app/api/home_safety_v1.py",
     "/app/app/api/home_safety_v1.py",
     "backend"),
    ("backend/app/services/schema_sync.py",
     f"{PROJECT_DIR}/backend/app/services/schema_sync.py",
     "/app/app/services/schema_sync.py",
     "backend"),
    ("backend/tests/test_home_safety_v1.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_v1.py",
     "/app/tests/test_home_safety_v1.py",
     "backend"),
    ("backend/tests/test_home_safety_v2.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_v2.py",
     "/app/tests/test_home_safety_v2.py",
     "backend"),
    ("backend/tests/test_home_safety_v2_revision.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_v2_revision.py",
     "/app/tests/test_home_safety_v2_revision.py",
     "backend"),
    ("backend/tests/test_home_safety_gwid_ephone_v1.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_gwid_ephone_v1.py",
     "/app/tests/test_home_safety_gwid_ephone_v1.py",
     "backend"),
    # 前端走完整 rebuild，不需要 docker cp
    ("h5-web/src/app/home-safety/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/home-safety/page.tsx",
     None, None),
    ("admin-web/src/app/(admin)/home-safety/page.tsx",
     f"{PROJECT_DIR}/admin-web/src/app/(admin)/home-safety/page.tsx",
     None, None),
]


def ssh_connect():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PASSWORD,
                timeout=60, banner_timeout=60, auth_timeout=60,
                look_for_keys=False, allow_agent=False)
    cli.get_transport().set_keepalive(30)
    return cli


def sq(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


def run(cli, cmd, *, timeout=180, sudo=False, check=True, quiet=False):
    full = cmd
    if sudo:
        full = f"echo {sq(PASSWORD)} | sudo -S bash -lc {sq(cmd)}"
    if not quiet:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = cli.exec_command(full, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if not quiet:
        if out.strip():
            print(out[-3500:])
        if err.strip():
            print(f"[stderr] {err[-1500:]}")
        print(f"[rc={rc}]")
    if check and rc != 0:
        raise RuntimeError(f"cmd failed rc={rc}: {cmd}")
    return rc, out, err


def find_container(cli, prefix, kw):
    rc, out, _ = run(cli, "docker ps --format '{{.Names}}'", check=False, quiet=True)
    names = [n.strip() for n in out.splitlines() if n.strip()]
    for n in names:
        if kw in n.lower() and DEPLOY_ID in n:
            return n
    return None


def main():
    print(f"=== Connecting to {USER}@{HOST}:{PORT} ===")
    cli = ssh_connect()

    # 1) 上传源文件到宿主机
    print("\n=== 1. Upload source files to host ===")
    sftp = cli.open_sftp()
    for local, host_dst, _, _ in LOCAL_FILES:
        # 确保目录存在
        host_dir = host_dst.rsplit("/", 1)[0]
        run(cli, f"mkdir -p {host_dir}", check=False, quiet=True)
        # 上传
        print(f"  upload {local} -> {host_dst}")
        sftp.put(local, host_dst)
    sftp.close()

    # 2) 找到 backend 容器
    print("\n=== 2. Locate backend container ===")
    be = find_container(cli, DEPLOY_ID, "backend")
    if not be:
        # fallback 直接按 deploy_id 取
        be = f"{DEPLOY_ID}-backend"
    print(f"[+] backend = {be}")

    # 3) docker cp backend 文件
    print("\n=== 3. docker cp backend source files ===")
    for local, host_dst, container_dst, container in LOCAL_FILES:
        if not container_dst or container != "backend":
            continue
        print(f"  cp {host_dst} -> {be}:{container_dst}")
        run(cli, f"docker cp {host_dst} {be}:{container_dst}")

    # 4) restart backend
    print("\n=== 4. Restart backend ===")
    run(cli, f"docker restart {be}")
    # 等待 backend health
    for i in range(30):
        time.sleep(2)
        rc, out, _ = run(cli, f"docker exec {be} sh -c 'wget -qO- http://localhost:8000/api/health 2>&1 || echo NOTREADY'",
                         check=False, quiet=True)
        if "NOTREADY" not in out and out.strip():
            print(f"[+] backend ready: {out[:200]}")
            break
        print(f"[poll {i}] waiting backend ready ...")

    # 5) 跑 pytest（home_safety 全套）
    print("\n=== 5. Run pytest (home_safety 全套) ===")
    rc, out, err = run(
        cli,
        f"docker exec {be} sh -c 'cd /app && python -m pytest "
        f"tests/test_home_safety_v1.py "
        f"tests/test_home_safety_v2.py "
        f"tests/test_home_safety_v2_revision.py "
        f"tests/test_home_safety_callback_schema_sync_v1.py "
        f"tests/test_home_safety_gwid_ephone_v1.py "
        f"-v --tb=short 2>&1'",
        timeout=600, check=False,
    )
    print("\n=== pytest summary ===")
    # 打印最后 200 行
    lines = (out + err).splitlines()
    for l in lines[-200:]:
        print(l)
    if rc != 0:
        print(f"\n[!] pytest exited with rc={rc} — backend tests still pending; will continue with frontend rebuild")

    # 6) 重建 h5-web 和 admin-web
    print("\n=== 6. Rebuild h5-web ===")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -20", timeout=600)
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10", timeout=120)

    print("\n=== 7. Rebuild admin-web ===")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -20", timeout=600)
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d admin-web 2>&1 | tail -10", timeout=120)

    # 7) Smoke test
    print("\n=== 8. Smoke test ===")
    base = f"https://localhost/autodev/{DEPLOY_ID}"
    for path, label in [
        ("/api/health", "backend health"),
        ("/home-safety/", "H5 home-safety"),
        ("/admin/home-safety/", "Admin home-safety"),
        ("/api/home_safety/devices", "API devices (期望 401)"),
        ("/api/home_safety/devices/bind/defaults", "API bind defaults (期望 401)"),
    ]:
        run(cli, f"curl -sk -o /dev/null -w '{label} {path} -> %{{http_code}}\\n' --max-time 15 {base}{path}", check=False)

    cli.close()
    print("\n=== DEPLOY DONE ===")
    return rc


if __name__ == "__main__":
    try:
        rc = main()
        sys.exit(0 if rc == 0 else 2)
    except Exception as e:
        print(f"\n[FATAL] {e}", file=sys.stderr)
        sys.exit(1)
