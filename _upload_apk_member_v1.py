"""Upload new APK (member center v1.0) to server and verify URL."""
import paramiko, urllib.request, time, os, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DID}"
APK_DIR = f"{PROJECT_DIR}/static/apk"

APK_NAME = open("_apk_name.txt").read().strip()
LOCAL = os.path.join("_apk_tmp", APK_NAME)
DST = f"{APK_DIR}/{APK_NAME}"

print(f"Local: {LOCAL}  size={os.path.getsize(LOCAL)}")
print(f"Remote: {DST}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(c):
    print(f"$ {c}")
    _, stdout, stderr = ssh.exec_command(c, timeout=120)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out:
        print(out.rstrip())
    if err:
        print("ERR:", err.rstrip())
    print(f"[exit {code}]")
    return code, out, err


run(f"mkdir -p {APK_DIR}")

sftp = ssh.open_sftp()
sftp.put(LOCAL, DST)
sftp.close()
print("Uploaded via SFTP")

run(f"chmod 644 {DST}")
run(f"ls -la {DST}")

# Make sure the top-level alias conf exists (idempotent)
TOPLEVEL_CONF = f"/home/ubuntu/gateway/conf.d/{DID}-toplevel-apk.conf"
code, out, _ = run(f"test -f {TOPLEVEL_CONF} && echo EXISTS || echo MISSING")
if "MISSING" in out:
    print("Toplevel conf missing, recreating...")
    conf = (
        f"# Direct top-level APK download for project {DID}\n"
        f"location ~ ^/autodev/{DID}/(app_[A-Za-z0-9_\\-]+\\.apk)$ {{\n"
        f"    alias /data/static/apk/$1;\n"
        f"    types {{\n"
        f"        application/vnd.android.package-archive apk;\n"
        f"    }}\n"
        f"    default_type application/vnd.android.package-archive;\n"
        f"    add_header Content-Disposition 'attachment';\n"
        f"    add_header Cache-Control \"public, max-age=86400\" always;\n"
        f"}}\n"
    )
    sftp = ssh.open_sftp()
    with sftp.open(TOPLEVEL_CONF, 'w') as f:
        f.write(conf)
    sftp.close()
    run("docker exec gateway nginx -t && docker exec gateway nginx -s reload")

ssh.close()

URLS = [
    f"https://newbb.test.bangbangvip.com/autodev/{DID}/{APK_NAME}",
    f"https://newbb.test.bangbangvip.com/autodev/{DID}/apk/{APK_NAME}",
]
time.sleep(2)
ok_url = None
for u in URLS:
    print(f"\nHEAD {u}")
    try:
        req = urllib.request.Request(u, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"  status={r.status} length={r.headers.get('Content-Length')} type={r.headers.get('Content-Type')}")
            if r.status == 200 and not ok_url:
                ok_url = u
    except urllib.error.HTTPError as e:
        print(f"  HTTPError {e.code}")
    except Exception as e:
        print(f"  {e}")

print("\n=== RESULT ===")
print(f"APK_NAME={APK_NAME}")
print(f"OK_URL={ok_url}")
sys.exit(0 if ok_url else 1)
