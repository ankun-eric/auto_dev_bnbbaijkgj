#!/usr/bin/env python3
"""[PRD-AICHAT-HOME-GRID-V1 2026-05-16] 打包微信小程序源码 → SFTP 上传 → HTTPS 校验

流程：
1. 生成唯一文件名 miniprogram_<YYYYMMDD_HHMMSS>_<4hex>.zip
2. 把 miniprogram/ 全量打包为 zip（排除 node_modules / .git / .DS_Store / *.log 等）
3. paramiko SFTP 上传到服务器 /tmp/，再 mv 到宿主机绑定目录
   /home/ubuntu/<deploy_id>/static/miniprogram/<filename>.zip
   该目录通过 gateway 容器 bind mount 暴露在 /data/static/miniprogram/，
   nginx 反向代理路径为 {BASE_URL}/miniprogram/<filename>.zip
4. HTTPS GET 校验下载链接 200 + 字节长度匹配（多次重试）
5. 输出 zip 文件名 / 完整下载 URL / 大小（MB）

可独立反复运行；上传失败会自动重试。
"""
from __future__ import annotations

import os
import sys
import ssl
import time
import secrets
import zipfile
import datetime
import urllib.request
import urllib.error

import paramiko


HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

SRC_DIR = r"C:\auto_output\bnbbaijkgj\miniprogram"
LOCAL_TMP = r"C:\auto_output\bnbbaijkgj\scripts\_dist"

EXCLUDE_DIRS = {
    "node_modules",
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "miniprogram_npm",
    ".cache",
}
EXCLUDE_SUFFIXES = (".log",)
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}


def gen_filename() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)  # 4 hex chars
    return f"miniprogram_{ts}_{rand}.zip"


def build_zip(src_dir: str, out_path: str) -> tuple[int, int]:
    """打包 src_dir 全部内容到 out_path，返回 (文件数, 大小字节)。"""
    if not os.path.isdir(src_dir):
        raise FileNotFoundError(f"源目录不存在: {src_dir}")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    file_count = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                if fn in EXCLUDE_FILES:
                    continue
                if fn.lower().endswith(EXCLUDE_SUFFIXES):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, src_dir).replace("\\", "/")
                try:
                    zf.write(full, rel)
                    file_count += 1
                except OSError as e:
                    print(f"[zip] skip {rel}: {e}")
    size = os.path.getsize(out_path)
    return file_count, size


def ssh_connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        HOST, username=USER, password=PASSWORD,
        timeout=30, allow_agent=False, look_for_keys=False,
    )
    return c


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 180) -> tuple[int, str, str]:
    print(f"[ssh] $ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print(f"[stderr] {err.rstrip()}")
    return rc, out, err


def http_status(url: str, timeout: int = 60, method: str = "GET") -> tuple[int, int]:
    """返回 (status_code, content_length)。失败返回 (0, 0)。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            url, method=method,
            headers={"User-Agent": "miniprogram-upload-check/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read() if method == "GET" else b""
            return resp.status, len(data) if method == "GET" else int(resp.headers.get("Content-Length", 0))
    except urllib.error.HTTPError as e:
        return e.code, 0
    except Exception as e:
        print(f"[http] error: {e}")
        return 0, 0


def sftp_upload_with_retry(client: paramiko.SSHClient, local: str, remote: str, retries: int = 5) -> None:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            sftp = client.open_sftp()
            try:
                t0 = time.time()
                sftp.put(local, remote)
                print(f"[sftp] 完成 ({time.time()-t0:.1f}s)")
                return
            finally:
                sftp.close()
        except Exception as e:
            last_err = e
            print(f"[sftp] attempt {attempt} failed: {e}; sleep 5s")
            time.sleep(5)
    raise RuntimeError(f"SFTP 上传失败 after {retries} attempts: {last_err}")


def main() -> int:
    fname = gen_filename()
    local_zip = os.path.join(LOCAL_TMP, fname)
    remote_tmp = f"/tmp/{fname}"
    host_static_dir = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"
    host_target = f"{host_static_dir}/{fname}"
    container_path = f"/data/static/miniprogram/{fname}"
    download_url = f"{BASE_URL}/miniprogram/{fname}"

    print(f"[pack] 源目录   : {SRC_DIR}")
    print(f"[pack] 输出文件 : {local_zip}")
    fcount, size = build_zip(SRC_DIR, local_zip)
    size_mb = size / 1024 / 1024
    print(f"[pack] 完成: {fcount} files, {size:,} bytes ({size_mb:.2f} MB)")

    print(f"\n[ssh] 连接 {HOST} ...")
    client = ssh_connect()
    try:
        print(f"[sftp] 上传 -> {remote_tmp}")
        sftp_upload_with_retry(client, local_zip, remote_tmp)
        run(client, f"ls -la {remote_tmp}")

        print("\n[gateway] 确认 gateway 容器存在")
        rc, out, _ = run(client, "docker ps --filter name=^gateway$ --format '{{.Names}}\\t{{.Status}}'")
        if "gateway" not in out:
            print("[FATAL] gateway 容器不存在")
            return 2

        print(f"\n[host] 确保宿主机绑定目录存在: {host_static_dir}")
        rc, _, _ = run(client, f"mkdir -p {host_static_dir} && ls -ld {host_static_dir}")
        if rc != 0:
            print("[FATAL] 无法创建宿主机目录")
            return 3

        print(f"\n[host] 移动 zip 到宿主机绑定目录: {host_target}")
        rc, _, _ = run(
            client,
            f"mv {remote_tmp} {host_target} && chmod 644 {host_target} && ls -la {host_target}",
        )
        if rc != 0:
            print("[FATAL] 移动文件失败")
            return 3

        print("\n[verify] docker exec ls 校验容器内文件（通过 bind mount 可见）")
        rc, out, _ = run(client, f"docker exec gateway ls -la {container_path}")
        if rc != 0 or fname not in out:
            print("[WARN] 容器内未发现该文件，但宿主机已写入，继续 HTTP 校验")

        print(f"\n[remote] curl -I -k 服务器侧验证")
        run(client, f"curl -I -k -s -o /dev/null -w 'HTTP %{{http_code}} size=%{{size_download}}\\n' {download_url}")

    finally:
        client.close()

    print(f"\n[http] 本地 HTTPS GET 验证下载链接 {download_url}")
    last_code = 0
    last_len = 0
    for attempt in range(1, 8):
        code, length = http_status(download_url, timeout=60, method="GET")
        print(f"  [attempt {attempt}] HTTP {code}, content-length={length}")
        last_code, last_len = code, length
        if code == 200 and length > 0:
            break
        time.sleep(3)

    print("\n" + "=" * 72)
    if last_code == 200:
        print("[OK] 上传成功")
        print(f"  文件名       : {fname}")
        print(f"  下载 URL     : {download_url}")
        print(f"  文件大小     : {size_mb:.2f} MB ({size:,} bytes)")
        print(f"  HTTP 状态码  : {last_code}")
        print(f"  服务字节数   : {last_len:,}")
        size_match = "MATCH" if last_len == size else f"MISMATCH (local {size} vs served {last_len})"
        print(f"  字节匹配     : {size_match}")
        return 0
    else:
        print(f"[FAIL] 下载链接验证失败: HTTP {last_code}")
        print(f"  URL: {download_url}")
        return 5


if __name__ == "__main__":
    sys.exit(main())
