"""[PRD-405] 部署脚本：上传后端 + admin-web + h5-web 改动到服务器并重建。

服务器信息：
- Host: newbb.test.bangbangvip.com
- User: ubuntu
- Pass: Newbang888
- Project dir: /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/

流程：
1. SFTP 上传
   - backend/app/api/ai_home_config.py
   - backend/app/schemas/ai_home_config.py
   - backend/app/models/models.py
   - backend/app/main.py
   - backend/tests/test_ai_home_config.py
   - h5-web/src/app/(ai-chat)/ai-home/page.tsx
   - admin-web/src/app/(admin)/layout.tsx
   - admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx (新建)
   - admin-web/src/app/(admin)/home-settings/ai-home-config/logs/page.tsx (新建)
2. backend: docker cp 文件 → restart backend 容器
3. h5-web 与 admin-web: docker compose build & up -d
4. 容器内 pytest tests/test_ai_home_config.py
5. 远程 smoke：GET /api/ai-home-config 应 200
"""
import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

# (local_path, remote_path, target_container)
FILES = [
    # backend
    (
        os.path.join(LOCAL_ROOT, "backend/app/api/ai_home_config.py"),
        f"{PROJECT_DIR}/backend/app/api/ai_home_config.py",
        "backend",
    ),
    (
        os.path.join(LOCAL_ROOT, "backend/app/schemas/ai_home_config.py"),
        f"{PROJECT_DIR}/backend/app/schemas/ai_home_config.py",
        "backend",
    ),
    (
        os.path.join(LOCAL_ROOT, "backend/app/models/models.py"),
        f"{PROJECT_DIR}/backend/app/models/models.py",
        "backend",
    ),
    (
        os.path.join(LOCAL_ROOT, "backend/app/main.py"),
        f"{PROJECT_DIR}/backend/app/main.py",
        "backend",
    ),
    (
        os.path.join(LOCAL_ROOT, "backend/tests/test_ai_home_config.py"),
        f"{PROJECT_DIR}/backend/tests/test_ai_home_config.py",
        "backend",
    ),
    # h5-web
    (
        os.path.join(LOCAL_ROOT, "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
        f"{PROJECT_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx",
        "h5-web",
    ),
    # admin-web
    (
        os.path.join(LOCAL_ROOT, "admin-web/src/app/(admin)/layout.tsx"),
        f"{PROJECT_DIR}/admin-web/src/app/(admin)/layout.tsx",
        "admin-web",
    ),
    (
        os.path.join(
            LOCAL_ROOT, "admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx"
        ),
        f"{PROJECT_DIR}/admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx",
        "admin-web",
    ),
    (
        os.path.join(
            LOCAL_ROOT,
            "admin-web/src/app/(admin)/home-settings/ai-home-config/logs/page.tsx",
        ),
        f"{PROJECT_DIR}/admin-web/src/app/(admin)/home-settings/ai-home-config/logs/page.tsx",
        "admin-web",
    ),
]


def ensure_remote_dir(sftp, remote_path):
    parts = []
    cur = os.path.dirname(remote_path)
    while cur and cur != "/":
        parts.append(cur)
        cur = os.path.dirname(cur)
    for p in reversed(parts):
        try:
            sftp.stat(p)
        except IOError:
            try:
                sftp.mkdir(p)
            except Exception:
                pass


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[1/6] SSH connect {HOST} ...", flush=True)
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = ssh.open_sftp()

    print("[2/6] SFTP upload files ...", flush=True)
    for local_path, remote_path, _ in FILES:
        if not os.path.exists(local_path):
            print(f"  [SKIP missing] {local_path}", flush=True)
            continue
        ensure_remote_dir(sftp, remote_path)
        sftp.put(local_path, remote_path)
        print(f"  uploaded -> {remote_path}", flush=True)

    sftp.close()

    def run(cmd, timeout=900):
        print(f"  $ {cmd}", flush=True)
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "ignore")
        err = stderr.read().decode("utf-8", "ignore")
        rc = stdout.channel.recv_exit_status()
        print(out, flush=True)
        if err.strip():
            print(f"[stderr] {err}", flush=True)
        return rc, out, err

    backend_container = f"{DEPLOY_ID}-backend"
    h5_container = f"{DEPLOY_ID}-h5-web"
    admin_container = f"{DEPLOY_ID}-admin-web"

    print("[3/6] Backend: docker cp + restart ...", flush=True)
    backend_files = [r for _, r, c in FILES if c == "backend"]
    for r in backend_files:
        rel = r.replace(PROJECT_DIR + "/backend/", "")
        run(f"docker cp {r} {backend_container}:/app/{rel}")
    run(f"docker restart {backend_container}")
    time.sleep(8)

    print("[4/6] h5-web: docker compose build & up ...", flush=True)
    run(
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.yml build h5-web 2>&1 | tail -20",
        timeout=900,
    )
    run(f"cd {PROJECT_DIR} && docker compose -f docker-compose.yml up -d h5-web")

    print("[4.5/6] admin-web: docker compose build & up ...", flush=True)
    run(
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.yml build admin-web 2>&1 | tail -20",
        timeout=900,
    )
    run(f"cd {PROJECT_DIR} && docker compose -f docker-compose.yml up -d admin-web")
    time.sleep(8)

    print("[5/6] pytest in backend container ...", flush=True)
    rc, out, err = run(
        f"docker exec {backend_container} python -m pytest tests/test_ai_home_config.py -x -v 2>&1 | tail -60",
        timeout=300,
    )

    print("[6/6] smoke ...", flush=True)
    base = f"https://{HOST}/autodev/{DEPLOY_ID}"
    smoke_cmds = [
        f"curl -s -o /dev/null -w '%{{http_code}}' {base}/api/health",
        f"curl -s -o /dev/null -w '%{{http_code}}' {base}/api/ai-home-config",
        f"curl -s -o /dev/null -w '%{{http_code}}' {base}/",
        f"curl -s -o /dev/null -w '%{{http_code}}' {base}/admin/home-settings/ai-home-config",
    ]
    for cmd in smoke_cmds:
        run(cmd)

    ssh.close()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
