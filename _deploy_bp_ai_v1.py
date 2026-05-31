"""[PRD-BP-AI-EXPLAIN-V1 2026-05-31] 远程部署：
1) 上传 backend/app/api/bp_v1.py + backend/app/main.py + 测试文件 -> docker cp
2) 上传 H5 page.tsx -> docker cp，并按模式 reload / rebuild
3) 重启后端
4) 烟测
5) 容器内 pytest
"""
import os
import time
import sys
import paramiko
import posixpath

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

BACKEND_CTN = f"{DEPLOY_ID}-backend"
H5_CTN = f"{DEPLOY_ID}-h5"

BACKEND_FILES = [
    ("backend/app/api/bp_v1.py", "/app/app/api/bp_v1.py"),
    ("backend/app/main.py", "/app/app/main.py"),
    ("backend/tests/test_bp_ai_v1_20260531.py", "/app/tests/test_bp_ai_v1_20260531.py"),
]

H5_FILES = [
    ("h5-web/src/app/health-metric/[type]/page.tsx", "/app/src/app/health-metric/[type]/page.tsx"),
]


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def run(c, cmd, timeout=120):
    print(f"$ {cmd}")
    si, so, se = c.exec_command(cmd, timeout=timeout)
    o = so.read().decode("utf-8", errors="ignore")
    e = se.read().decode("utf-8", errors="ignore")
    rc = so.channel.recv_exit_status()
    if o:
        print(o.rstrip())
    if e:
        print("STDERR:", e.rstrip())
    return rc, o, e


def upload(c, local, remote):
    sftp = c.open_sftp()
    try:
        try:
            sftp.mkdir(posixpath.dirname(remote))
        except Exception:
            pass
        sftp.put(local, remote)
        print(f"  + {local} -> {remote}")
    finally:
        sftp.close()


def deploy_backend(c):
    print("\n=== Deploy Backend ===")
    for local, ctn_path in BACKEND_FILES:
        if not os.path.exists(local):
            print(f"  skip missing: {local}")
            continue
        remote_tmp = f"/tmp/_bp_ai_{os.path.basename(local)}"
        upload(c, local, remote_tmp)
        run(c, f"docker cp {remote_tmp} {BACKEND_CTN}:{ctn_path}")
        run(c, f"rm -f {remote_tmp}")
    print(">>> Restarting backend ...")
    run(c, f"docker restart {BACKEND_CTN}")
    print(">>> Waiting for backend ...")
    for i in range(30):
        time.sleep(2)
        rc, o, _ = run(c, f"docker exec {BACKEND_CTN} curl -fsS http://127.0.0.1:8000/health 2>/dev/null || true", timeout=10)
        if rc == 0 and o.strip():
            print(f"Backend ready after {(i+1)*2}s")
            break
    else:
        print("Backend may still be starting...")


def deploy_h5(c):
    print("\n=== Deploy H5 ===")
    rc2, cmdline, _ = run(c, f"docker exec {H5_CTN} cat /proc/1/cmdline 2>/dev/null", timeout=10)
    print(f"H5 process cmdline: {cmdline}")

    for local, ctn_path in H5_FILES:
        if not os.path.exists(local):
            continue
        remote_tmp = f"/tmp/_bp_ai_h5_{os.path.basename(local)}"
        upload(c, local, remote_tmp)
        run(c, f"docker cp {remote_tmp} {H5_CTN}:{ctn_path}")
        run(c, f"rm -f {remote_tmp}")

    if "next-server" in cmdline or "next start" in cmdline or "production" in cmdline:
        print(">>> Production mode detected, rebuilding next ...")
        run(c, f"docker exec {H5_CTN} sh -c 'cd /app && npm run build' 2>&1 | tail -40", timeout=900)
        run(c, f"docker restart {H5_CTN}")
        time.sleep(10)
    else:
        print(">>> Dev mode - reloading via touch")
        run(c, f"docker exec {H5_CTN} touch '/app/src/app/health-metric/[type]/page.tsx'")
    print("H5 deploy done")


def smoke_test(c):
    print("\n=== Smoke Test ===")
    # 1) BP AI endpoint exists, unauthenticated -> 401 (proves route registered)
    rc, o, _ = run(
        c,
        f"curl -fsS -o /dev/null -w 'HTTP=%{{http_code}}' -X POST "
        f"'{BASE_URL}/api/bp-v1/ai-explain-single' "
        f"-H 'Content-Type: application/json' -d '{{\"record_id\":1,\"profile_id\":1}}'",
        timeout=30,
    )
    print(f">>> bp-v1 ai-explain-single HTTP: {o}")

    rc, o, _ = run(
        c,
        f"curl -fsS -o /dev/null -w 'HTTP=%{{http_code}}' -X POST "
        f"'{BASE_URL}/api/bp-v1/ai-explain-trend' "
        f"-H 'Content-Type: application/json' -d '{{\"range\":\"7d\",\"profile_id\":1}}'",
        timeout=30,
    )
    print(f">>> bp-v1 ai-explain-trend HTTP: {o}")

    # 2) front pages
    for path in ["/", "/health-metric/blood_pressure", "/health-metric/blood_pressure/history"]:
        rc, o, _ = run(c, f"curl -fsS -o /dev/null -w 'HTTP=%{{http_code}}' '{BASE_URL}{path}'", timeout=30)
        print(f">>> {path} HTTP: {o}")


def run_tests_in_container(c):
    print("\n=== Run in-container pytest ===")
    rc, o, e = run(
        c,
        f"docker exec {BACKEND_CTN} sh -c 'cd /app && python -m pytest "
        f"tests/test_bp_ai_v1_20260531.py "
        f"tests/test_glucose_v1_20260530.py "
        f"--tb=short -q 2>&1 | tail -80'",
        timeout=600,
    )
    return rc, o


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    c = conn()
    try:
        if cmd in ("all", "backend"):
            deploy_backend(c)
        if cmd in ("all", "h5"):
            deploy_h5(c)
        if cmd in ("all", "smoke"):
            smoke_test(c)
        if cmd in ("all", "test"):
            run_tests_in_container(c)
    finally:
        c.close()
