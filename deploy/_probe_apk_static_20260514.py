"""Probe nginx static mapping for APK serving on this deploy id."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(cmd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20,
              look_for_keys=False, allow_agent=False)
    try:
        _, o, e = c.exec_command(cmd, timeout=60)
        return o.read().decode("utf-8", "ignore"), e.read().decode("utf-8", "ignore")
    finally:
        c.close()


cmds = [
    f"ls -la /home/ubuntu/{DEPLOY_ID}/",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/static/ 2>&1 | head -30",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/uploads/ 2>&1 | head -30",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/uploads/static/ 2>&1 | head -30",
    "docker ps --format '{{.Names}}' | grep -i nginx",
    "docker inspect gateway --format '{{json .Mounts}}' 2>/dev/null | python3 -m json.tool 2>/dev/null | head -60",
    f"docker exec gateway ls /data/static/ 2>&1 | head -30",
    f"docker exec gateway sh -c 'ls -la /data/static/ 2>&1' | head -30",
    # find conf entries for this deploy id
    "docker exec gateway grep -rn '" + DEPLOY_ID + "' /etc/nginx/ 2>/dev/null | head -40",
    # any apk in the apk dir already
    f"ls -la /home/ubuntu/{DEPLOY_ID}/static/apk/ 2>&1 | head -20",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/static/downloads/ 2>&1 | head -20",
    # confirm an old apk url still works
    f"curl -Is 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/apk/' 2>&1 | head -5",
]
for c in cmds:
    print("\n$ " + c)
    out, err = run(c)
    print(out)
    if err.strip():
        print("[ERR]", err)
