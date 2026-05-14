"""Move uploaded APK into static/apk/ so it's served by existing nginx /apk/ route,
and additionally add a top-level direct location for the file so the requested URL also works.
"""
import paramiko, urllib.request, time

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASSWORD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR=f"/home/ubuntu/{DID}"
APK_NAME="app_pointsskin_20260514_180959_434b.apk"
SRC=f"{PROJECT_DIR}/{APK_NAME}"
APK_DIR=f"{PROJECT_DIR}/static/apk"
DST=f"{APK_DIR}/{APK_NAME}"

ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PASSWORD,timeout=30)

def run(c, check=True):
    print(f"$ {c}")
    stdin,stdout,stderr=ssh.exec_command(c, timeout=60)
    code=stdout.channel.recv_exit_status()
    out=stdout.read().decode('utf-8',errors='replace'); err=stderr.read().decode('utf-8',errors='replace')
    if out: print(out.rstrip())
    if err: print("ERR:",err.rstrip())
    print(f"[exit {code}]")
    return code,out,err

run(f"mkdir -p {APK_DIR}")
run(f"cp -f {SRC} {DST}")
run(f"chmod 644 {DST}")
run(f"ls -la {DST}")

# Also create a top-level direct location for the URL the task asked for.
# We add an *additional* conf file that includes a direct location for top-level apk files,
# placed in routes dir (already included via main conf.d/*.conf is NOT including this dir).
# Actually the conf.d/*.conf is included; we just add a new conf with a fresh file at conf.d level.
TOPLEVEL_CONF=f"/home/ubuntu/gateway/conf.d/{DID}-toplevel-apk.conf"
conf=f"""# Direct top-level APK download for project {DID}
location ~ ^/autodev/{DID}/(app_[A-Za-z0-9_\\-]+\\.apk)$ {{
    alias /data/static/apk/$1;
    types {{
        application/vnd.android.package-archive apk;
    }}
    default_type application/vnd.android.package-archive;
    add_header Content-Disposition 'attachment';
    add_header Cache-Control "public, max-age=86400" always;
}}
"""
sftp=ssh.open_sftp()
with sftp.open(TOPLEVEL_CONF, 'w') as f:
    f.write(conf)
sftp.close()
print("Wrote", TOPLEVEL_CONF)

code,out,err=run("docker exec gateway nginx -t")
if code!=0:
    print("nginx -t failed, removing toplevel conf")
    run(f"rm -f {TOPLEVEL_CONF}")
    run("docker exec gateway nginx -t")
else:
    run("docker exec gateway nginx -s reload")

ssh.close()

URLS=[
    f"https://newbb.test.bangbangvip.com/autodev/{DID}/apk/{APK_NAME}",
    f"https://newbb.test.bangbangvip.com/autodev/{DID}/{APK_NAME}",
]
time.sleep(2)
for u in URLS:
    print(f"\nHEAD {u}")
    try:
        req=urllib.request.Request(u, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"  status={r.status} length={r.headers.get('Content-Length')} type={r.headers.get('Content-Type')}")
    except urllib.error.HTTPError as e:
        print(f"  HTTPError {e.code}")
    except Exception as e:
        print(f"  {e}")
