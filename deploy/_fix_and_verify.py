import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ZIP_NAME = "miniprogram_20260428_005149_2155.zip"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_ID}"
STATIC_DOWNLOADS = f"{PROJECT_DIR}/static/downloads"
CONF_PATH = f"/home/ubuntu/gateway/conf.d/{PROJECT_ID}.conf"

cmds = [
    f"mkdir -p {STATIC_DOWNLOADS}",
    f"cp {PROJECT_DIR}/{ZIP_NAME} {STATIC_DOWNLOADS}/{ZIP_NAME}",
    f"ls -la {STATIC_DOWNLOADS}/{ZIP_NAME}",
]
for cmd in cmds:
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"STDERR: {err}")

print("\nNow restoring original config (removing my added block that uses wrong path)...")
stdin, stdout, stderr = ssh.exec_command(f"cp {CONF_PATH}.bak.static {CONF_PATH}")
stdout.read()

stdin, stdout, stderr = ssh.exec_command("docker exec gateway nginx -t 2>&1")
out = stdout.read().decode() + stderr.read().decode()
print(f"nginx -t: {out}")
if "successful" in out:
    stdin, stdout, stderr = ssh.exec_command("docker exec gateway nginx -s reload")
    stdout.read()
    print("Reverted and reloaded.")

import urllib.request, ssl
url = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/{ZIP_NAME}"
print(f"\nVerifying: {url}")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
try:
    req = urllib.request.Request(url, method="HEAD")
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    print(f"HTTP {resp.status} - OK!")
    print(f"Content-Length: {resp.headers.get('Content-Length', 'unknown')}")
    print(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
except Exception as e:
    print(f"Failed: {e}")
    print("Trying downloads path...")
    url2 = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}/downloads/{ZIP_NAME}"
    print(f"Trying: {url2}")
    try:
        req = urllib.request.Request(url2, method="HEAD")
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        print(f"HTTP {resp.status} - OK!")
        print(f"Content-Length: {resp.headers.get('Content-Length', 'unknown')}")
    except Exception as e2:
        print(f"Also failed: {e2}")

ssh.close()
