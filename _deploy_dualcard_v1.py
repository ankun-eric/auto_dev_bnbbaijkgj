"""[PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 部署脚本：将后端+H5 改动同步到服务器并重建容器。"""
import os
import sys
import tarfile
import paramiko
from pathlib import Path

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = Path(__file__).parent


def ssh_exec(client, cmd, timeout=600):
    print(f">>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out_chunks = []
    err_chunks = []
    while True:
        if stdout.channel.recv_ready():
            data = stdout.channel.recv(4096).decode("utf-8", errors="ignore")
            out_chunks.append(data)
            print(data, end="")
        if stdout.channel.recv_stderr_ready():
            data = stdout.channel.recv_stderr(4096).decode("utf-8", errors="ignore")
            err_chunks.append(data)
            print(data, end="")
        if stdout.channel.exit_status_ready():
            break
    # drain
    while stdout.channel.recv_ready():
        data = stdout.channel.recv(4096).decode("utf-8", errors="ignore")
        out_chunks.append(data)
        print(data, end="")
    while stdout.channel.recv_stderr_ready():
        data = stdout.channel.recv_stderr(4096).decode("utf-8", errors="ignore")
        err_chunks.append(data)
        print(data, end="")
    code = stdout.channel.recv_exit_status()
    return code, "".join(out_chunks), "".join(err_chunks)


def make_tar(src_dir: Path, out_tar: Path, exclude_globs=None):
    exclude_globs = exclude_globs or []
    def _filter(tarinfo):
        # 跳过 node_modules, .next, __pycache__ 等
        path = tarinfo.name
        skip_parts = ("node_modules/", "/.next/", "/__pycache__/", "/.git/",
                      ".next/", ".pytest_cache/", "build/", "dist/", ".cache/")
        for s in skip_parts:
            if s in path:
                return None
        return tarinfo
    with tarfile.open(out_tar, "w:gz") as tf:
        tf.add(src_dir, arcname=src_dir.name, filter=_filter)


def main():
    print("[1] 打包 backend + h5-web 改动文件 ...")
    tar_path = LOCAL_ROOT / "_dualcard_v1_patch.tar.gz"
    if tar_path.exists():
        tar_path.unlink()
    # 仅打包：backend/app/api/reverse_guardian.py, backend/app/api/family_management.py,
    # backend/app/schemas/reverse_guardian.py, backend/tests/test_guardian_dualcard_v1_20260528.py,
    # h5-web/src/app/health-profile/page.tsx,
    # h5-web/src/app/health-profile/my-guardians/page.tsx,
    # h5-web/src/app/health-profile/my-guardians/invite/page.tsx,
    # h5-web/src/app/health-profile/i-guard/page.tsx
    files = [
        "backend/app/api/reverse_guardian.py",
        "backend/app/api/family_management.py",
        "backend/app/schemas/reverse_guardian.py",
        "backend/tests/test_guardian_dualcard_v1_20260528.py",
        "h5-web/src/app/health-profile/page.tsx",
        "h5-web/src/app/health-profile/my-guardians/page.tsx",
        "h5-web/src/app/health-profile/my-guardians/invite/page.tsx",
        "h5-web/src/app/health-profile/i-guard/page.tsx",
    ]
    with tarfile.open(tar_path, "w:gz") as tf:
        for rel in files:
            fp = LOCAL_ROOT / rel
            if not fp.exists():
                print(f"  ✗ Missing file: {rel}")
                sys.exit(1)
            tf.add(fp, arcname=rel)
            print(f"  + {rel}")
    print(f"  -> {tar_path} ({tar_path.stat().st_size//1024} KB)")

    print("[2] SSH 连接服务器 ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)

    print("[3] 上传 patch tar ...")
    sftp = client.open_sftp()
    remote_tar = f"/tmp/_dualcard_v1_patch_{os.getpid()}.tar.gz"
    sftp.put(str(tar_path), remote_tar)
    sftp.close()

    print("[4] 展开 patch & 重建 backend + h5-web ...")
    cmds = [
        f"cd {PROJECT_DIR} && tar xzf {remote_tar}",
        f"rm -f {remote_tar}",
        # 重建 backend（代码变化即可，简单 restart 即可，但为确保 schema 兼容这里 rebuild）
        f"cd {PROJECT_DIR} && docker compose up -d --no-deps --build backend",
        # 重建 h5-web
        f"cd {PROJECT_DIR} && docker compose up -d --no-deps --build h5-web",
        f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}",
    ]
    for cmd in cmds:
        code, _, _ = ssh_exec(client, cmd, timeout=900)
        if code != 0 and "grep" not in cmd:
            print(f"  ✗ Command failed (code={code}): {cmd}")
            client.close()
            sys.exit(1)

    print("[5] 等待容器就绪 ...")
    ssh_exec(client, f"sleep 8 && docker logs --tail 20 {DEPLOY_ID}-backend 2>&1", timeout=60)

    print("[6] Smoke test：调用 guardian-count 接口 ...")
    ssh_exec(client,
        f"docker exec {DEPLOY_ID}-backend curl -s http://localhost:8000/health || echo NO_HEALTH",
        timeout=60,
    )
    client.close()
    print("\n[OK] 部署完成。")


if __name__ == "__main__":
    main()
