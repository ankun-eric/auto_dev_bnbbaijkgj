"""
修复脚本：复用已下载的 APK，仅重新上传到 nginx 实际 alias 目录 /home/ubuntu/<PID>/static/apk/
"""
from __future__ import annotations
import json, secrets, time
from datetime import datetime
from pathlib import Path

import paramiko

REPO = Path(r"C:\auto_output\bnbbaijkgj")
PID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PID}"
SSH = ("newbb.test.bangbangvip.com", "ubuntu", "Newbang888")
TAG = "android-v20260517-123838-dc67"

apk_local = REPO / "_apk_downloads" / f"bini_health_{TAG}.apk"
assert apk_local.exists(), apk_local

ts = datetime.now().strftime("%Y%m%d%H%M%S")
rand = secrets.token_hex(3)
remote_name = f"app_{ts}_{rand}.apk"
remote_tmp = f"/tmp/{remote_name}"
persist_dir = f"/home/ubuntu/{PID}/static/apk"
persist_path = f"{persist_dir}/{remote_name}"
backup_dir = f"/home/ubuntu/{PID}/h5-web/public"
backup_path = f"{backup_dir}/{remote_name}"

print(f"[*] uploading {apk_local.name} -> {remote_tmp}")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH[0], username=SSH[1], password=SSH[2], timeout=30)
try:
    sftp = c.open_sftp()
    try:
        sftp.put(str(apk_local), remote_tmp)
    finally:
        sftp.close()
    cmd = (
        f"set -e; "
        f"sudo -n mkdir -p {persist_dir}; "
        f"sudo -n cp {remote_tmp} {persist_path}; "
        f"sudo -n chmod 644 {persist_path}; "
        f"sudo -n mkdir -p {backup_dir}; "
        f"sudo -n cp {remote_tmp} {backup_path}; "
        f"sudo -n chmod 644 {backup_path}; "
        f"rm -f {remote_tmp}; "
        f"echo NGINX_DIR:; ls -la {persist_path}; "
        f"echo BACKUP_DIR:; ls -la {backup_path}; "
        f"echo STATIC_TREE:; sudo -n ls -la /home/ubuntu/{PID}/static/ 2>&1 | head -5; "
        f"echo APK_LISTING:; sudo -n ls -la /home/ubuntu/{PID}/static/apk/ 2>&1 | head -10"
    )
    i, o, e = c.exec_command(cmd, timeout=180)
    out = o.read().decode(errors="replace")
    err = e.read().decode(errors="replace")
    rc = o.channel.recv_exit_status()
    print("OUT:\n" + out)
    if err:
        print("ERR:\n" + err)
    print("rc=", rc)
finally:
    c.close()

url = f"{BASE_URL}/apk/{remote_name}"
print(f"\nDownload URL: {url}")

import urllib.request, ssl
ctx = ssl.create_default_context()
for attempt in range(6):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            print(f"attempt {attempt+1}: HTTP {resp.status}  "
                  f"Content-Length={resp.headers.get('Content-Length')}  "
                  f"Content-Type={resp.headers.get('Content-Type')}")
            if resp.status == 200:
                final = {
                    "tag": TAG,
                    "apk_local": str(apk_local),
                    "apk_size": apk_local.stat().st_size,
                    "server_filename": remote_name,
                    "download_url": url,
                    "github_release_url": f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/{TAG}",
                    "http_status": resp.status,
                    "content_length": resp.headers.get("Content-Length"),
                    "content_type": resp.headers.get("Content-Type"),
                    "build_success": True,
                }
                (REPO / "_build_apk_v3_summary.json").write_text(
                    json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
                print("SUMMARY:\n" + json.dumps(final, ensure_ascii=False, indent=2))
                break
    except Exception as ex:
        print(f"attempt {attempt+1} error: {ex}")
    time.sleep(5 * (attempt + 1))
