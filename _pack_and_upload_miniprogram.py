#!/usr/bin/env python3
"""Pack miniprogram/ to zip and SFTP upload to gateway-nginx static dir."""
import os
import sys
import time
import zipfile
import paramiko

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "miniprogram")
ZIP_NAME = "miniprogram_20260504_023553_87ac.zip"
LOCAL_ZIP = os.path.join(ROOT, ZIP_NAME)

REMOTE_DIR = "/data/static/downloads"
REMOTE_ZIP = f"{REMOTE_DIR}/{ZIP_NAME}"

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__"}
EXCLUDE_FILES = {".DS_Store"}
EXCLUDE_EXT = {".log"}


def should_skip(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDE_DIRS:
            return True
    base = parts[-1]
    if base in EXCLUDE_FILES:
        return True
    _, ext = os.path.splitext(base)
    if ext.lower() in EXCLUDE_EXT:
        return True
    return False


def build_zip():
    if not os.path.isdir(SRC_DIR):
        print(f"ERR: src dir not found: {SRC_DIR}")
        sys.exit(2)
    if os.path.exists(LOCAL_ZIP):
        os.remove(LOCAL_ZIP)
    count = 0
    total_bytes = 0
    with zipfile.ZipFile(LOCAL_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(SRC_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, SRC_DIR)
                if should_skip(rel):
                    continue
                arcname = rel.replace("\\", "/")
                try:
                    sz = os.path.getsize(full)
                except OSError:
                    continue
                zf.write(full, arcname)
                count += 1
                total_bytes += sz
    zsize = os.path.getsize(LOCAL_ZIP)
    print(f"[zip] {LOCAL_ZIP}")
    print(f"[zip] files={count} src_bytes={total_bytes} zip_bytes={zsize}")
    return zsize


def with_retry(fn, label):
    delays = [10, 20, 40]
    last_exc = None
    for i in range(3):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            print(f"[retry] {label} attempt {i + 1} failed: {e}")
            if i < 2:
                time.sleep(delays[i])
    raise last_exc


STAGING_REMOTE = f"/home/ubuntu/{ZIP_NAME}"


def _ssh_run(cmd, timeout=120):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
        # Provide sudo password (passwordless sudo expected on this host)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
    finally:
        ssh.close()
    return rc, out, err


def upload():
    def _do_upload():
        t = paramiko.Transport((HOST, 22))
        t.banner_timeout = 30
        t.connect(username=USER, password=PASS)
        sftp = paramiko.SFTPClient.from_transport(t)
        try:
            sftp.put(LOCAL_ZIP, STAGING_REMOTE)
            st = sftp.stat(STAGING_REMOTE)
            print(f"[sftp] staged -> {STAGING_REMOTE} size={st.st_size}")
        finally:
            sftp.close()
            t.close()

    with_retry(_do_upload, "sftp upload to staging")

    def _do_move():
        cmd = (
            f"sudo mkdir -p {REMOTE_DIR} && "
            f"sudo mv -f {STAGING_REMOTE} {REMOTE_ZIP} && "
            f"sudo chmod 644 {REMOTE_ZIP} && "
            f"ls -la {REMOTE_ZIP}"
        )
        rc, out, err = _ssh_run(cmd)
        print(f"[ssh] mv rc={rc}\nSTDOUT: {out}\nSTDERR: {err}")
        if rc != 0:
            raise RuntimeError(f"mv failed rc={rc}: {err}")

    with_retry(_do_move, "ssh move into static dir")


if __name__ == "__main__":
    build_zip()
    upload()
    print("DONE")
