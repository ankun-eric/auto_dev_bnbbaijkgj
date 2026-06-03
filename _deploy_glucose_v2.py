"""[PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30] 远程部署：
1) 上传文件到 /tmp
2) docker cp 到容器
3) 重启容器
4) 烟测
"""
import os
import time
import paramiko
import posixpath

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

BACKEND_CTN = f"{DEPLOY_ID}-backend"
H5_CTN = f"{DEPLOY_ID}-h5"

# (local_path, container_path)
BACKEND_FILES = [
    ("backend/app/api/glucose_v1.py", "/app/app/api/glucose_v1.py"),
    ("backend/app/api/health_profile_v3.py", "/app/app/api/health_profile_v3.py"),
    ("backend/app/main.py", "/app/app/main.py"),
    ("backend/tests/test_glucose_card_optimize_v2.py", "/app/tests/test_glucose_card_optimize_v2.py"),
    ("backend/tests/test_glucose_v1_20260530.py", "/app/tests/test_glucose_v1_20260530.py"),
]

H5_FILES = [
    ("h5-web/src/lib/bg-level.ts", "/app/src/lib/bg-level.ts"),
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
        # ensure remote dir
        try:
            sftp.mkdir(posixpath.dirname(remote))
        except Exception:
            pass
        sftp.put(local, remote)
        print(f"  + {local} -> {remote}")
    finally:
        sftp.close()


def docker_cp_into(c, ctn, tmp_remote, container_path):
    # docker cp src ctn:dst
    run(c, f"docker cp {tmp_remote} {ctn}:{container_path}")


def deploy_backend(c):
    print("\n=== Deploy Backend ===")
    for local, ctn_path in BACKEND_FILES:
        if not os.path.exists(local):
            print(f"  skip missing: {local}")
            continue
        remote_tmp = f"/tmp/_glucose_v2_{os.path.basename(local)}"
        upload(c, local, remote_tmp)
        docker_cp_into(c, BACKEND_CTN, remote_tmp, ctn_path)
        run(c, f"rm -f {remote_tmp}")
    print("\n>>> Restarting backend ...")
    run(c, f"docker restart {BACKEND_CTN}")
    # 等待启动
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
    # 检查 h5 容器是 next dev 还是 static build
    rc, o, _ = run(c, f"docker exec {H5_CTN} ls /app/.next 2>/dev/null | head -3", timeout=15)
    rc2, o2, _ = run(c, f"docker exec {H5_CTN} cat /proc/1/cmdline 2>/dev/null", timeout=10)
    print(f"H5 process cmdline: {o2}")

    for local, ctn_path in H5_FILES:
        if not os.path.exists(local):
            continue
        remote_tmp = f"/tmp/_glucose_v2_h5_{os.path.basename(local)}"
        upload(c, local, remote_tmp)
        docker_cp_into(c, H5_CTN, remote_tmp, ctn_path)
        run(c, f"rm -f {remote_tmp}")

    # next dev 模式下文件改动自动 reload；next start 需 rebuild
    if "next-server" in o2 or "next start" in o2 or "production" in o2:
        print(">>> Production mode detected, rebuilding next ...")
        rc, o, _ = run(c, f"docker exec {H5_CTN} sh -c 'cd /app && npm run build' 2>&1 | tail -30", timeout=600)
        run(c, f"docker restart {H5_CTN}")
        time.sleep(10)
    else:
        print(">>> Dev mode - reloading via touch")
        run(c, f"docker exec {H5_CTN} touch /app/src/app/health-metric/\\[type\\]/page.tsx")
    print("H5 deploy done")


def smoke_test(c):
    print("\n=== Smoke Test ===")
    # 1) /api/glucose-v1/admin/ai-prompts （无需认证）
    rc, o, _ = run(c, f"curl -fsS '{BASE_URL}/api/glucose-v1/admin/ai-prompts'", timeout=30)
    if "glucose_single_explain" in o and "glucose_trend_explain" in o:
        print(">>> AC-11 PASSED: ai-prompts 列表返回两条记录")
    else:
        print(">>> AC-11 FAIL")
        print(o[:500])

    # 2) front page
    rc, o, _ = run(c, f"curl -fsS -o /dev/null -w 'HTTP=%{{http_code}}' '{BASE_URL}/'", timeout=30)
    print(f">>> Front HTTP: {o}")

    # 3) glucose v1 健康
    rc, o, _ = run(c, f"docker exec {BACKEND_CTN} curl -fsS http://127.0.0.1:8000/health || echo FAILED", timeout=15)
    print(f">>> Backend internal health: {o[:200]}")


def run_tests_in_container(c):
    """在容器内跑 PRD 验收测试。"""
    print("\n=== Run in-container pytest ===")
    rc, o, e = run(c,
        f"docker exec {BACKEND_CTN} sh -c 'cd /app && python -m pytest tests/test_glucose_card_optimize_v2.py "
        f"tests/test_glucose_v1_20260530.py --tb=short -q 2>&1 | tail -20'", timeout=300)
    return rc, o


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    c = conn()
    try:
        if cmd in ("all", "backend"):
            deploy_backend(c)
        if cmd in ("all", "h5"):
            deploy_h5(c)
        if cmd in ("all", "smoke"):
            smoke_test(c)
        if cmd in ("test",):
            run_tests_in_container(c)
    finally:
        c.close()
