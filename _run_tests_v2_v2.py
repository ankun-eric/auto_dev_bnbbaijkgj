"""上传源码到宿主机 + docker cp 进容器 + 跑测试"""
import paramiko
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"
BE_CONTAINER = f"{DEPLOY_ID}-backend"

FILES = [
    ("backend/app/api/home_safety_v1.py", "/app/app/api/home_safety_v1.py"),
    ("backend/tests/test_home_safety_v2_revision.py", "/app/tests/test_home_safety_v2_revision.py"),
    ("backend/tests/test_home_safety_v1.py", "/app/tests/test_home_safety_v1.py"),
]


def run(c, cmd, t=600):
    print(f"$ {cmd}")
    _, o, _ = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    if out.strip():
        print(out)
    return out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = c.open_sftp()
    for local, _ in FILES:
        remote = f"{REMOTE_BASE}/{local}"
        rdir = remote.rsplit("/", 1)[0]
        run(c, f"mkdir -p '{rdir}'")
        if os.path.exists(local):
            sftp.put(local, remote)
            print(f"[uploaded] {local}")
    sftp.close()

    # docker cp 进容器
    for local, container_path in FILES:
        host_path = f"{REMOTE_BASE}/{local}"
        run(c, f"docker cp {host_path} {BE_CONTAINER}:{container_path}")

    # 重启 backend（让新代码生效）
    run(c, f"docker restart {BE_CONTAINER}")
    import time
    time.sleep(8)
    # 等 backend 就绪
    for _ in range(10):
        out = run(c, f"docker logs --tail=5 {BE_CONTAINER}")
        if "Application startup complete" in out or "Uvicorn running" in out:
            break
        time.sleep(3)

    # docker exec 跑测试
    cmd = (
        f"docker exec {BE_CONTAINER} "
        f"python -m pytest tests/test_home_safety_v1.py tests/test_home_safety_v2_revision.py "
        f"-v --tb=short 2>&1 | tail -120"
    )
    run(c, cmd, t=600)
    c.close()


if __name__ == "__main__":
    main()
