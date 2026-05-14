"""Find nginx route for /autodev/<id>/<filename> -> server static dir."""
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
        out = o.read().decode("utf-8", "ignore")
        err = e.read().decode("utf-8", "ignore")
        return out, err
    finally:
        c.close()


cmds = [
    "ls /home/ubuntu/gateway-nginx/conf.d/routes/ | head -50",
    f"grep -rln '{DEPLOY_ID}' /home/ubuntu/gateway-nginx/ 2>/dev/null",
    f"grep -rln 'autodev' /home/ubuntu/gateway-nginx/ 2>/dev/null | head -10",
    # also try common /etc dirs
    "docker exec gateway sh -c 'ls /etc/nginx/conf.d/ ; echo ---; cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -40' 2>&1 | head -80",
    f"docker exec gateway sh -c 'grep -rln {DEPLOY_ID} /etc/nginx/ 2>/dev/null'",
    f"docker exec gateway sh -c 'grep -rln autodev /etc/nginx/ 2>/dev/null | head -20'",
]
for c in cmds:
    print("\n$ " + c)
    out, err = run(c)
    print(out)
    if err.strip():
        print("[ERR]", err)
