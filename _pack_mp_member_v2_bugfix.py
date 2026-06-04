"""[会员中心入口与权益对比 v1.0 bugfix] 小程序打包+上传到服务器
打包 miniprogram/ -> zip, 上传到服务器, 验证 HTTPS 下载.

按用户要求 URL 形如:
  https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/<filename>.zip
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
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def run(client, cmd, timeout=120, ignore_err=False):
    print(f"\n$ {cmd[:240]}", flush=True)
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:], flush=True)
    if err.strip():
        print("STDERR:", err[-1500:], flush=True)
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed rc={rc}: {cmd[:120]}")
    return rc, out, err


def main():
    base = os.path.abspath(os.path.dirname(__file__))
    src_dir = os.path.join(base, "miniprogram")
    ts = time.strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    filename = f"miniprogram_{ts}_{rand}.zip"
    out_path = os.path.join(base, filename)
    print(f"打包: {src_dir} -> {out_path}")

    tmpdir = tempfile.mkdtemp(prefix="mp_pack_")
    try:
        dst = os.path.join(tmpdir, "miniprogram")
        shutil.copytree(src_dir, dst, ignore=shutil.ignore_patterns(
            "node_modules", ".git", "miniprogram_npm",
            "__pycache__", "*.pyc", ".DS_Store"
        ))
        archive_no_ext = out_path[:-4]
        shutil.make_archive(archive_no_ext, "zip", tmpdir, "miniprogram")
        size = os.path.getsize(out_path)
        print(f"  Zip 大小: {size/1024:.1f} KB")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\nSSH 连接 {USER}@{HOST}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        # 1. 查看 gateway nginx 配置，找到 /autodev/{DEPLOY_ID}/ 根目录对应静态路径
        run(client, f"sudo grep -nE '({DEPLOY_ID}|autodev)' /home/ubuntu/gateway/conf.d/*.conf 2>/dev/null | head -40", ignore_err=True)
        run(client, f"sudo cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf 2>/dev/null | head -80", ignore_err=True)

        # 2. 查看 h5 容器 /app/public 目录（h5 服务通常通过此处提供静态文件）
        run(client, f"docker exec {DEPLOY_ID}-h5 ls /app/public 2>/dev/null | head -30", ignore_err=True)
        run(client, f"docker exec {DEPLOY_ID}-h5 ls /app 2>/dev/null | head -30", ignore_err=True)

        # 3. 查看 docker 容器映射的静态目录
        run(client, f"ls /home/ubuntu/{DEPLOY_ID}/ 2>/dev/null", ignore_err=True)
        run(client, f"ls /home/ubuntu/{DEPLOY_ID}/static/ 2>/dev/null", ignore_err=True)
    finally:
        pass

    # 完成探测后，保留连接进行上传
    print("\n--- 探测完成，开始上传 ---")

    # 候选目标 1: 直接放到 h5 容器的 public 下（Next.js 静态资源会通过 /<path> 暴露）
    # 但由于 URL 前缀是 /autodev/{DEPLOY_ID}/，nginx 已 strip 该前缀转发到 h5 容器
    # 所以放到 h5 容器 public 根目录最合适

    # 先用 SFTP 上传到 /home/ubuntu 临时位置
    sftp = client.open_sftp()
    tmp_remote = f"/home/ubuntu/{filename}"
    print(f"\nSFTP 上传 -> {tmp_remote}")
    sftp.put(out_path, tmp_remote)
    sftp.close()
    run(client, f"ls -la {tmp_remote}")

    # 通过 docker cp 放到 h5 容器 /app/public 下
    run(client, f"docker cp {tmp_remote} {DEPLOY_ID}-h5:/app/public/{filename}", ignore_err=True)
    run(client, f"docker exec {DEPLOY_ID}-h5 ls -la /app/public/{filename}", ignore_err=True)

    url = f"{BASE_URL}/{filename}"
    print(f"\n验证: {url}")
    rc, out, _ = run(client,
        f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}'",
        ignore_err=True)
    code = out.strip()
    print(f"HTTP code = {code}")

    if code != "200":
        # 备选：放到 gateway 静态目录 /data/static/ (映射到 /home/ubuntu/{DEPLOY_ID}/static/)
        print("\n备选方案：上传到 gateway 静态目录")
        remote_dir = f"/home/ubuntu/{DEPLOY_ID}/static"
        run(client, f"mkdir -p {remote_dir}")
        run(client, f"cp {tmp_remote} {remote_dir}/{filename}")
        run(client, f"chmod 644 {remote_dir}/{filename}")
        run(client, f"ls -la {remote_dir}/{filename}")
        # 重新验证
        rc, out, _ = run(client,
            f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}'",
            ignore_err=True)
        code = out.strip()
        print(f"HTTP code (备选) = {code}")

    # 清理 /home/ubuntu/ 下的临时文件
    run(client, f"rm -f {tmp_remote}", ignore_err=True)

    client.close()

    print(f"\nDONE filename: {filename}")
    print(f"DONE URL:      {url}")
    print(f"DONE HTTP:     {code}")

    with open(os.path.join(base, "_mp_member_v2_zip.txt"), "w") as f:
        f.write(f"{filename}\n{url}\nHTTP={code}\n")


if __name__ == "__main__":
    main()
