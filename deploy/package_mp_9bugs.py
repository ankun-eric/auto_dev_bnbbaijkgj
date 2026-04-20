"""9 Bugs 修复 - 打包小程序 zip 并上传到服务器 static/downloads。

- zip 解压后直接是小程序根（含 app.json / app.js / project.config.json）
- 文件名唯一: miniprogram_9bugs_YYYYMMDD_HHMMSS_xxxx.zip
- 覆盖 miniprogram_latest.zip
- 上传后 HTTP HEAD 验证可下载
"""
import os
import sys
import time
import secrets
import zipfile
import fnmatch
import datetime
import paramiko
import urllib.request

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
STATIC_DOWNLOADS_DIR = f"{PROJECT_DIR}/static/downloads"

# 生成唯一文件名
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
rand4 = secrets.token_hex(2)  # 4位十六进制
ZIP_NAME = f"miniprogram_9bugs_{ts}_{rand4}.zip"

SKIP_DIRS = {"node_modules", ".git", "dist", "miniprogram_npm"}
SKIP_FILES_EXACT = {".DS_Store"}
SKIP_FILE_PATTERNS = ["*.log"]


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)
    return c


def run(c, cmd, timeout=180):
    print(f"\n$ {cmd[:200]}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-1200:])
    if err:
        print(f"[stderr] {err[-600:]}")
    print(f"[exit {code}]")
    return code


def should_skip_file(fn):
    if fn in SKIP_FILES_EXACT:
        return True
    for p in SKIP_FILE_PATTERNS:
        if fnmatch.fnmatch(fn, p):
            return True
    return False


def build_mp_zip(mp_dir, out_path):
    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(mp_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in files:
                if should_skip_file(fn):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, mp_dir)
                # 解压后直接是小程序根（不加顶层 miniprogram/ 前缀）
                zf.write(full, arcname=rel.replace(os.sep, "/"))
                count += 1
    size = os.path.getsize(out_path)
    print(f"  [mp zip] {count} files -> {out_path} ({size} bytes, {size/1024/1024:.2f} MB)")
    return count, size


def verify_url(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return f"ERR:{e}", {}


def main():
    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mp_dir = os.path.join(local_root, "miniprogram")
    if not os.path.isfile(os.path.join(mp_dir, "app.json")):
        print(f"[FATAL] miniprogram/app.json 不存在: {mp_dir}")
        sys.exit(2)

    local_zip = os.path.join(local_root, ZIP_NAME)
    print(f"=== 打包 ===")
    print(f"源目录: {mp_dir}")
    print(f"输出:   {local_zip}")
    count, size = build_mp_zip(mp_dir, local_zip)

    # 校验 zip 根级必须包含 app.json
    with zipfile.ZipFile(local_zip, "r") as zf:
        names = zf.namelist()
        assert "app.json" in names, "zip 根没有 app.json"
        has_appjs = "app.js" in names
        has_proj = "project.config.json" in names
        print(f"  root app.json=OK, app.js={has_appjs}, project.config.json={has_proj}")

    print(f"\n=== 上传 ===")
    c = connect()
    print(f"Connected to {HOST}")
    run(c, f"mkdir -p {STATIC_DOWNLOADS_DIR}")

    sftp = c.open_sftp()
    remote_zip = f"{STATIC_DOWNLOADS_DIR}/{ZIP_NAME}"
    remote_latest = f"{STATIC_DOWNLOADS_DIR}/miniprogram_latest.zip"
    print(f"上传 -> {remote_zip}")
    sftp.put(local_zip, remote_zip)
    print(f"上传 -> {remote_latest}")
    sftp.put(local_zip, remote_latest)
    sftp.close()

    run(c, f"chmod 644 {remote_zip} {remote_latest}")
    run(c, f"ls -lh {remote_latest} {remote_zip}")

    url_unique = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/{ZIP_NAME}"
    url_latest = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/miniprogram_latest.zip"

    print(f"\n=== 验证 URL ===")
    s1, h1 = verify_url(url_unique)
    print(f"  unique: {s1}  (Content-Length={h1.get('Content-Length')})")
    s2, h2 = verify_url(url_latest)
    print(f"  latest: {s2}  (Content-Length={h2.get('Content-Length')})")

    os.remove(local_zip)
    c.close()

    ok = (s1 == 200 and s2 == 200)
    print("\n=== DONE ===")
    print(f"  ZIP:        {ZIP_NAME}")
    print(f"  唯一链接:   {url_unique}")
    print(f"  最新链接:   {url_latest}")
    print(f"  验证结果:   unique={s1}, latest={s2}  -> {'OK' if ok else 'FAIL'}")
    if not ok:
        sys.exit(3)


if __name__ == "__main__":
    main()
