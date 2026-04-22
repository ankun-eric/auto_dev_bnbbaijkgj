import os, sys, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ssh_helper import create_client, run_cmd

APK_NAME = "app_20260423_021006_3b7d.apk"
SRC = f"/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/downloads/{APK_NAME}"
DST_DIR = "/var/www/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk"
DST = f"{DST_DIR}/{APK_NAME}"
URL = f"https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/{APK_NAME}"

s = create_client()
print(run_cmd(s, f"mkdir -p {DST_DIR} && cp -v {SRC} {DST} && ls -la {DST}")[0])
s.close()

print(f"HEAD check: {URL}")
req = urllib.request.Request(URL, method="HEAD")
with urllib.request.urlopen(req, timeout=30) as r:
    print("status:", r.status)
    print("content-length:", r.headers.get("Content-Length"))
    print("content-type:", r.headers.get("Content-Type"))
