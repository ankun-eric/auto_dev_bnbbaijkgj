"""PRD-442 全域迁移落地（cursor_prompt_443）部署脚本

将 H5 静态资源 design-system-v2/ 上传到 h5 容器并 docker restart，让 next-server 重扫 public/。
对小程序 wxss 和 Flutter token 包不做服务器侧操作（这些是端打包阶段使用）。
"""
import os
import sys
import time
import stat
import urllib.request
import urllib.error
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
ROOT = Path(__file__).resolve().parent
LOCAL_DIR = ROOT / "h5-web" / "public" / "design-system-v2"
REMOTE_TMP = f"/tmp/design-system-v2-{int(time.time())}"
CONTAINER_PATH = "/app/public/design-system-v2"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"[ssh] connecting to {HOST} ...")
ssh.connect(HOST, username=USER, password=PWD, timeout=30)


def run(cmd: str, timeout: int = 120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"\n$ {cmd[:120]}")
    print(f"[rc={rc}]")
    if out:
        print(out[:1500])
    if err:
        print("ERR:", err[:500])
    return rc, out, err


# ---- 1) SFTP 上传 H5 静态资源 ----
print("=" * 70)
print("Step 1: SFTP upload H5 static assets")
print("=" * 70)
sftp = ssh.open_sftp()


def sftp_mkdirs(path):
    parts = path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


sftp_mkdirs(REMOTE_TMP)
files_to_upload = [p for p in LOCAL_DIR.iterdir() if p.is_file()]
print(f"[upload] {len(files_to_upload)} files -> {REMOTE_TMP}")
for fp in files_to_upload:
    remote = f"{REMOTE_TMP}/{fp.name}"
    sftp.put(str(fp), remote)
    print(f"  + {fp.name} ({fp.stat().st_size} bytes)")
sftp.close()

# ---- 2) docker cp 进 h5 容器 ----
print("=" * 70)
print("Step 2: docker cp into h5 container")
print("=" * 70)
container = f"{DEPLOY_ID}-h5"
# 先确保目标目录存在（容器内）
run(f"docker exec {container} mkdir -p {CONTAINER_PATH}")
run(f"docker cp {REMOTE_TMP}/. {container}:{CONTAINER_PATH}/")
run(f"docker exec {container} ls -la {CONTAINER_PATH} 2>&1 | head -20")

# ---- 3) docker restart 让 next-server 重扫 public ----
print("=" * 70)
print("Step 3: docker restart h5 container (next-server rescans public/)")
print("=" * 70)
run(f"docker restart {container}")

print("[wait] sleeping 35s for next-server to start ...")
time.sleep(35)

# ---- 4) 容器内验证 ----
run(f"docker exec {container} ls -la {CONTAINER_PATH} 2>&1 | head -20")

# ---- 5) Smoke ----
print("=" * 70)
print("Step 4: Smoke test via base URL")
print("=" * 70)

paths = [
    "/design-system-v2/index.html",
    "/design-system-v2/design-tokens.css",
    "/design-system-v2/icons.json",
    "/design-system-v2/PRD-442.md",
]
pass_count = 0
for p in paths:
    url = BASE_URL + p
    ok = False
    for retry in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "smoke/1.0"})
            r = urllib.request.urlopen(req, timeout=15)
            body = r.read()
            print(f"  [OK]   HTTP {r.status}  {p}  ({len(body)} bytes)")
            pass_count += 1
            ok = True
            break
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 307, 308):
                print(f"  [OK]   HTTP {e.code}  {p}")
                pass_count += 1
                ok = True
                break
            if retry < 2:
                time.sleep(5)
                continue
            print(f"  [FAIL] HTTP {e.code}  {p}")
            break
        except Exception as e:
            if retry < 2:
                time.sleep(5)
                continue
            print(f"  [FAIL] {type(e).__name__}  {p}: {e}")
            break

# ---- 6) 回归（PRD-441/442 v1 资产仍可用） ----
print("\nRegression:")
for p in ["/ai-home", "/design-system/index.html", "/menu-mode-design-system/index.html"]:
    try:
        req = urllib.request.Request(BASE_URL + p, headers={"User-Agent": "smoke/1.0"})
        r = urllib.request.urlopen(req, timeout=15)
        print(f"  [OK]   HTTP {r.status}  {p}")
    except urllib.error.HTTPError as e:
        ok = e.code in (200, 301, 302, 307, 308)
        print(f"  [{'OK' if ok else 'FAIL'}]   HTTP {e.code}  {p}")
    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}  {p}")

# ---- 7) 清理临时目录 ----
run(f"rm -rf {REMOTE_TMP}")

ssh.close()

print("=" * 70)
print(f"Smoke result: {pass_count}/{len(paths)} PASS")
print("=" * 70)
sys.exit(0 if pass_count == len(paths) else 1)
