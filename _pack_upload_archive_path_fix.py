"""Pack miniprogram and upload to server for BUG-FIX-AI-HOME-ARCHIVE-PATH-404-V1."""
import datetime
import os
import random
import string
import subprocess
import sys
import zipfile

ROOT = r"C:\auto_output\bnbbaijkgj"
MP_DIR = os.path.join(ROOT, "miniprogram")
SERVER = "ubuntu@newbb.test.bangbangvip.com"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram/"
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram"

EXCLUDES = {"node_modules", ".git", "__pycache__", ".DS_Store"}


def make_zip_name():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"miniprogram_archive_path_fix_{ts}_{rand}.zip"


def zip_dir(src_dir, zip_path):
    base = os.path.dirname(src_dir)
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDES]
            for f in files:
                if f in EXCLUDES:
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, base)
                zf.write(full, rel)
                count += 1
    return count


def run(cmd, check=True):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed: {cmd}")
    return r


def main():
    zip_name = make_zip_name()
    zip_path = os.path.join(ROOT, zip_name)

    print(f"[1/4] Packing {MP_DIR} -> {zip_path}")
    n = zip_dir(MP_DIR, zip_path)
    size_mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"  files={n}, size={size_mb:.2f} MB")

    print(f"[2/4] Uploading via scp to {SERVER}:{REMOTE_DIR}")
    run(f'scp -o StrictHostKeyChecking=no "{zip_path}" {SERVER}:{REMOTE_DIR}')

    print(f"[3/4] Verifying remote file")
    run(f'ssh -o StrictHostKeyChecking=no {SERVER} "ls -lh {REMOTE_DIR}{zip_name}"')

    url = f"{BASE_URL}/{zip_name}"
    print(f"[4/4] HEAD check on {url}")
    r = subprocess.run(
        f'curl -sS -o NUL -w "%{{http_code}}" "{url}"',
        shell=True, capture_output=True, text=True,
    )
    code = r.stdout.strip()
    print(f"  http_code={code}")

    print("\n==== RESULT ====")
    print(f"ZIP_NAME: {zip_name}")
    print(f"DOWNLOAD_URL: {url}")
    print(f"HTTP_STATUS: {code}")


if __name__ == "__main__":
    main()
