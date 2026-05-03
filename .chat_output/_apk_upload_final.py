"""Upload APK to server, add root-level .apk nginx rule, reload gateway, verify URL."""
import os
import re
import sys
import time
import socket
import ssl
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{UUID}"
APK_DIR_HOST = f"{PROJECT_DIR}/static/apk"

NEW_NAME = "app_20260503_213145_bfb0.apk"
LOCAL_APK = r"C:\auto_output\bnbbaijkgj\.chat_output\apk_dl\bini_health_android-v20260503-212105-c81b.apk"

REMOTE_APK_PATH = f"{APK_DIR_HOST}/{NEW_NAME}"
URL_ROOT = f"/autodev/{UUID}/{NEW_NAME}"           # required by task
URL_APK_SUBPATH = f"/autodev/{UUID}/apk/{NEW_NAME}"  # fallback (already supported)


def http_head(path: str, timeout: int = 30):
    ctx = ssl._create_unverified_context()
    try:
        with socket.create_connection((HOST, 443), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=HOST) as s:
                req = (
                    f"HEAD {path} HTTP/1.1\r\nHost: {HOST}\r\n"
                    f"User-Agent: probe/1.0\r\nAccept: */*\r\nConnection: close\r\n\r\n"
                )
                s.sendall(req.encode("ascii"))
                data = b""
                deadline = time.time() + timeout
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
        return int(m.group(1)) if m else 0, head.split("\r\n\r\n")[0]
    except Exception as e:
        return -1, f"ERROR: {e}"


ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd: str) -> tuple[int, str, str]:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=False)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[:3000])
    if err:
        print("[stderr]", err[:500])
    return rc, out, err


print("=== Step 1: Ensure apk dir exists and is writable ===")
run(f"sudo -n chown -R ubuntu:ubuntu {APK_DIR_HOST} 2>/dev/null || true")
run(f"mkdir -p {APK_DIR_HOST}")
rc, _, _ = run(f"test -w {APK_DIR_HOST} && echo WRITABLE || echo NOT_WRITABLE")
if "NOT_WRITABLE" in _:
    # use a fresh subdir we own
    APK_DIR_HOST_ALT = f"{PROJECT_DIR}/static/_apk2"
    run(f"mkdir -p {APK_DIR_HOST_ALT}")
    REMOTE_APK_PATH = f"{APK_DIR_HOST_ALT}/{NEW_NAME}"

print("\n=== Step 2: SFTP upload APK ===")
sftp = ssh.open_sftp()
print(f"Uploading {LOCAL_APK} -> {REMOTE_APK_PATH} ...")
sftp.put(LOCAL_APK, REMOTE_APK_PATH)
sftp.chmod(REMOTE_APK_PATH, 0o644)
attrs = sftp.stat(REMOTE_APK_PATH)
print(f"Uploaded size: {attrs.st_size} bytes (local: {os.path.getsize(LOCAL_APK)})")
assert attrs.st_size == os.path.getsize(LOCAL_APK), "size mismatch!"
sftp.close()

# Determine if we used apk or _apk2 (which dir nginx alias maps to)
final_dir_name = REMOTE_APK_PATH.rsplit("/", 2)[-2]  # "apk" or "_apk2"
print(f"Stored under static/{final_dir_name}/")

print("\n=== Step 3: Test existing /apk/ subpath URL ===")
code, head = http_head(URL_APK_SUBPATH)
print(f"  HEAD {URL_APK_SUBPATH} -> {code}")
if code != -1:
    for line in head.split("\r\n")[:6]:
        print(f"    {line}")

if final_dir_name != "apk":
    print(f"WARN: file is in static/{final_dir_name}/, but nginx rule maps /apk/ -> /data/static/apk/")
    # need to also copy to static/apk via sudo
    rc, _, _ = run(f"sudo -n cp {REMOTE_APK_PATH} {APK_DIR_HOST}/{NEW_NAME} && sudo -n chmod 644 {APK_DIR_HOST}/{NEW_NAME}")
    if rc != 0:
        print("sudo copy failed; relying on writeable static/apk anyway")
    code, head = http_head(URL_APK_SUBPATH)
    print(f"  HEAD (after copy) {URL_APK_SUBPATH} -> {code}")

print("\n=== Step 4: Add root-level .apk regex location to gateway nginx ===")
conf_path = f"/home/ubuntu/gateway/conf.d/{UUID}.conf"

run(f"cat {conf_path} | grep -n 'apk' | head -10")
# Check if root-level .apk rule already exists
rc, out, _ = run(
    f"grep -E 'autodev/{UUID}/\\(\\[\\^/\\]\\+\\\\\\\\.apk\\)' {conf_path} || true"
)
if "(" in out and ".apk" in out:
    print("Root-level .apk regex location already present, skipping")
else:
    print("Adding root-level .apk regex location ...")
    snippet = f"""
# AUTO: direct apk alias for /autodev/{UUID}/*.apk -> /data/static/apk/*.apk
location ~ ^/autodev/{UUID}/([^/]+\\.apk)$ {{
    alias /data/static/apk/$1;
    types {{
        application/vnd.android.package-archive apk;
    }}
    default_type application/vnd.android.package-archive;
    add_header Content-Disposition 'attachment';
}}
"""
    # Use a heredoc to append
    backup_path = f"{conf_path}.bak.directapk.{int(time.time())}"
    rc, _, _ = run(f"cp {conf_path} {backup_path}")
    # Append snippet via SFTP read-modify-write
    sftp = ssh.open_sftp()
    with sftp.open(conf_path, "r") as f:
        cur = f.read().decode("utf-8")
    new = cur + snippet
    with sftp.open(conf_path + ".new", "w") as f:
        f.write(new.encode("utf-8"))
    sftp.close()
    run(f"mv {conf_path}.new {conf_path}")
    run(f"tail -20 {conf_path}")

print("\n=== Step 5: Test gateway nginx config and reload ===")
rc, out, err = run("docker exec gateway nginx -t")
if "successful" not in (out + err):
    print("ERROR: nginx config test failed; restoring backup")
    run(f"ls /home/ubuntu/gateway/conf.d/{UUID}.conf.bak.directapk.* | tail -1")
    sys.exit(1)
run("docker exec gateway nginx -s reload")
time.sleep(2)

print("\n=== Step 6: Verify both URLs ===")
results = {}
for label, url in [("ROOT_LEVEL", URL_ROOT), ("APK_SUBPATH", URL_APK_SUBPATH)]:
    code, head = http_head(url)
    results[label] = (code, head)
    print(f"\n  {label}: HEAD {url} -> {code}")
    for line in head.split("\r\n")[:8]:
        print(f"    {line}")

ssh.close()

# Save results
import json
with open(r"C:\auto_output\bnbbaijkgj\.chat_output\_apk_result.json", "w") as f:
    json.dump({
        "new_name": NEW_NAME,
        "remote_path": REMOTE_APK_PATH,
        "url_root": f"https://{HOST}{URL_ROOT}",
        "url_apk_subpath": f"https://{HOST}{URL_APK_SUBPATH}",
        "status_root": results.get("ROOT_LEVEL", (None, ""))[0],
        "status_subpath": results.get("APK_SUBPATH", (None, ""))[0],
    }, f, indent=2)
print("\nDONE")
