"""Probe nginx config to find where /autodev/<id>/ static is served."""
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
        rc = o.channel.recv_exit_status()
        return rc, out, err
    finally:
        c.close()


cmds = [
    f"docker ps --format '{{{{.Names}}}}\t{{{{.Image}}}}' | head -50",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/uploads/",
    f"ls -la /home/ubuntu/{DEPLOY_ID}/uploads/static/ | head -20",
    # locate gateway-nginx config
    "docker ps --format '{{.Names}}' | grep -i nginx",
    f"grep -r '{DEPLOY_ID}' /home/ubuntu/gateway-nginx/ 2>/dev/null | head -40 || true",
    "ls /home/ubuntu/gateway-nginx/ 2>/dev/null || true",
    "ls /home/ubuntu/gateway-nginx/conf.d/ 2>/dev/null || true",
    f"find /home/ubuntu/gateway-nginx -name '*.conf' 2>/dev/null | xargs grep -l '{DEPLOY_ID}' 2>/dev/null",
]
for c in cmds:
    print("\n$ " + c)
    rc, out, err = run(c)
    print(out)
    if err.strip():
        print("[ERR]", err)
