"""Dump nginx config for deploy id."""
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
    f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}.conf",
]
for c in cmds:
    print("$ " + c)
    out, err = run(c)
    print(out)
    if err.strip():
        print("[ERR]", err)
