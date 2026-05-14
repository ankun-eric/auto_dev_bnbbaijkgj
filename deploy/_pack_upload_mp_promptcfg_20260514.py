"""Pack miniprogram/ -> zip, upload to server static dir, verify HTTPS 200.

Note: the task description's stated remote path /uploads/static is not actually
served by nginx for /autodev/<id>/<file>. The real nginx route for downloadable
miniprogram zips is /autodev/<id>/miniprogram/<file>.zip which aliases to host
/home/ubuntu/<id>/static/miniprogram/. We also copy the zip to the requested
/uploads/static dir for completeness.

Target:
  Remote real (nginx-served) dir: /home/ubuntu/<id>/static/miniprogram/
  Public URL: https://.../autodev/<id>/miniprogram/<name>.zip
"""
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
# Real nginx-mapped static dir
REMOTE_STATIC = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"
# Also mirror to the path the task description mentioned
REMOTE_UPLOADS_STATIC = f"/home/ubuntu/{DEPLOY_ID}/uploads/static"
URL_BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/miniprogram"

EXCLUDE_DIRS = {"node_modules", ".git", ".cache", "__pycache__", ".DS_Store", ".vscode", ".idea"}
EXCLUDE_FILE_SUFFIXES = (".pyc",)


def gen_name() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rh = secrets.token_hex(2)
    return f"miniprogram_promptcfg_{ts}_{rh}.zip"


def build_zip(src: str, out_path: str) -> int:
    src = os.path.abspath(src)
    base_parent = os.path.dirname(src)
    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if f.endswith(EXCLUDE_FILE_SUFFIXES) or f == ".DS_Store":
                    continue
                full = os.path.join(root, f)
                arc = os.path.relpath(full, base_parent).replace(os.sep, "/")
                zf.write(full, arc)
                count += 1
    return count


def ssh_client() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20,
              look_for_keys=False, allow_agent=False)
    return c


def ssh_exec(cmd: str, timeout: int = 60) -> tuple[int, str]:
    c = ssh_client()
    try:
        _, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "ignore")
        err = e.read().decode("utf-8", "ignore")
        rc = o.channel.recv_exit_status()
        return rc, out + (("\n[STDERR]\n" + err) if err.strip() else "")
    finally:
        c.close()


def upload(local: str, remote: str) -> None:
    t = paramiko.Transport((HOST, 22))
    t.connect(username=USER, password=PASSWORD)
    try:
        sftp = paramiko.SFTPClient.from_transport(t)
        sftp.put(local, remote)
        try:
            sftp.chmod(remote, 0o644)
        except Exception:
            pass
    finally:
        t.close()


def main() -> int:
    name = gen_name()
    local_zip = os.path.join(LOCAL_OUT_DIR, name)
    remote_zip = f"{REMOTE_STATIC}/{name}"
    url = f"{URL_BASE}/{name}"

    print(f"[1/5] zip filename: {name}")

    print(f"[2/5] building zip from: {LOCAL_SRC}")
    t0 = time.time()
    n = build_zip(LOCAL_SRC, local_zip)
    size = os.path.getsize(local_zip)
    print(f"  -> {n} files, {size} bytes ({size/1024:.1f} KB), {time.time()-t0:.1f}s")

    print(f"[3/5] ensure remote dir: {REMOTE_STATIC}")
    rc, out = ssh_exec(f"mkdir -p {REMOTE_STATIC} && ls -ld {REMOTE_STATIC}")
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

    mirror_zip = f"{REMOTE_UPLOADS_STATIC}/{name}"
    print(f"  mirror copy -> {mirror_zip}")
    ssh_exec(f"mkdir -p {REMOTE_UPLOADS_STATIC} && cp -f {remote_zip} {mirror_zip} && chmod 644 {mirror_zip}")

    print(f"[5/5] HTTP verify: {url}")
    # try a few times; nginx may need a moment
    status = ""
    for i in range(5):
        rc, out = ssh_exec(f"curl -Is '{url}' | head -1")
        status = out.strip().splitlines()[0] if out.strip() else ""
        print(f"  attempt {i+1}: {status}")
        if "200" in status:
            break
        time.sleep(1)

    ok = "200" in status

    size_kb = size / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"

    print("\n========== RESULT ==========")
    print(f"ZIP_NAME: {name}")
    print(f"ZIP_SIZE: {size_str} ({size} bytes, {n} files)")
    print(f"DOWNLOAD_URL: {url}")
    print(f"HTTP_STATUS: {status}")
    print(f"HTTP_OK: {ok}")
    print("============================")
    print(f"DOWNLOAD_URL={url}")

    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
