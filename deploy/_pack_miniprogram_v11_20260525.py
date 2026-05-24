"""[旧会员体系废弃 v1.1] 小程序打包+上传到服务器
- 打包 miniprogram/ 为 zip
- SFTP 上传到 /home/ubuntu/{DEPLOY_ID}/uploads/ 下
- 通过 nginx /uploads/ 静态路径暴露：
    URL: {BASE_URL}/uploads/<filename>.zip
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import secrets

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def run(client, cmd, timeout=120, ignore_err=False):
    print(f"\n$ {cmd[:240]}", flush=True)
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-2000:], flush=True)
    if err.strip():
        print("STDERR:", err[-1000:], flush=True)
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed rc={rc}")
    return rc, out, err


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    src_dir = os.path.join(base, "miniprogram")
    ts = time.strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    filename = f"miniprogram_{ts}_{rand}.zip"
    out_path = os.path.join(base, filename)
    print(f"打包: {src_dir} -> {out_path}")

    # 用 shutil 排除 node_modules / .git
    tmpdir = tempfile.mkdtemp(prefix="mp_pack_")
    try:
        dst = os.path.join(tmpdir, "miniprogram")
        shutil.copytree(src_dir, dst, ignore=shutil.ignore_patterns(
            "node_modules", ".git", "__pycache__", "*.pyc"
        ))
        # 打包成 zip
        archive_no_ext = out_path[:-4]
        shutil.make_archive(archive_no_ext, "zip", tmpdir, "miniprogram")
        size = os.path.getsize(out_path)
        print(f"  Zip 大小: {size/1024:.1f} KB")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # gateway nginx 配置中 `/miniprogram/` 指向 `/data/static/miniprogram/`，
    # gateway 容器把宿主机 `/home/ubuntu/{DEPLOY_ID}/static/` 挂载为 `/data/static/`。
    # 因此上传目标为：宿主机 /home/ubuntu/{DEPLOY_ID}/static/miniprogram/
    remote_dir = f"{PROJ_DIR}/static/miniprogram"
    print(f"\nSSH 上传 -> {USER}@{HOST}:{remote_dir}/{filename}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        sftp = client.open_sftp()
        run(client, f"mkdir -p {remote_dir}")
        remote_path = f"{remote_dir}/{filename}"
        sftp.put(out_path, remote_path)
        sftp.close()
        run(client, f"chmod 644 {remote_path}")

        url = f"{BASE_URL}/miniprogram/{filename}"
        print(f"\n下载 URL: {url}")
        # 验证 HTTP 200
        run(client,
            f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}'",
            ignore_err=True)
    finally:
        client.close()

    # 写入文件名记录
    with open(os.path.join(base, ".miniprogram_zip_v11.txt"), "w") as f:
        f.write(filename)
    print(f"\nDONE: {filename}")


if __name__ == "__main__":
    main()
