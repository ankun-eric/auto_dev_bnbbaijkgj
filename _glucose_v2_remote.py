"""[PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30] 远程 helper：检查 + 拷贝 + 重启 + 验证。

用法：
  python _glucose_v2_remote.py status        # 查看当前部署
  python _glucose_v2_remote.py copy-backend  # 拷贝 backend 改动
  python _glucose_v2_remote.py copy-h5       # 拷贝 H5 改动
  python _glucose_v2_remote.py restart       # 重启 backend / h5
  python _glucose_v2_remote.py smoke         # 接口烟测
"""
import io
import sys
import os
import time
import paramiko
import posixpath

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def run(c, cmd, hide=False):
    if not hide:
        print(f"$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=180)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    rc = stdout.channel.recv_exit_status()
    if out and not hide:
        print(out.rstrip())
    if err and not hide:
        print("STDERR:", err.rstrip())
    return rc, out, err


def status():
    c = conn()
    print(f"=== Containers for {DEPLOY_ID} ===")
    run(c, f"docker ps -a --format '{{{{.Names}}}}\\t{{{{.Image}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID} || echo NONE")
    print(f"\n=== Project dirs ===")
    run(c, f"ls -la /home/ubuntu/autodev/{DEPLOY_ID}/ 2>/dev/null || echo NO_DIR")
    print(f"\n=== Gateway nginx ===")
    run(c, "docker ps --format '{{.Names}}' | grep -i 'gateway\\|nginx' | head -5")
    c.close()


def upload(c, local_path, remote_path):
    """Upload single file via SFTP."""
    sftp = c.open_sftp()
    try:
        # mkdir -p remote dir
        remote_dir = posixpath.dirname(remote_path)
        # ensure dir exists
        parts = remote_dir.split("/")
        cur = ""
        for p in parts:
            if not p:
                cur += "/"
                continue
            cur = posixpath.join(cur, p) if cur else "/" + p
            try:
                sftp.stat(cur)
            except IOError:
                try:
                    sftp.mkdir(cur)
                except Exception:
                    pass
        sftp.put(local_path, remote_path)
        print(f"  uploaded: {local_path} -> {remote_path}")
    finally:
        sftp.close()


BACKEND_FILES = [
    ("backend/app/api/glucose_v1.py", f"/home/ubuntu/autodev/{DEPLOY_ID}/backend/app/api/glucose_v1.py"),
    ("backend/app/api/health_profile_v3.py", f"/home/ubuntu/autodev/{DEPLOY_ID}/backend/app/api/health_profile_v3.py"),
    ("backend/app/main.py", f"/home/ubuntu/autodev/{DEPLOY_ID}/backend/app/main.py"),
    ("backend/tests/test_glucose_card_optimize_v2.py", f"/home/ubuntu/autodev/{DEPLOY_ID}/backend/tests/test_glucose_card_optimize_v2.py"),
    ("backend/tests/test_glucose_v1_20260530.py", f"/home/ubuntu/autodev/{DEPLOY_ID}/backend/tests/test_glucose_v1_20260530.py"),
]


H5_FILES = [
    ("h5-web/src/lib/bg-level.ts", f"/home/ubuntu/autodev/{DEPLOY_ID}/h5-web/src/lib/bg-level.ts"),
    ("h5-web/src/app/health-metric/[type]/page.tsx", f"/home/ubuntu/autodev/{DEPLOY_ID}/h5-web/src/app/health-metric/[type]/page.tsx"),
]


def copy_backend():
    c = conn()
    for local, remote in BACKEND_FILES:
        full_local = os.path.join(os.getcwd(), local.replace("/", os.sep))
        if not os.path.exists(full_local):
            print(f"  skip (missing): {full_local}")
            continue
        upload(c, full_local, remote)
    c.close()


def copy_h5():
    c = conn()
    for local, remote in H5_FILES:
        full_local = os.path.join(os.getcwd(), local.replace("/", os.sep))
        if not os.path.exists(full_local):
            print(f"  skip (missing): {full_local}")
            continue
        upload(c, full_local, remote)
    c.close()


def find_backend_container(c):
    rc, out, _ = run(c, f"docker ps --format '{{{{.Names}}}}' | grep {DEPLOY_ID} | grep -i 'backend\\|api' | head -1", hide=True)
    name = (out or "").strip()
    if not name:
        # 找任意 backend 容器
        rc, out, _ = run(c, f"docker ps --format '{{{{.Names}}}}' | grep {DEPLOY_ID} | head -5", hide=True)
        print("Containers:", out)
    return name


def find_h5_container(c):
    rc, out, _ = run(c, f"docker ps --format '{{{{.Names}}}}' | grep {DEPLOY_ID} | grep -i 'h5\\|frontend\\|web' | head -1", hide=True)
    return (out or "").strip()


def restart():
    c = conn()
    backend = find_backend_container(c)
    h5 = find_h5_container(c)
    print(f"Backend: {backend}")
    print(f"H5: {h5}")
    if backend:
        run(c, f"docker restart {backend}")
        print("Waiting backend startup ...")
        time.sleep(15)
    if h5:
        run(c, f"docker restart {h5}")
        time.sleep(10)
    c.close()


def smoke():
    """Smoke test via curl on server (internal network)."""
    c = conn()
    # 1) backend health (内部) — 通过 nginx
    backend = find_backend_container(c)
    print(f"Backend container: {backend}")
    if backend:
        run(c, f"docker exec {backend} curl -fsS http://127.0.0.1:8000/health 2>&1 | head -5 || true")
        run(c, f"docker exec {backend} curl -fsS -X GET http://127.0.0.1:8000/api/glucose-v1/admin/ai-prompts 2>&1 | head -10 || true")

    # 2) 外部访问网关
    print("\n=== External via gateway ===")
    run(c, f"curl -fsS -o /dev/null -w 'HTTP=%{{http_code}}\\n' '{BASE_URL}/'")
    run(c, f"curl -fsS '{BASE_URL}/api/glucose-v1/admin/ai-prompts' 2>&1 | head -20 || true")
    c.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {
        "status": status,
        "copy-backend": copy_backend,
        "copy-h5": copy_h5,
        "restart": restart,
        "smoke": smoke,
    }.get(cmd, status)()
