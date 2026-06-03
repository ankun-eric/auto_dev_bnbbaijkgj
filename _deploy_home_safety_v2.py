"""[PRD-HOME-SAFETY-V2 2026-05-27] 部署脚本：上传关键文件 + 重建容器 + 运行测试"""
import sys
import time
from _ssh_helper import get_client, run, put_file

REMOTE_BASE = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

FILES = [
    ("backend/app/api/home_safety_v1.py", f"{REMOTE_BASE}/backend/app/api/home_safety_v1.py"),
    ("backend/app/services/schema_sync.py", f"{REMOTE_BASE}/backend/app/services/schema_sync.py"),
    ("backend/tests/test_home_safety_v2.py", f"{REMOTE_BASE}/backend/tests/test_home_safety_v2.py"),
    ("admin-web/src/app/(admin)/home-safety/page.tsx", f"{REMOTE_BASE}/admin-web/src/app/(admin)/home-safety/page.tsx"),
]


def main():
    print("=== Step 1: Upload files ===")
    for local, remote in FILES:
        print(f"  -> {remote}")
        put_file(local, remote)
    print("Upload done.")

    print("\n=== Step 2: Verify httpx in backend container ===")
    rc, out, err = run(
        f"cd {REMOTE_BASE} && sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -c 'import httpx; print(httpx.__version__)'",
        timeout=60,
    )
    print("httpx:", out.strip(), err.strip())

    print("\n=== Step 3: Rebuild + restart backend container ===")
    rc, out, err = run(
        f"cd {REMOTE_BASE} && sudo docker compose -f docker-compose.prod.yml up -d --build backend 2>&1 | tail -50",
        timeout=600,
    )
    print(out)
    if err:
        print("STDERR:", err[-1000:])

    print("\n=== Step 4: Wait for backend healthy ===")
    for i in range(30):
        rc, out, err = run(
            "sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend curl -fs http://localhost:8000/docs >/dev/null && echo OK || echo NOTREADY",
            timeout=15,
        )
        if "OK" in out:
            print(f"  ready at iter {i}")
            break
        time.sleep(3)
    else:
        print("  WARNING: backend not ready after 90s")

    print("\n=== Step 5: Run v1 + v2 home_safety tests inside backend container ===")
    rc, out, err = run(
        "sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -m pytest tests/test_home_safety_v1.py tests/test_home_safety_v2.py -v --tb=short 2>&1 | tail -200",
        timeout=600,
    )
    print(out)
    if err:
        print("STDERR:", err[-2000:])
    return rc


if __name__ == "__main__":
    sys.exit(main())
