"""Poll Android build status, then download APK and upload to server."""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import subprocess
import paramiko
import socket
import ssl
import re

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
TOKEN = "${GITHUB_TOKEN}"
RUN_ID = 25281427722

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{UUID}"
APK_DIR_HOST = f"{PROJECT_DIR}/static/apk"

with open(r"C:\auto_output\bnbbaijkgj\.chat_output\_apk_tag.txt") as f:
    TAG = f.read().strip()
print(f"Tag: {TAG}")

def gh_get(path):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}",
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# Poll
print("\nPolling Android build status...")
for i in range(60):  # up to 30 minutes
    info = gh_get(f"/actions/runs/{RUN_ID}")
    status = info.get("status")
    conclusion = info.get("conclusion")
    print(f"  [{i:02d}] status={status} conclusion={conclusion}  {info.get('updated_at')}")
    if status == "completed":
        if conclusion != "success":
            print(f"BUILD FAILED: {conclusion}")
            sys.exit(2)
        break
    time.sleep(30)
else:
    print("TIMEOUT waiting for build")
    sys.exit(3)

print("\nBuild succeeded. Looking for release...")
# Get release by tag
try:
    rel = gh_get(f"/releases/tags/{TAG}")
except urllib.error.HTTPError as e:
    print(f"Release not found yet: {e}")
    time.sleep(15)
    rel = gh_get(f"/releases/tags/{TAG}")

assets = rel.get("assets", [])
print(f"  release id={rel.get('id')}, assets={[a['name'] for a in assets]}")
apk_asset = next((a for a in assets if a["name"].endswith(".apk")), None)
if not apk_asset:
    print("No APK in release")
    sys.exit(4)

# Download APK
download_url = apk_asset["browser_download_url"]
local_apk = rf"C:\auto_output\bnbbaijkgj\.chat_output\apk_dl\{apk_asset['name']}"
os.makedirs(os.path.dirname(local_apk), exist_ok=True)
print(f"\nDownloading {download_url} -> {local_apk}")
req = urllib.request.Request(
    download_url,
    headers={"Authorization": f"token {TOKEN}", "Accept": "application/octet-stream"},
)
with urllib.request.urlopen(req, timeout=600) as r:
    with open(local_apk, "wb") as f:
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)
size = os.path.getsize(local_apk)
print(f"  downloaded: {size} bytes")

# Upload to server
new_name = f"app_onsite_{int(time.time())}.apk"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    print(f"  $ {cmd[:120]}  exit={rc}")
    if out.strip():
        print(f"    {out[:300]}")
    return rc, out


run(f"mkdir -p {APK_DIR_HOST}")
sftp = ssh.open_sftp()
remote_path = f"{APK_DIR_HOST}/{new_name}"
print(f"\nUploading to {remote_path} ...")
sftp.put(local_apk, remote_path)
sftp.chmod(remote_path, 0o644)
attrs = sftp.stat(remote_path)
print(f"  uploaded size: {attrs.st_size}")
assert attrs.st_size == size
sftp.close()
ssh.close()

# verify
def http_head(path):
    ctx = ssl._create_unverified_context()
    with socket.create_connection((HOST, 443), timeout=20) as raw:
        with ctx.wrap_socket(raw, server_hostname=HOST) as s:
            s.sendall(f"HEAD {path} HTTP/1.1\r\nHost: {HOST}\r\nUser-Agent: probe/1.0\r\nConnection: close\r\n\r\n".encode())
            data = b""
            deadline = time.time() + 15
            while time.time() < deadline:
                try:
                    chunk = s.recv(4096)
                except socket.timeout:
                    break
                if not chunk:
                    break
                data += chunk
                if b"\r\n\r\n" in data:
                    break
    head = data.decode("iso-8859-1", errors="replace")
    m = re.match(r"HTTP/\d\.\d\s+(\d+)", head)
    return (int(m.group(1)) if m else 0), head.split("\r\n\r\n")[0]


URL_ROOT = f"/autodev/{UUID}/{new_name}"
URL_SUB = f"/autodev/{UUID}/apk/{new_name}"
c1, h1 = http_head(URL_ROOT)
c2, h2 = http_head(URL_SUB)
print(f"\nHEAD {URL_ROOT} -> {c1}")
print(f"HEAD {URL_SUB}  -> {c2}")

result = {
    "tag": TAG,
    "apk_name": new_name,
    "remote_path": remote_path,
    "size": size,
    "url_root": f"https://{HOST}{URL_ROOT}",
    "url_apk": f"https://{HOST}{URL_SUB}",
    "status_root": c1,
    "status_apk": c2,
    "github_release_url": rel.get("html_url"),
    "github_apk_download": download_url,
}
print("\n" + json.dumps(result, indent=2))
with open(r"C:\auto_output\bnbbaijkgj\.chat_output\_apk_final.json", "w") as f:
    json.dump(result, f, indent=2)
print("\nDONE")
