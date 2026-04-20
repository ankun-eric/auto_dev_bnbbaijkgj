"""Home 3 Bugs 修复 - 打包小程序 zip 并上传到服务器 static/downloads。"""
import os
import sys
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

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
rand4 = secrets.token_hex(2)
ZIP_NAME = f"miniprogram_home3bugs_{ts}_{rand4}.zip"

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
        print(f"[FATAL] miniprogram/app.json missing: {mp_dir}")
        sys.exit(2)

    local_zip = os.path.join(local_root, ZIP_NAME)
    print(f"=== Pack ===")
    print(f"src: {mp_dir}")
    print(f"out: {local_zip}")
    build_mp_zip(mp_dir, local_zip)

    with zipfile.ZipFile(local_zip, "r") as zf:
        names = zf.namelist()
        assert "app.json" in names, "zip root missing app.json"
        print(f"  root app.json=OK, app.js={'app.js' in names}, project.config.json={'project.config.json' in names}")

    print(f"\n=== Upload ===")
    c = connect()
    print(f"Connected to {HOST}")
    run(c, f"mkdir -p {STATIC_DOWNLOADS_DIR}")

    sftp = c.open_sftp()
    remote_zip = f"{STATIC_DOWNLOADS_DIR}/{ZIP_NAME}"
    remote_latest = f"{STATIC_DOWNLOADS_DIR}/miniprogram_latest.zip"
    print(f"put -> {remote_zip}")
    sftp.put(local_zip, remote_zip)
    print(f"put -> {remote_latest}")
    sftp.put(local_zip, remote_latest)
    sftp.close()

    run(c, f"chmod 644 {remote_zip} {remote_latest}")
    run(c, f"ls -lh {remote_latest} {remote_zip}")

    url_unique = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/{ZIP_NAME}"
    url_latest = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/miniprogram_latest.zip"

    print(f"\n=== Verify URL ===")
    s1, h1 = verify_url(url_unique)
    print(f"  unique: {s1}  (Content-Length={h1.get('Content-Length')})")
    s2, h2 = verify_url(url_latest)
    print(f"  latest: {s2}  (Content-Length={h2.get('Content-Length')})")

    os.remove(local_zip)
    c.close()

    ok = (s1 == 200 and s2 == 200)
    print("\n=== DONE ===")
    print(f"  ZIP:     {ZIP_NAME}")
    print(f"  unique:  {url_unique}")
    print(f"  latest:  {url_latest}")
    print(f"  verify:  unique={s1}, latest={s2} -> {'OK' if ok else 'FAIL'}")
    if not ok:
        sys.exit(3)


if __name__ == "__main__":
    main()
