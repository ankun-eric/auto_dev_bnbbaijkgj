"""Upload APK to server and verify HTTPS download URL.

Strategy: probe nginx/docker config for the static mapping, then upload
to BOTH the project root and static/apk (matching previously working
APK at static/apk path). Try several candidate URL paths and pick
the one returning HTTP 200 directly under
   /autodev/<uuid>/<APK filename>
matching task constraint (the URL must start with that base).
"""
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
BASE_URL = f"https://{HOST}/autodev/{UUID}"

LOCAL_APK = r"C:\auto_output\bnbbaijkgj\.chat_output\apk_dl\bini_health_android-v20260503-212105-c81b.apk"

now = time.strftime("%Y%m%d_%H%M%S")
import secrets
hex4 = secrets.token_hex(2)
NEW_NAME = f"app_{now}_{hex4}.apk"
print(f"Local APK: {LOCAL_APK}")
print(f"Renamed APK: {NEW_NAME}")
print(f"Size: {os.path.getsize(LOCAL_APK)} bytes")


def http_head(path: str, timeout: int = 30):
    """Return status code of HTTPS HEAD against host:443 path. Skip TLS verify."""
    ctx = ssl._create_unverified_context()
    try:
        with socket.create_connection((HOST, 443), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=HOST) as s:
                req = (
                    f"HEAD {path} HTTP/1.1\r\n"
                    f"Host: {HOST}\r\n"
                    f"User-Agent: probe/1.0\r\n"
                    f"Accept: */*\r\n"
                    f"Connection: close\r\n\r\n"
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


def run(cmd: str, hide: bool = False) -> str:
    if not hide:
        print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if not hide:
        if out:
            print(out)
        if err:
            print("[stderr]", err)
    return out


print("\n=== Inspect nginx config to find static path mapping ===")
run(f"cat {PROJECT_DIR}/nginx.conf 2>/dev/null | head -80")
run(f"docker exec {UUID}-backend cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -60 || true")
run(
    "docker ps --format '{{.Names}}' | xargs -I{} sh -c "
    "'echo === {} ===; docker exec {} sh -c \"ls /etc/nginx/conf.d/ 2>/dev/null && cat /etc/nginx/conf.d/*.conf 2>/dev/null\" 2>/dev/null' "
    f"| grep -A 30 -i '{UUID}\\|location\\|alias\\|root' | head -120 || true"
)
run("ls /etc/nginx/conf.d/ 2>/dev/null && grep -rni 'autodev\\|alias\\|6b099ed3' /etc/nginx/ 2>/dev/null | head -40 || true")
run("ls /etc/nginx/sites-enabled/ 2>/dev/null && cat /etc/nginx/sites-enabled/* 2>/dev/null | head -80 || true")
run(f"sudo -n grep -rni '{UUID}' /etc/nginx/ 2>/dev/null | head -30 || true")
run("docker ps --format '{{.Names}}' | grep -i gateway || true")

print("\n=== Test where existing APK is served from ===")
existing_apk = "bini_health_book_after_pay_20260503_203439_8a32.apk"
existing_zip = "miniprogram_20260503_212049_9128.zip"
for path in [
    f"/autodev/{UUID}/{existing_apk}",
    f"/autodev/{UUID}/static/apk/{existing_apk}",
    f"/autodev/{UUID}/{existing_zip}",
    f"/autodev/{UUID}/static/downloads/{existing_zip}",
]:
    code, head = http_head(path)
    print(f"  HEAD {path} -> {code}")
    if head and code != -1:
        for line in head.split("\r\n")[:5]:
            print(f"    {line}")

print("\n=== Inspect gateway-nginx routing ===")
run("docker ps --format '{{.Names}}' | grep -i gateway")
run("docker exec gateway-nginx sh -c 'ls /etc/nginx/conf.d/ && cat /etc/nginx/conf.d/*.conf' 2>/dev/null | head -200 || true")

ssh.close()
print("\nDONE PHASE 1")
