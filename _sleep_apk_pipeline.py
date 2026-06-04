#!/usr/bin/env python3
"""[PRD-SLEEP-ALIGN-BP-V1] 下载 Android release APK -> 上传 gateway downloads/，校验 iOS release"""
import subprocess, os, time, ssl, urllib.request
import paramiko

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST, USER, PWD = "newbb.test.bangbangvip.com", "ubuntu", "Newbang888"
BASE = f"https://{HOST}/autodev/{DEPLOY_ID}"

atag = open("_sleep_android_tag.txt").read().strip()
itag = open("_sleep_ios_tag.txt").read().strip()
print("ATAG", atag, "ITAG", itag)

dl = os.path.abspath("apk_download")
os.makedirs(dl, exist_ok=True)

# 1) download apk
subprocess.run(f'gh release download {atag} -R {REPO} --pattern "*.apk" --dir "{dl}" --clobber',
               shell=True, check=True, timeout=600)
apk = None
for f in os.listdir(dl):
    if f.endswith(".apk") and atag in f:
        apk = os.path.join(dl, f); break
if not apk:
    cand = [os.path.join(dl, f) for f in os.listdir(dl) if f.endswith(".apk")]
    apk = max(cand, key=os.path.getmtime)
print("local apk", apk, os.path.getsize(apk)/1024/1024, "MB")

# 2) upload to gateway downloads/
ts = time.strftime("%Y%m%d-%H%M%S")
remote_name = f"app_sleep_align_{ts}.apk"
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=60)
sftp = c.open_sftp(); sftp.put(apk, f"/home/ubuntu/{remote_name}"); sftp.close()
cmd = (f"docker cp /home/ubuntu/{remote_name} gateway-nginx:/data/static/apk/{remote_name} && "
       f"docker exec gateway-nginx ls -l /data/static/apk/{remote_name} && rm -f /home/ubuntu/{remote_name}")
_, o, e = c.exec_command(cmd, timeout=180)
print(o.read().decode(errors="ignore")); 
err = e.read().decode(errors="ignore")
if err.strip(): print("STDERR", err)
c.close()

apk_url = f"{BASE}/downloads/{remote_name}"
ios_release = f"https://github.com/{REPO}/releases/tag/{itag}"
ipa_url = f"https://github.com/{REPO}/releases/download/{itag}/bini_health_{itag}.ipa"

# 3) verify apk
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
code = "ERR"
try:
    req = urllib.request.Request(apk_url, method="HEAD", headers={"User-Agent":"Mozilla/5.0"})
    r = urllib.request.urlopen(req, timeout=30, context=ctx); code = r.status
except Exception as ex:
    code = f"ERR {ex}"
print(f"\nAPK_URL {apk_url} HTTP {code}")
print(f"IOS_RELEASE {ios_release}")
print(f"IPA_URL {ipa_url}")
open("_sleep_app_urls.txt","w").write(f"APK {apk_url} HTTP={code}\nIOS {ios_release}\nIPA {ipa_url}\n")
