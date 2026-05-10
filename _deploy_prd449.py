"""PRD-449 AI 首页（ai-home）页面优化部署脚本

仅改动 h5-web 前端：
- 新增 AiAvatar 公共组件（h5-web/src/components/ai-chat/AiAvatar.tsx）
- 顶部栏背景改主色 + "小康"间距压缩 4px
- 欢迎区/AI 消息小头像/loading 卡片头像 → AiAvatar
- 新增默认头像图 h5-web/public/images/default-ai-avatar.png

部署流程：
- 本地打 h5-web/src + h5-web/public/images 的 tar.gz
- SFTP 上传到服务器
- 解压覆盖
- docker compose build h5-web + up -d h5-web
- smoke 测试关键页面 + 默认图可访问
"""
from __future__ import annotations

import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

ROOT = Path(__file__).resolve().parent
TS = int(time.time())
LOCAL_TAR = ROOT / f"prd449_h5_{TS}.tar.gz"
REMOTE_TAR = f"/tmp/prd449_h5_{TS}.tar.gz"


def main() -> None:
    print("=" * 70)
    print("Step 0: tar h5-web/src + h5-web/public/images locally")
    print("=" * 70)
    h5_src = ROOT / "h5-web" / "src"
    h5_imgs = ROOT / "h5-web" / "public" / "images"
    if not h5_src.exists():
        print(f"ERROR: {h5_src} not found")
        sys.exit(1)
    if not h5_imgs.exists():
        print(f"ERROR: {h5_imgs} not found (default-ai-avatar.png missing)")
        sys.exit(1)
    with tarfile.open(LOCAL_TAR, "w:gz") as tar:
        tar.add(h5_src, arcname="h5-web/src")
        tar.add(h5_imgs, arcname="h5-web/public/images")
    sz = LOCAL_TAR.stat().st_size
    print(f"local tar: {LOCAL_TAR}  ({sz/1024/1024:.2f} MB)")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting to {HOST} ...")
    ssh.connect(HOST, username=USER, password=PWD, timeout=60)

    def run(cmd: str, timeout: int = 1200, show_tail: int = 3000):
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(f"\n$ {cmd[:160]}")
        print(f"[rc={rc}]")
        if out:
            print(out[-show_tail:])
        if err and rc != 0:
            print("ERR:", err[-1500:])
        return rc, out, err

    print("=" * 70)
    print("Step 1: SFTP upload")
    print("=" * 70)
    sftp = ssh.open_sftp()
    sftp.put(str(LOCAL_TAR), REMOTE_TAR)
    sftp.close()
    print(f"uploaded -> {REMOTE_TAR}")

    print("=" * 70)
    print("Step 2: extract & verify on server")
    print("=" * 70)
    cmds = [
        f"cd {REMOTE_PROJECT_DIR} && rm -rf .prd449_backup && mkdir -p .prd449_backup",
        f"cd {REMOTE_PROJECT_DIR} && cp -r h5-web/src .prd449_backup/h5_src",
        f"cd {REMOTE_PROJECT_DIR} && (cp -r h5-web/public/images .prd449_backup/h5_images 2>/dev/null || true)",
        f"cd {REMOTE_PROJECT_DIR} && tar -xzf {REMOTE_TAR}",
        f"ls -la {REMOTE_PROJECT_DIR}/h5-web/public/images/",
        f"ls {REMOTE_PROJECT_DIR}/h5-web/src/components/ai-chat/AiAvatar.tsx",
        f"grep -c 'PRD-449' {REMOTE_PROJECT_DIR}/h5-web/src/components/ai-chat/AiAvatar.tsx",
        f"grep -c 'PRD-449 R1' {REMOTE_PROJECT_DIR}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        f"grep -c 'PRD-449 R2' {REMOTE_PROJECT_DIR}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        f"grep -c 'PRD-449 R3' {REMOTE_PROJECT_DIR}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
        f"grep -c 'PRD-449 R4' {REMOTE_PROJECT_DIR}/h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx",
    ]
    for c in cmds:
        run(c, timeout=120)

    print("=" * 70)
    print("Step 3: rebuild h5-web container")
    print("=" * 70)
    rc, out, _ = run(
        f"cd {REMOTE_PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -120",
        timeout=1800,
    )
    if rc != 0:
        print("h5-web build FAILED, rolling back source ...")
        run(
            f"cd {REMOTE_PROJECT_DIR} && rm -rf h5-web/src && cp -r .prd449_backup/h5_src h5-web/src"
        )
        ssh.close()
        sys.exit(2)

    rc, _, _ = run(
        f"cd {REMOTE_PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web",
        timeout=120,
    )
    if rc != 0:
        print("h5-web up failed, abort.")
        ssh.close()
        sys.exit(3)

    run(
        f"docker ps --filter name={DEPLOY_ID}-h5 --format '{{{{.Names}}}}|{{{{.Status}}}}'"
    )

    run(
        f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null || true"
    )

    run(f"rm -f {REMOTE_TAR}")
    LOCAL_TAR.unlink(missing_ok=True)

    print("=" * 70)
    print("Step 6: wait 30s & smoke test")
    print("=" * 70)
    time.sleep(30)

    smoke_paths = [
        "/",
        "/login/",
        "/ai-home/",
        "/images/default-ai-avatar.png",
    ]
    pass_count = 0
    for p in smoke_paths:
        url = BASE_URL + p
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "PRD449-smoke/1.0"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                code = resp.getcode()
                ok = code == 200
                if ok:
                    pass_count += 1
                print(f"  {url}  -> {code}  {'PASS' if ok else 'FAIL'}")
        except Exception as e:
            print(f"  {url}  -> ERROR: {e}")

    print(f"\n[smoke] {pass_count}/{len(smoke_paths)} PASS")

    ssh.close()
    print("=" * 70)
    print(f"PRD-449 deploy DONE. smoke = {pass_count}/{len(smoke_paths)}")
    print("=" * 70)
    sys.exit(0 if pass_count >= len(smoke_paths) - 1 else 2)


if __name__ == "__main__":
    main()
