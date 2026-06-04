import os, zipfile, time, secrets, paramiko

ROOT = r"C:\auto_output\bnbbaijkgj"
MP = os.path.join(ROOT, "miniprogram")
ts = time.strftime("%Y%m%d_%H%M%S")
rnd = secrets.token_hex(2)
ZIPNAME = f"miniprogram_glu_spo2_{ts}_{rnd}.zip"
ZIPPATH = os.path.join(ROOT, ZIPNAME)

EXCLUDE_DIRS = {"node_modules", ".git", "miniprogram_npm"}
count = 0
with zipfile.ZipFile(ZIPPATH, "w", zipfile.ZIP_DEFLATED) as z:
    for base, dirs, files in os.walk(MP):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            fp = os.path.join(base, f)
            arc = os.path.relpath(fp, MP)
            z.write(fp, arc)
            count += 1
print(f"zip: {ZIPNAME}  files={count}  size={os.path.getsize(ZIPPATH)} bytes")

# upload to gateway downloads dir (consistent with prior deploys: docker cp into gateway /data/static/apk/)
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)
sftp=c.open_sftp()
remote_tmp=f"/home/ubuntu/{ZIPNAME}"
sftp.put(ZIPPATH, remote_tmp)
sftp.close()
print("uploaded to", remote_tmp)

def sh(cmd,t=120):
    print("$",cmd); i,o,e=c.exec_command(cmd,timeout=t)
    out=o.read().decode("utf-8","ignore"); err=e.read().decode("utf-8","ignore")
    if out.strip():print(out[-2000:])
    if err.strip():print("[stderr]",err[-800:])
    return out

# find gateway downloads static dir (prior used /data/static/apk inside gateway). Discover mount.
sh("docker exec gateway-nginx sh -c 'ls -d /data/static/apk 2>/dev/null || ls -d /usr/share/nginx/html/downloads 2>/dev/null || true'")
# copy into gateway container downloads path used previously: /data/static/apk
sh(f"docker cp {remote_tmp} gateway-nginx:/data/static/apk/{ZIPNAME} 2>&1 || true")
sh(f"docker exec gateway-nginx sh -c 'ls -la /data/static/apk/{ZIPNAME} 2>/dev/null || true'")
# verify via gateway downloads route
sh(f"curl -s -o /dev/null -w '%{{http_code}}' https://{HOST}/autodev/{DID}/downloads/{ZIPNAME}; echo '  <- download url'")
c.close()
print("DOWNLOAD_URL=", f"https://{HOST}/autodev/{DID}/downloads/{ZIPNAME}")
