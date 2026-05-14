"""Find where H5 container serves /<file>.apk from."""
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


H5 = f"{DEPLOY_ID}-h5"
cmds = [
    f"docker inspect {H5} --format '{{{{json .Mounts}}}}' | python3 -m json.tool",
    f"docker exec {H5} ls -la /app/public/ 2>&1 | head -30",
    f"docker exec {H5} sh -c 'ls /app/public/*.apk 2>/dev/null' | head",
    # check whether the existing apk lives under public
    f"docker exec {H5} sh -c 'find /app/public -name app_prd440*.apk -maxdepth 3 2>/dev/null'",
    f"docker exec {H5} sh -c 'find / -name app_prd440*.apk 2>/dev/null' ",
]
for c in cmds:
    print("\n$ " + c)
    out, err = run(c)
    print(out)
    if err.strip():
        print("[ERR]", err)
