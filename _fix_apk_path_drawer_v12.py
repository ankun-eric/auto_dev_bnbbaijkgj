"""Move the already uploaded APK into the static/apk/ subdir and verify HTTP 200."""
import paramiko
import time
import urllib.request

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
NAME = "app_20260520_011728_b076.apk"
ROOT = f"/home/ubuntu/{DEPLOY_ID}"
SRC = f"{ROOT}/{NAME}"
DST = f"{ROOT}/static/apk/{NAME}"
URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/{NAME}"


def ssh_exec(cmd, timeout=60):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20,
              look_for_keys=False, allow_agent=False)
    try:
        _, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "ignore")
        err = e.read().decode("utf-8", "ignore")
        rc = o.channel.recv_exit_status()
        return rc, out, err
    finally:
        c.close()


print(f"Moving {SRC} -> {DST}")
rc, out, err = ssh_exec(
    f"mkdir -p {ROOT}/static/apk && mv -f {SRC} {DST} && chmod 644 {DST} && ls -la {DST}"
)
print("rc=", rc)
print(out)
if err.strip():
    print("ERR:", err)

print(f"\nHEAD {URL}")
size = 0
code = ""
for i in range(10):
    try:
        req = urllib.request.Request(URL, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            cl = int(resp.headers.get("Content-Length", "0"))
            print(f"  try{i+1} status={code} content-length={cl}")
            if code == 200 and cl > 1024 * 1024:
                size = cl
                break
    except Exception as e:
        print(f"  try{i+1} err: {e}")
    time.sleep(5)

print(f"\nFINAL: code={code} size_bytes={size} size_mb={round(size/1024/1024,2)}")
print(f"DOWNLOAD_URL={URL}")
