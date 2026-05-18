"""[PRD-FAMILY-AUTH-MP-V1] 打包小程序为 zip 并上传到服务器，并校验下载链接。"""
import datetime
import os
import secrets
import sys
import urllib.request
import zipfile

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ROOT = os.path.dirname(os.path.abspath(__file__))
MP_DIR = os.path.join(ROOT, "miniprogram")

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".DS_Store"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}


def make_zip(out_path):
    print(f"[pack] miniprogram -> {out_path}")
    count, total_size = 0, 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if f in EXCLUDE_FILES:
                    continue
                full = os.path.join(root, f)
                rel = "miniprogram/" + os.path.relpath(full, MP_DIR).replace("\\", "/")
                z.write(full, rel)
                count += 1
                total_size += os.path.getsize(full)
    print(f"[pack] {count} files, {total_size//1024} KB, zip {os.path.getsize(out_path)//1024} KB")


def upload(local_zip, remote_dir, fname):
    print(f"[ssh] {USER}@{HOST}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30,
                   allow_agent=False, look_for_keys=False)
    try:
        _, out, _ = client.exec_command(f"mkdir -p {remote_dir}")
        out.channel.recv_exit_status()
        sftp = client.open_sftp()
        remote_path = f"{remote_dir}/{fname}"
        print(f"[sftp] put -> {remote_path}")
        sftp.put(local_zip, remote_path)
        sftp.chmod(remote_path, 0o644)
        sftp.close()
        _, out, _ = client.exec_command(f"ls -la {remote_path}")
        print(out.read().decode("utf-8").strip())

        # 同步复制进 backend 容器的 /app/uploads（docker volume），
        # 这是 nginx /uploads → backend:/uploads StaticFiles 实际读取的目录。
        container = f"{DEPLOY_ID}-backend"
        _, out, _ = client.exec_command(
            f"docker cp {remote_path} {container}:/app/uploads/{fname}",
            timeout=60,
        )
        rc = out.channel.recv_exit_status()
        print(f"[docker cp] {container}:/app/uploads/{fname} rc={rc}")
        _, out, _ = client.exec_command(
            f"docker exec {container} ls -la /app/uploads/{fname}",
            timeout=30,
        )
        print(out.read().decode("utf-8").strip())
    finally:
        client.close()


def verify_url(url):
    print(f"[verify] HEAD {url}")
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.getcode()
            size = resp.headers.get("Content-Length")
            print(f"[verify] HTTP {code}, size={size}")
            return code == 200
    except Exception as e:
        print(f"[verify] FAIL {e}")
        return False


def main():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rnd = secrets.token_hex(2)
    fname = f"miniprogram_family_auth_{ts}_{rnd}.zip"
    local_zip = os.path.join(ROOT, fname)
    make_zip(local_zip)

    remote_dir = f"/home/ubuntu/{DEPLOY_ID}/uploads/miniprogram"
    upload(local_zip, remote_dir, fname)

    url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/uploads/{fname}"
    print(f"\n[result] Download URL: {url}")
    ok = verify_url(url)
    with open(os.path.join(ROOT, "_mp_family_auth_v1_url.txt"), "w", encoding="utf-8") as f:
        f.write(url + ("\n" if ok else "\n# WARN: HTTP not 200\n"))
    if not ok:
        sys.exit(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
