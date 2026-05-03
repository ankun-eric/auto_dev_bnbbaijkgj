"""Package miniprogram, upload to server via SFTP, verify URL."""
from __future__ import annotations

import os
import sys
import time
import secrets
import zipfile
import datetime
import subprocess
import posixpath
from pathlib import Path

import paramiko

# ----- Config -----
PROJECT_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
MP_DIR = PROJECT_ROOT / "miniprogram"
OUT_DIR = PROJECT_ROOT / ".chat_output"
OUT_DIR.mkdir(exist_ok=True)

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{PROJECT_ID}"

EXCLUDE_DIRS = {"node_modules", ".git", "miniprogram_npm", "__pycache__", ".idea", ".vscode"}
EXCLUDE_SUFFIX = {".log"}


def gen_filename() -> str:
    now = datetime.datetime.now()
    rand = secrets.token_hex(2)
    return f"miniprogram_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}_{rand}.zip"


def make_zip(zip_path: Path) -> int:
    """Pack miniprogram dir into zip; entries are relative to MP_DIR (no extra wrapper)."""
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if any(f.endswith(s) for s in EXCLUDE_SUFFIX):
                    continue
                full = Path(root) / f
                arc = full.relative_to(MP_DIR).as_posix()
                zf.write(full, arc)
                count += 1
    return count


def ssh_connect(retries: int = 3) -> paramiko.SSHClient:
    last = None
    for i in range(retries):
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30, allow_agent=False, look_for_keys=False)
            return cli
        except Exception as e:
            last = e
            print(f"[ssh] connect retry {i+1}/{retries}: {e}")
            time.sleep(2)
    raise RuntimeError(f"ssh connect failed: {last}")


def run(cli: paramiko.SSHClient, cmd: str) -> tuple[int, str, str]:
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def find_static_dir(cli: paramiko.SSHClient) -> str:
    """Find the static dir served at BASE_URL/<file>."""
    print(f"[probe] listing {REMOTE_PROJECT_DIR}")
    rc, out, err = run(cli, f"ls -la {REMOTE_PROJECT_DIR}/")
    print(out)
    if err:
        print("STDERR:", err)

    # look for existing static-like dirs
    candidates = []
    for name in ("static", "public", "uploads", "downloads", "dist"):
        rc, out, _ = run(cli, f"test -d {REMOTE_PROJECT_DIR}/{name} && echo YES || echo NO")
        if "YES" in out:
            candidates.append(f"{REMOTE_PROJECT_DIR}/{name}")
    print(f"[probe] candidate dirs: {candidates}")

    # check docker-compose for nginx static mount
    rc, out, _ = run(cli, f"cat {REMOTE_PROJECT_DIR}/docker-compose.yml 2>/dev/null | head -200")
    print("[probe] docker-compose.yml head:")
    print(out)

    # check nginx config dir
    rc, out, _ = run(cli, f"ls {REMOTE_PROJECT_DIR}/nginx 2>/dev/null; ls {REMOTE_PROJECT_DIR}/gateway* 2>/dev/null")
    print("[probe] nginx/gateway dirs:")
    print(out)

    # try to find any pre-existing zip / apk to follow precedent
    rc, out, _ = run(cli, f"find {REMOTE_PROJECT_DIR} -maxdepth 4 -type f \\( -name '*.zip' -o -name '*.apk' \\) 2>/dev/null | head -20")
    print("[probe] existing zip/apk files:")
    print(out)

    return ""  # actual decision below


def main():
    fname = gen_filename()
    zip_path = OUT_DIR / fname
    print(f"[step 1] generated filename: {fname}")

    print(f"[step 2] zipping {MP_DIR} -> {zip_path}")
    n = make_zip(zip_path)
    size = zip_path.stat().st_size
    print(f"[step 2] packed {n} files, size={size} bytes")

    # quick verify zip content (first-level entries)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        first_level = sorted({n.split('/')[0] for n in names})
    print(f"[step 2] first-level entries: {first_level[:20]}")
    assert "app.json" in names, "app.json missing at root!"
    assert "app.js" in names, "app.js missing at root!"

    print("[step 3] connecting SSH")
    cli = ssh_connect()
    try:
        find_static_dir(cli)

        # Decide remote dir: prefer existing static; else create one
        remote_dir = f"{REMOTE_PROJECT_DIR}/static"
        run(cli, f"mkdir -p {remote_dir}")

        remote_path = f"{remote_dir}/{fname}"
        print(f"[step 3] uploading -> {remote_path}")

        sftp = cli.open_sftp()
        for attempt in range(3):
            try:
                sftp.put(str(zip_path), remote_path)
                break
            except Exception as e:
                print(f"[sftp] upload retry {attempt+1}: {e}")
                time.sleep(2)
        else:
            raise RuntimeError("sftp upload failed")
        sftp.close()

        rc, out, _ = run(cli, f"ls -la {remote_path}")
        print(f"[step 3] remote ls: {out.strip()}")

        # Inspect nginx routing
        print("[step 3.5] checking nginx route mapping for autodev/<id>/")
        rc, out, _ = run(cli, "docker ps --format '{{.Names}}\\t{{.Image}}' | grep -i nginx")
        print(f"[probe] nginx containers: {out}")

        rc, out, _ = run(cli, f"docker inspect $(docker ps -q --filter name=gateway-nginx) 2>/dev/null | head -200")
        # not always useful; show truncated

        # Check generic gateway-nginx config that maps autodev/<id> to the static dir
        rc, out, _ = run(cli, "find /home/ubuntu -maxdepth 5 -type f -name '*.conf' 2>/dev/null | xargs grep -l '" + PROJECT_ID + "' 2>/dev/null | head -5")
        print(f"[probe] confs mentioning project id: {out}")

        # Try to fetch URL from inside server first
        url = f"{BASE_URL}/{fname}"
        print(f"[step 4] verifying {url}")

        last_status = None
        last_headers = ""
        for attempt in range(3):
            rc, out, err = run(cli, f"curl -skI -o /dev/null -w '%{{http_code}}' '{url}'")
            last_status = out.strip()
            print(f"[verify {attempt+1}] HTTP status: {last_status}")
            rc2, out2, _ = run(cli, f"curl -skI '{url}' | head -20")
            last_headers = out2
            print(f"[verify {attempt+1}] headers:\n{out2}")
            if last_status == "200":
                break
            time.sleep(2)

        return {
            "filename": fname,
            "remote_path": remote_path,
            "url": url,
            "status": last_status,
            "headers": last_headers,
            "size": size,
        }
    finally:
        cli.close()


if __name__ == "__main__":
    res = main()
    print("\n=== RESULT ===")
    for k, v in res.items():
        print(f"{k}: {v}")
