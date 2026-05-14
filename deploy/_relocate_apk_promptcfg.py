"""Move freshly uploaded apk into the correct static/apk/ dir and re-verify URL."""
import paramiko, urllib.request, sys, time
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
NAME = "app_promptcfg_20260514_222647_f9f6.apk"
SRC = f"/home/ubuntu/{DEPLOY_ID}/static/{NAME}"
DST = f"/home/ubuntu/{DEPLOY_ID}/static/apk/{NAME}"
MIRROR = f"/home/ubuntu/{DEPLOY_ID}/uploads/static/{NAME}"  # already created

def run(cmd, timeout=60):
    c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST,username=USER,password=PWD,timeout=20,look_for_keys=False,allow_agent=False)
    try:
        _,o,e=c.exec_command(cmd,timeout=timeout)
        return o.read().decode(),e.read().decode(),o.channel.recv_exit_status()
    finally:
        c.close()

print("== move src -> dst ==")
print(SRC, "->", DST)
o,e,rc = run(f"mkdir -p /home/ubuntu/{DEPLOY_ID}/static/apk && cp -f {SRC} {DST} && chmod 644 {DST} && ls -la {DST}")
print(o); print("[ERR]"+e if e.strip() else ""); print("rc=",rc)

# remove the stray file from static/ root (keep apk-dir copy + uploads/static mirror)
o,e,rc = run(f"rm -f {SRC} && ls -la {SRC} 2>&1 || echo REMOVED_OK")
print(o)

# verify the two URLs
B = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
for u in [f"{B}/{NAME}", f"{B}/apk/{NAME}"]:
    for i in range(5):
        try:
            req = urllib.request.Request(u, method="HEAD")
            with urllib.request.urlopen(req,timeout=20) as r:
                print(f"HEAD {u} -> {r.status}  len={r.headers.get('Content-Length')}")
                break
        except Exception as ex:
            print(f"  try{i+1} err: {ex}")
            time.sleep(3)
