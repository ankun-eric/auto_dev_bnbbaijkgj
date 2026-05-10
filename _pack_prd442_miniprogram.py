"""
PRD-442 多端打包子 Agent A：微信小程序 zip 打包与上传
=====================================================

步骤：
  1) 用 zipfile 把 miniprogram/ 目录打包为 zip
     - 排除 node_modules/、.git/、__pycache__/、.DS_Store、*.log
     - zip 顶层即 miniprogram 目录的内容（app.json/project.config.json 等）
  2) 通过 paramiko SFTP 上传到 /data/static/miniprogram/<文件名>
  3) 用 urllib.request 验证下载 URL 返回 HTTP 200

文件命名：miniprogram_prd442_<YYYYMMDDHHMMSS>_<4位hex>.zip
"""
import os
import sys
import io
import time
import secrets
import zipfile
import datetime
import urllib.request
import urllib.error

import paramiko

# ------------------ 常量 ------------------
PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
SRC_DIR = os.path.join(PROJECT_ROOT, "miniprogram")

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PWD = "Newbang888"
SSH_PORT = 22

REMOTE_HOST_DIR = f"/home/{SSH_USER}/{DEPLOY_ID}/static/miniprogram"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}/miniprogram"

LOG_PATH = os.path.join(PROJECT_ROOT, "_pack_prd442_miniprogram.log")

# 排除规则
EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__"}
EXCLUDE_FILES = {".DS_Store"}
EXCLUDE_SUFFIX = (".log",)


# ------------------ 双写日志 ------------------
class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def should_exclude(rel_path: str, name: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDE_DIRS:
            return True
    if name in EXCLUDE_FILES:
        return True
    if name.lower().endswith(EXCLUDE_SUFFIX):
        return True
    return False


def build_zip(src_dir: str, zip_path: str) -> tuple[int, int]:
    """打包 src_dir 整个目录到 zip_path，返回 (文件数, 总字节数)。

    zip 内顶层就是 src_dir 下的内容（不带 miniprogram/ 这一层），
    例如根有 app.json、project.config.json，便于直接被微信开发者工具导入。
    """
    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(src_dir):
            # 原地剪枝
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fname in files:
                rel_dir = os.path.relpath(root, src_dir)
                rel_path = fname if rel_dir == "." else os.path.join(rel_dir, fname)
                if should_exclude(rel_path, fname):
                    continue
                full = os.path.join(root, fname)
                try:
                    sz = os.path.getsize(full)
                except OSError:
                    continue
                arcname = rel_path.replace("\\", "/")
                zf.write(full, arcname)
                file_count += 1
                total_bytes += sz
    return file_count, total_bytes


def sftp_upload(local_path: str, remote_path: str):
    print(f"[SSH] connect {SSH_USER}@{HOST}:{SSH_PORT}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PWD, timeout=30)
    try:
        remote_dir = os.path.dirname(remote_path).replace("\\", "/")
        # 用 sudo 创建目录，保证 /data/static/miniprogram/ 存在并可写
        cmd = (
            f"sudo mkdir -p {remote_dir} && "
            f"sudo chown -R {SSH_USER}:{SSH_USER} {remote_dir} && "
            f"sudo chmod -R 755 {remote_dir}"
        )
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        print(f"[remote mkdir] rc={rc} stdout={out!r} stderr={err!r}")

        sftp = ssh.open_sftp()
        try:
            print(f"[SFTP] put {local_path} -> {remote_path}")
            sftp.put(local_path, remote_path)
            st = sftp.stat(remote_path)
            print(f"[SFTP] uploaded size={st.st_size} bytes")
        finally:
            sftp.close()

        # 确保对 nginx 可读
        ssh.exec_command(f"sudo chmod 644 {remote_path}", timeout=30)[1].channel.recv_exit_status()
    finally:
        ssh.close()


def verify_download(url: str, expected_size: int) -> tuple[int, int]:
    """返回 (http_status, downloaded_bytes)"""
    print(f"[HTTP] GET {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "prd442-pack/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        status = r.status
        print(f"[HTTP] status={status} bytes={len(data)} expected={expected_size}")
        return status, len(data)


def main() -> int:
    log_f = open(LOG_PATH, "w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, log_f)
    sys.stderr = Tee(sys.__stderr__, log_f)

    print("=" * 70)
    print("PRD-442 子 Agent A · 微信小程序 zip 打包 & 上传")
    print("=" * 70)
    print(f"src       : {SRC_DIR}")
    print(f"server    : {HOST}")
    print(f"remote dir: {REMOTE_HOST_DIR}")
    print(f"base url  : {BASE_URL}")

    if not os.path.isdir(SRC_DIR):
        print(f"[FATAL] 源目录不存在：{SRC_DIR}")
        return 2

    # 校验小程序关键文件存在
    for must in ("app.json", "project.config.json"):
        if not os.path.isfile(os.path.join(SRC_DIR, must)):
            print(f"[WARN] miniprogram/ 顶层缺少 {must}（仍继续打包，但请人工核查）")

    # ---- 1) 命名 + 打包 ----
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    rand = secrets.token_hex(2)  # 4 位 hex
    zip_name = f"miniprogram_prd442_{ts}_{rand}.zip"
    zip_path = os.path.join(PROJECT_ROOT, zip_name)
    print(f"\n[1/3] 打包 -> {zip_path}")
    t0 = time.time()
    n_files, raw_bytes = build_zip(SRC_DIR, zip_path)
    zsize = os.path.getsize(zip_path)
    print(
        f"      done. files={n_files} raw={raw_bytes} bytes "
        f"zip={zsize} bytes ({zsize/1024:.1f} KiB) "
        f"in {time.time()-t0:.2f}s"
    )

    # 简单自检：列出 zip 顶层条目
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        top = sorted({n.split("/", 1)[0] for n in names})
        print(f"      zip top-level entries (前 20 个): {top[:20]}")
        for must in ("app.json", "project.config.json"):
            assert must in names, f"zip 内缺少 {must}！names sample={names[:5]}"
        print("      [check] app.json + project.config.json 在 zip 顶层 OK")

    # ---- 2) 上传 ----
    print(f"\n[2/3] 上传到 {REMOTE_HOST_DIR}/{zip_name}")
    remote_path = f"{REMOTE_HOST_DIR}/{zip_name}"
    sftp_upload(zip_path, remote_path)

    # ---- 3) 下载验证 ----
    download_url = f"{BASE_URL}/{zip_name}"
    print(f"\n[3/3] 验证下载 URL")
    status, got = verify_download(download_url, zsize)

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"zip file       : {zip_name}")
    print(f"local size     : {zsize} bytes")
    print(f"download url   : {download_url}")
    print(f"http status    : {status}")
    print(f"downloaded     : {got} bytes")
    if status == 200 and got == zsize:
        print("STATUS         : OK ✓")
        return 0
    else:
        print(f"STATUS         : FAIL (status={status}, size match={got == zsize})")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(99)
