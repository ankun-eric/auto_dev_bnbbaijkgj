"""
[PRD-AI-HOME-V1 2026-05-19] H5 端 AI 首页与抽屉入口优化部署脚本

- 将本次改动的 h5-web 源码（含归档/迁移/新组件）打包上传到服务器
- 在服务器上 docker-compose 重建并启动 h5-web 容器（仅 H5 改动）
- 全程使用 paramiko，无人值守
"""
import os
import sys
import time
import tarfile
import io

try:
    import paramiko
except ImportError:
    print("paramiko not installed, install via `pip install paramiko`")
    sys.exit(1)

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/{USER}/{DEPLOY_ID}"

# 本地工作目录
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))


def ssh_exec(cli, cmd, timeout=900):
    print(f"$ {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print("[stderr]", err)
    return code, out, err


def make_tar_bytes(items):
    """items: list of (local_path, arcname)"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for local, arc in items:
            if not os.path.exists(local):
                print(f"[WARN] missing local {local}")
                continue
            tf.add(local, arcname=arc)
    buf.seek(0)
    return buf.read()


def upload_bytes(cli, data, remote_path):
    sftp = cli.open_sftp()
    try:
        with sftp.open(remote_path, "wb") as f:
            f.write(data)
    finally:
        sftp.close()


def main():
    print(f"[deploy] connecting {HOST} ...")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    print("[deploy] connected.")

    # 1) ensure remote project exists
    code, out, _ = ssh_exec(cli, f"ls -la {REMOTE_BASE}/h5-web/src/app 2>&1 | head -n 5")
    if code != 0:
        print("[deploy] remote project directory not ready, abort.")
        cli.close()
        sys.exit(2)

    # 2) Pack changed files & upload
    items = [
        # 新增/修改的 h5-web 文件
        (os.path.join(LOCAL_ROOT, "h5-web/src/app/services/page.tsx"),
         "h5-web/src/app/services/page.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/app/_archived_tabs"),
         "h5-web/src/app/_archived_tabs"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
         "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/app/(ai-chat)/ai-settings/page.tsx"),
         "h5-web/src/app/(ai-chat)/ai-settings/page.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/app/login/page.tsx"),
         "h5-web/src/app/login/page.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/app/page.tsx"),
         "h5-web/src/app/page.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/app/search/result/page.tsx"),
         "h5-web/src/app/search/result/page.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/app/health-guide/page.tsx"),
         "h5-web/src/app/health-guide/page.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/components/ai-chat/Sidebar.tsx"),
         "h5-web/src/components/ai-chat/Sidebar.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/components/ai-chat/MemberCodeModal.tsx"),
         "h5-web/src/components/ai-chat/MemberCodeModal.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/src/components/search/GlobalSearchEntry.tsx"),
         "h5-web/src/components/search/GlobalSearchEntry.tsx"),
        (os.path.join(LOCAL_ROOT, "h5-web/next.config.js"),
         "h5-web/next.config.js"),
    ]
    data = make_tar_bytes(items)
    print(f"[deploy] tarball size = {len(data)/1024:.1f} KiB")

    remote_tar = f"{REMOTE_BASE}/_deploy_prd_aihome_v1.tar.gz"
    upload_bytes(cli, data, remote_tar)

    # 3) Remove the (tabs) directory and extract over project
    ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && rm -rf 'h5-web/src/app/(tabs)' && tar -xzf _deploy_prd_aihome_v1.tar.gz",
        timeout=120,
    )

    # 4) Rebuild h5-web container
    code, out, err = ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -n 80",
        timeout=900,
    )
    if code != 0:
        print("[deploy] build failed")
        cli.close()
        sys.exit(3)

    code, out, err = ssh_exec(
        cli,
        f"cd {REMOTE_BASE} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -n 40",
        timeout=180,
    )
    if code != 0:
        print("[deploy] up failed")
        cli.close()
        sys.exit(4)

    # 5) Wait healthy
    print("[deploy] waiting h5-web ...")
    for i in range(30):
        time.sleep(2)
        c, o, _ = ssh_exec(cli, f"docker logs --tail 5 {DEPLOY_ID}-h5 2>&1")
        if "ready" in o.lower() or "started server" in o.lower():
            print("[deploy] h5-web ready")
            break

    cli.close()
    print("[deploy] done.")


if __name__ == "__main__":
    main()
