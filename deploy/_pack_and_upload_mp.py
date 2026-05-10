"""Pack miniprogram/ into a zip, upload to server downloads dir, verify HTTP 200."""
import datetime
import os
import secrets
import sys
import time
import zipfile

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

LOCAL_SRC = r"C:\auto_output\bnbbaijkgj\miniprogram"
LOCAL_OUT_DIR = r"C:\auto_output\bnbbaijkgj"
REMOTE_DOWNLOADS = f"/home/ubuntu/{DEPLOY_ID}/static/downloads"
URL_BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/downloads"

EXCLUDE_DIRS = {"node_modules", ".git", ".cache", "__pycache__", ".DS_Store"}


def gen_name() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rh = secrets.token_hex(2)
    return f"miniprogram_{ts}_{rh}.zip"


def build_zip(src: str, out_path: str) -> None:
    src = os.path.abspath(src)
    base_parent = os.path.dirname(src)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, base_parent).replace(os.sep, "/")
                zf.write(full, arc)


def upload(local: str, remote: str) -> None:
    transport = paramiko.Transport((HOST, 22))
    transport.connect(username=USER, password=PASSWORD)
    try:
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.put(local, remote)
        try:
            sftp.chmod(remote, 0o644)
        except Exception:
            pass
    finally:
        transport.close()


def ssh_exec(cmd: str, timeout: int = 60) -> tuple[int, str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=20,
                   look_for_keys=False, allow_agent=False)
    try:
        _, o, e = client.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "ignore")
        err = e.read().decode("utf-8", "ignore")
        rc = o.channel.recv_exit_status()
        return rc, out + ("\n[STDERR]\n" + err if err.strip() else "")
    finally:
        client.close()


def main() -> int:
    name = gen_name()
    local_zip = os.path.join(LOCAL_OUT_DIR, name)
    remote_zip = f"{REMOTE_DOWNLOADS}/{name}"

    print(f"[1/5] filename: {name}")
    print(f"[2/5] building zip: {local_zip}")
    t0 = time.time()
    build_zip(LOCAL_SRC, local_zip)
    size = os.path.getsize(local_zip)
    print(f"  -> built in {time.time()-t0:.1f}s, size={size} bytes ({size/1024:.1f} KB)")

    print(f"[3/5] ensuring remote dir: {REMOTE_DOWNLOADS}")
    rc, out = ssh_exec(f"mkdir -p {REMOTE_DOWNLOADS} && ls -ld {REMOTE_DOWNLOADS}")
    print(out)
    if rc != 0:
        print("[FAIL] mkdir failed")
        return 1

    print(f"[4/5] uploading -> {remote_zip}")
    t0 = time.time()
    upload(local_zip, remote_zip)
    print(f"  -> uploaded in {time.time()-t0:.1f}s")

    rc, out = ssh_exec(f"ls -la {remote_zip}")
    print(out)

    url = f"{URL_BASE}/{name}"
    print(f"[5/5] verifying URL: {url}")
    rc, out = ssh_exec(f"curl -Is '{url}' | head -5")
    print(out)
    ok = "200" in out.split("\n", 1)[0]

    size_kb = size / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"

    print("\n========== RESULT ==========")
    print(f"NAME: {name}")
    print(f"SIZE: {size_str} ({size} bytes)")
    print(f"URL:  {url}")
    print(f"HTTP_OK: {ok}")
    print("============================")

    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
