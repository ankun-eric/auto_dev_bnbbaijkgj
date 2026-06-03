"""[BUGFIX HS-V2-ALTER 2026-05-28] 部署 schema_sync.py 防御性自动迁移 + 新测试到远端 backend 容器，
然后跑 home_safety 系列回归测试 + 重启 backend 容器并复测三个 API。"""
from _ssh_helper import get_client, run

REMOTE_TMP = "/tmp/hs_v2_alter_20260528"
CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

# 1. 上传两个文件
def upload():
    c = get_client()
    try:
        sftp = c.open_sftp()
        try:
            sftp.mkdir(REMOTE_TMP)
        except Exception:
            pass
        sftp.put("backend/app/services/schema_sync.py", f"{REMOTE_TMP}/schema_sync.py")
        sftp.put(
            "backend/tests/test_home_safety_callback_schema_sync_v1.py",
            f"{REMOTE_TMP}/test_home_safety_callback_schema_sync_v1.py",
        )
        sftp.close()
    finally:
        c.close()


def step(label, cmd, timeout=300):
    print(f"\n=== {label} ===")
    rc, out, err = run(cmd, timeout=timeout)
    print(out[-2000:] if out else "(no stdout)")
    if err:
        print("[stderr]", err[-2000:])
    print(f"[rc={rc}]")
    return rc


if __name__ == "__main__":
    print(">>> uploading files...")
    upload()
    print("uploaded.")

    step(
        "docker cp schema_sync.py -> container",
        f"docker cp {REMOTE_TMP}/schema_sync.py {CONTAINER}:/app/app/services/schema_sync.py",
        timeout=120,
    )
    step(
        "docker cp test file -> container",
        f"docker cp {REMOTE_TMP}/test_home_safety_callback_schema_sync_v1.py "
        f"{CONTAINER}:/app/tests/test_home_safety_callback_schema_sync_v1.py",
        timeout=120,
    )

    # 跑新增的回归测试
    step(
        "pytest schema_sync regression",
        f"docker exec {CONTAINER} sh -c 'cd /app && python -m pytest -x -q "
        f"tests/test_home_safety_callback_schema_sync_v1.py 2>&1 | tail -40'",
        timeout=300,
    )

    # 跑 home_safety 相关全部测试
    step(
        "pytest home_safety related",
        f"docker exec {CONTAINER} sh -c 'cd /app && python -m pytest -q "
        f"tests/test_home_safety_v1.py tests/test_home_safety_v2.py tests/test_home_safety_v2_revision.py "
        f"tests/test_home_safety_callback_schema_sync_v1.py 2>&1 | tail -60'",
        timeout=900,
    )

    # 重启 backend 让 lifespan 重新跑 schema_sync（验证我们新增的 ALTER 幂等执行）
    step(
        "docker restart backend",
        f"docker restart {CONTAINER}",
        timeout=120,
    )

    # 等 5 秒
    import time
    time.sleep(8)

    step(
        "verify backend logs after restart",
        f"docker logs --tail 30 {CONTAINER} 2>&1 | tail -30",
        timeout=60,
    )
