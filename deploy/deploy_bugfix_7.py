"""部署 7-bug 修复 (commit 9a8d544) 到 newbb.test.bangbangvip.com。

策略:
- 先尝试 git fetch+reset (网络可能不稳, 重试 5 次)
- 失败则回退到 tar 上传变更文件
- 重新构建并启动 backend / h5-web 容器 (admin-web 此次未改, 可跳过)
- 重新加载 gateway nginx
- 验证关键页面返回 2xx/3xx
"""
import io
import os
import sys
import tarfile
import time

import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_DIR = "/home/ubuntu/gateway"
BASE_PATH = f"/autodev/{DEPLOY_ID}"

GIT_USER = os.environ.get("GIT_USER", "ankun-eric")
# 不在仓库里硬编码 PAT，避免触发 GitHub Push Protection。运行时从环境变量读取，
# 没有也没关系——服务器侧本身已配置过 origin URL，fetch 拿不到时会回退到 tar 上传。
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
GIT_URL = (
    f"https://{GIT_USER}:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
    if GIT_TOKEN
    else "https://github.com/ankun-eric/auto_dev_bnbbaijkgj.git"
)
TARGET_COMMIT = "9a8d544"

CHANGED_FILES = [
    "backend/app/api/home_config.py",
    "backend/app/api/points.py",
    "backend/app/init_data.py",
    "backend/app/main.py",
    "h5-web/src/app/(tabs)/ai/page.tsx",
    "h5-web/src/app/(tabs)/home/page.tsx",
    "h5-web/src/app/points/page.tsx",
]


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)
    return c


def run(c, cmd, timeout=600, check=False, quiet=False):
    if not quiet:
        print(f"\n$ {cmd[:220]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        if out:
            print(out[-3000:])
        if err:
            print(f"[stderr] {err[-1500:]}")
        print(f"[exit {code}]")
    if check and code != 0:
        raise RuntimeError(f"Command failed (exit {code}): {cmd}\n{err}")
    return out, err, code


def make_tarball(local_root, files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in files:
            full = os.path.join(local_root, rel.replace("/", os.sep))
            if os.path.exists(full):
                tar.add(full, arcname=rel)
                print(f"  + {rel}")
            else:
                print(f"  [warn] missing: {rel}")
    buf.seek(0)
    return buf.getvalue()


def main():
    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    c = connect()
    print(f"Connected to {HOST}")

    print(f"\n=== Step 0: Show current server commit ===")
    run(c, f"cd {PROJECT_DIR} && git log -1 --oneline")

    print(f"\n=== Step 1: Try git fetch + reset to {TARGET_COMMIT} ===")
    run(c, f"cd {PROJECT_DIR} && git remote set-url origin {GIT_URL}", quiet=True)
    run(c, f"cd {PROJECT_DIR} && git config http.lowSpeedLimit 0 && git config http.lowSpeedTime 999999 && git config http.postBuffer 524288000")

    fetched = False
    for i in range(3):
        print(f"  - attempt {i+1}/3")
        _, _, code = run(c, f"cd {PROJECT_DIR} && timeout 200 git fetch origin master 2>&1", timeout=240)
        if code == 0:
            fetched = True
            break
        time.sleep(8)

    if fetched:
        run(c, f"cd {PROJECT_DIR} && git reset --hard origin/master && git clean -fd", check=True)
        run(c, f"cd {PROJECT_DIR} && git log -1 --oneline")
    else:
        print("\n[fallback] git fetch failed -> tar upload changed files")
        tar_bytes = make_tarball(local_root, CHANGED_FILES)
        remote_tar = f"/tmp/{DEPLOY_ID}-bugfix7.tar.gz"
        sftp = c.open_sftp()
        with sftp.open(remote_tar, "wb") as f:
            f.write(tar_bytes)
        sftp.close()
        print(f"  uploaded {len(tar_bytes)} bytes")
        run(c, f"cd {PROJECT_DIR} && tar -xzf {remote_tar} && rm -f {remote_tar}", check=True)

    print(f"\n=== Step 2: Sanity check changed files ===")
    run(c, f"grep -n '搜索您想要的健康服务' {PROJECT_DIR}/backend/app/api/home_config.py | head -3")
    run(c, f"grep -n 'placeholder_v7_normalized' {PROJECT_DIR}/backend/app/main.py | head -3")
    run(c, f"grep -n 'ONCE_TASK_HIDE_AFTER_DAYS' {PROJECT_DIR}/backend/app/api/points.py | head -3")

    print("\n=== Step 3: Rebuild backend + h5-web (admin-web unchanged) ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend h5-web 2>&1 | tail -40", timeout=1500, check=True)

    print("\n=== Step 4: Recreate backend + h5-web ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend h5-web 2>&1 | tail -20", timeout=180, check=True)

    print("\n=== Step 5: Wait for containers ===")
    time.sleep(20)
    for i in range(8):
        out, _, _ = run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'")
        if "Restarting" not in out and out.count(DEPLOY_ID) >= 4:
            break
        time.sleep(8)

    print("\n=== Step 6: Connect gateway to network + reload ===")
    run(c, f"docker network connect {DEPLOY_ID}-network gateway 2>&1 || true")
    run(c, "docker exec gateway nginx -t 2>&1")
    run(c, "docker exec gateway nginx -s reload 2>&1")
    time.sleep(3)

    print("\n=== Step 7: Smoke check key URLs ===")
    urls = [
        f"https://{DOMAIN}{BASE_PATH}/h5/",
        f"https://{DOMAIN}{BASE_PATH}/h5/points",
        f"https://{DOMAIN}{BASE_PATH}/h5/ai",
        f"https://{DOMAIN}{BASE_PATH}/h5/profile/edit",
        f"https://{DOMAIN}{BASE_PATH}/h5/services",
        f"https://{DOMAIN}{BASE_PATH}/api/home-config",
        f"https://{DOMAIN}{BASE_PATH}/api/health",
    ]
    for u in urls:
        run(c, f"curl -sI -o /dev/null -w '%{{http_code}} {u}\\n' '{u}'", quiet=True)
        out, _, _ = run(c, f"curl -sI -o /dev/null -w '%{{http_code}}' '{u}'", quiet=True)
        print(f"  {out:>3}  {u}")

    print("\n=== Step 8: Backend logs tail ===")
    run(c, f"docker logs {DEPLOY_ID}-backend 2>&1 | tail -30")

    c.close()
    print("\n=== DEPLOY DONE ===")


if __name__ == "__main__":
    main()
