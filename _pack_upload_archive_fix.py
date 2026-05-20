"""Package miniprogram and upload to server for BUG-FIX-AI-HOME-ARCHIVE-PATH-404-V1."""
import datetime
import os
import random
import string
import subprocess
import sys
import zipfile

ROOT = r"C:/auto_output/bnbbaijkgj"
MP_DIR = os.path.join(ROOT, "miniprogram")
SERVER = "ubuntu@newbb.test.bangbangvip.com"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".idea", ".vscode"}


def gen_zip_name():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"miniprogram_archive_path_fix_{ts}_{rnd}.zip"


def zip_dir(src, out_path):
    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, src)
                zf.write(full, rel)
                count += 1
    return count


def run(cmd, check=True):
    print(f"$ {cmd}", flush=True)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout)
    if r.stderr:
        print("STDERR:", r.stderr)
    if check and r.returncode != 0:
        sys.exit(f"Command failed: {cmd} (rc={r.returncode})")
    return r


def main():
    zip_name = gen_zip_name()
    zip_path = os.path.join(ROOT, zip_name)
    print(f"Packing {MP_DIR} -> {zip_path}")
    n = zip_dir(MP_DIR, zip_path)
    size = os.path.getsize(zip_path)
    print(f"Zipped {n} files, size={size} bytes")

    scp_cmd = (
        f'scp -o StrictHostKeyChecking=no "{zip_path}" '
        f'{SERVER}:{REMOTE_DIR}/{zip_name}'
    )
    run(scp_cmd)

    ls_cmd = (
        f'ssh -o StrictHostKeyChecking=no {SERVER} '
        f'"ls -l {REMOTE_DIR}/{zip_name}"'
    )
    run(ls_cmd)

    url = f"{BASE_URL}/{zip_name}"
    curl_cmd = f'curl -sS -o NUL -w "%{{http_code}}" "{url}"'
    r = run(curl_cmd, check=False)
    status = (r.stdout or "").strip()

    print("\n========= RESULT =========")
    print(f"ZIP_NAME: {zip_name}")
    print(f"DOWNLOAD_URL: {url}")
    print(f"HTTP_STATUS: {status}")
    print("==========================")


if __name__ == "__main__":
    main()
