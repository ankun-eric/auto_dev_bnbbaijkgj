"""[PRD-AIHOME-SKELETON-V1 2026-05-19] 部署 ai-home 首屏骨架屏改造到测试服务器.

本次改动文件 (仅 h5-web 端):
  - h5-web/src/app/(ai-chat)/ai-home/page.tsx
  - h5-web/src/components/ai-chat/AiHomeSkeleton.tsx (新增)
  - h5-web/src/app/globals.css

仅需重建 h5-web 容器, 不影响后端/admin/数据库.
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
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

CHANGED_FILES = [
    "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    "h5-web/src/components/ai-chat/AiHomeSkeleton.tsx",
    "h5-web/src/app/globals.css",
]


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)
    return c


def run(c, cmd, timeout=600, check=False, quiet=False):
    if not quiet:
        print(f"\n$ {cmd[:240]}")
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
                print(f"  + {rel} ({os.path.getsize(full)} bytes)")
            else:
                print(f"  [warn] missing: {rel}")
    buf.seek(0)
    return buf.getvalue()


def main():
    local_root = os.path.dirname(os.path.abspath(__file__))
    print(f"local root: {local_root}")
    c = connect()
    print(f"Connected to {HOST}")

    print("\n=== Step 1: Tar & upload changed files ===")
    tar_bytes = make_tarball(local_root, CHANGED_FILES)
    remote_tar = f"/tmp/{DEPLOY_ID}-skeleton.tar.gz"
    sftp = c.open_sftp()
    with sftp.open(remote_tar, "wb") as f:
        f.write(tar_bytes)
    sftp.close()
    print(f"uploaded {len(tar_bytes)} bytes to {remote_tar}")

    print("\n=== Step 2: Extract on server ===")
    run(
        c,
        f"cd {PROJECT_DIR} && tar -xzf {remote_tar} && rm -f {remote_tar}",
        check=True,
    )
    # sanity check
    run(
        c,
        f"ls -la {PROJECT_DIR}/h5-web/src/components/ai-chat/AiHomeSkeleton.tsx "
        f"{PROJECT_DIR}/h5-web/src/app/'(ai-chat)'/ai-home/page.tsx 2>&1",
    )
    run(
        c,
        f"head -5 {PROJECT_DIR}/h5-web/src/components/ai-chat/AiHomeSkeleton.tsx",
    )
    run(
        c,
        f"grep -c 'AiHomeSkeleton' {PROJECT_DIR}/h5-web/src/app/'(ai-chat)'/ai-home/page.tsx",
    )
    run(
        c,
        f"grep -c 'firstScreenStatus' {PROJECT_DIR}/h5-web/src/app/'(ai-chat)'/ai-home/page.tsx",
    )
    run(
        c,
        f"grep -c 'skeleton-shimmer' {PROJECT_DIR}/h5-web/src/app/globals.css",
    )

    print("\n=== Step 3: Rebuild h5-web container ===")
    run(
        c,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -40",
        timeout=2400,
        check=True,
    )

    print("\n=== Step 4: Recreate h5-web ===")
    run(
        c,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate h5-web 2>&1 | tail -20",
        timeout=180,
        check=True,
    )

    print("\n=== Step 5: Wait for h5-web ===")
    time.sleep(15)
    for i in range(12):
        out, _, _ = run(
            c,
            f"docker ps --filter name={DEPLOY_ID}-h5-web --format '{{{{.Names}}}} {{{{.Status}}}}'",
            quiet=True,
        )
        print(f"[{i}] {out.strip()}")
        if out.strip() and "Restarting" not in out and "Up" in out:
            break
        time.sleep(8)

    print("\n=== Step 6: Smoke (HTTP code for /ai-home) ===")
    run(
        c,
        f"curl -sk -o /dev/null -w 'ai-home HTTP %{{http_code}}\\n' "
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/ai-home",
    )
    run(
        c,
        f"curl -sk -o /dev/null -w 'root HTTP %{{http_code}}\\n' "
        f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/",
    )

    c.close()
    print("\n=== DEPLOY DONE ===")


if __name__ == "__main__":
    main()
