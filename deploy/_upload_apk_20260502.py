"""上传 APK 到服务器，复制到多个常用路径，并验证 HTTPS 下载可达"""
import paramiko, time, sys, os, urllib.request

LOCAL = r"C:\tmp\apk_download\app_20260502_153125_90e6.apk"
FNAME = "app_20260502_153125_90e6.apk"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
DOMAIN = "newbb.test.bangbangvip.com"
SIZE = os.path.getsize(LOCAL)
print(f"[*] local file: {LOCAL} ({SIZE} bytes, {SIZE/1024/1024:.2f} MB)")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(DOMAIN, username="ubuntu", password="Newbang888", timeout=60)

print("[*] uploading via SFTP ...")
t = time.time()
sftp = c.open_sftp()
sftp.put(LOCAL, f"/tmp/{FNAME}")
sftp.close()
print(f"[*] uploaded in {time.time()-t:.1f}s")

def run(cmd, timeout=120):
    print(f"\n>>> {cmd[:300]}")
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode(errors="ignore")
    err = e.read().decode(errors="ignore")
    if out.strip():
        print(out[-2000:])
    if err.strip():
        print("ERR:", err[-1000:])
    return out

# Place into known-served dirs: static/apk, static/downloads, backend/uploads
APK_DIR = f"{PROJ}/static/apk"
DL_DIR = f"{PROJ}/static/downloads"
UP_DIR = f"{PROJ}/backend/uploads"

cmd = (
    f"echo Newbang888 | sudo -S mkdir -p {APK_DIR} {DL_DIR} {UP_DIR} && "
    f"echo Newbang888 | sudo -S cp /tmp/{FNAME} {APK_DIR}/{FNAME} && "
    f"echo Newbang888 | sudo -S cp /tmp/{FNAME} {DL_DIR}/{FNAME} && "
    f"echo Newbang888 | sudo -S cp /tmp/{FNAME} {UP_DIR}/{FNAME} && "
    f"echo Newbang888 | sudo -S chmod 644 {APK_DIR}/{FNAME} {DL_DIR}/{FNAME} {UP_DIR}/{FNAME} && "
    f"ls -la {APK_DIR}/{FNAME} {DL_DIR}/{FNAME} {UP_DIR}/{FNAME}"
)
run(cmd)

# Also try docker cp into backend container's /app/uploads (uploads volume)
container = f"{DEPLOY_ID}-backend"
run(f"echo Newbang888 | sudo -S docker ps --format '{{{{.Names}}}}' | grep -E '{DEPLOY_ID}.*backend' || true")
run(f"echo Newbang888 | sudo -S docker cp /tmp/{FNAME} {container}:/app/uploads/{FNAME} && echo OK || echo FAIL")
# Also try the lower-cased / alt name
run(f"echo Newbang888 | sudo -S docker exec {container} ls -la /app/uploads/{FNAME} || true")

c.close()

# Probe URLs
candidates = [
    f"https://{DOMAIN}/autodev/{DEPLOY_ID}/uploads/{FNAME}",
    f"https://{DOMAIN}/autodev/{DEPLOY_ID}/apk/{FNAME}",
    f"https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/{FNAME}",
    f"https://{DOMAIN}/autodev/{DEPLOY_ID}/static/apk/{FNAME}",
    f"https://{DOMAIN}/autodev/{DEPLOY_ID}/static/uploads/{FNAME}",
]
import ssl
ctx = ssl.create_default_context()
for u in candidates:
    try:
        req = urllib.request.Request(u, method="HEAD", headers={"User-Agent":"Mozilla/5.0"})
        r = urllib.request.urlopen(req, timeout=20, context=ctx)
        size = r.headers.get("Content-Length", "?")
        ctype = r.headers.get("Content-Type", "?")
        print(f"[OK] {r.status} size={size} type={ctype}  {u}")
    except urllib.error.HTTPError as he:
        print(f"[{he.code}] {u}")
    except Exception as e:
        print(f"[ERR] {type(e).__name__}: {e} {u}")
