"""Pack miniprogram into zip and upload to server's static dir."""
import os
import zipfile
import time
import paramiko
import socket
import ssl

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{UUID}"
STATIC_DIR = f"{PROJECT_DIR}/static"

SRC = r"C:\auto_output\bnbbaijkgj\miniprogram"
TS = time.strftime("%Y%m%d_%H%M%S")
ZIP_NAME = f"miniprogram_onsite_{TS}.zip"
LOCAL_ZIP = rf"C:\auto_output\bnbbaijkgj\.chat_output\{ZIP_NAME}"

EXCLUDES = {"node_modules", ".git", "__pycache__", ".DS_Store"}


def add_to_zip(zf, base_dir, root):
    for entry in os.listdir(root):
        if entry in EXCLUDES:
            continue
        full = os.path.join(root, entry)
        rel = os.path.relpath(full, base_dir)
        if os.path.isdir(full):
            add_to_zip(zf, base_dir, full)
        else:
            zf.write(full, arcname=rel.replace("\\", "/"))


print(f"Creating {LOCAL_ZIP} ...")
with zipfile.ZipFile(LOCAL_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    add_to_zip(zf, SRC, SRC)
print(f"  size: {os.path.getsize(LOCAL_ZIP)} bytes")

print(f"\nUploading to server ...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

# ensure miniprogram dir under static
def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    print(f"  $ {cmd[:120]}  exit={rc}")
    if out.strip():
        print(f"    {out[:300]}")
    if err.strip() and 'Warning' not in err:
        print(f"    [stderr] {err[:300]}")
    return rc, out

run(f"mkdir -p {STATIC_DIR}/miniprogram")
sftp = ssh.open_sftp()
remote_path = f"{STATIC_DIR}/miniprogram/{ZIP_NAME}"
sftp.put(LOCAL_ZIP, remote_path)
sftp.chmod(remote_path, 0o644)
attrs = sftp.stat(remote_path)
print(f"  uploaded: {attrs.st_size} bytes")
sftp.close()

# check nginx route
gw_conf = f"/home/ubuntu/gateway/conf.d/{UUID}.conf"
rc, out = run(f"grep -nE 'static|miniprogram' {gw_conf}")

# Test url
URL = f"/autodev/{UUID}/static/miniprogram/{ZIP_NAME}"


def http_head(path):
    ctx = ssl._create_unverified_context()
    try:
        with socket.create_connection((HOST, 443), timeout=20) as raw:
            with ctx.wrap_socket(raw, server_hostname=HOST) as s:
                req = f"HEAD {path} HTTP/1.1\r\nHost: {HOST}\r\nUser-Agent: probe/1.0\r\nConnection: close\r\n\r\n"
                s.sendall(req.encode("ascii"))
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
        import re
        m = re.match(r"HTTP/\d\.\d\s+(\d+)", head)
        return int(m.group(1)) if m else 0, head.split("\r\n\r\n")[0]
    except Exception as e:
        return -1, str(e)


code, head = http_head(URL)
print(f"\nHEAD {URL} -> {code}")
print(head[:400])

# also check existing miniprogram subpath
URL2 = f"/autodev/{UUID}/miniprogram/{ZIP_NAME}"
code2, head2 = http_head(URL2)
print(f"\nHEAD {URL2} -> {code2}")
print(head2[:400])

ssh.close()

import json
result = {
    "zip_name": ZIP_NAME,
    "remote_path": remote_path,
    "url_static": f"https://{HOST}{URL}",
    "url_miniprogram": f"https://{HOST}{URL2}",
    "status_static": code,
    "status_miniprogram": code2,
}
print("\n" + json.dumps(result, indent=2))
with open(r"C:\auto_output\bnbbaijkgj\.chat_output\_miniprogram_result.json", "w") as f:
    json.dump(result, f, indent=2)
