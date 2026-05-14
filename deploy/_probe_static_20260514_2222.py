"""Probe nginx config + filesystem to find correct static URL."""
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
    f"ls -la /home/ubuntu/{DEPLOY_ID}/uploads/static/ | tail -10",
    f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}.conf 2>&1 | head -100",
    f"docker exec gateway ls /data/static/ 2>&1 | head -20",
    f"docker inspect gateway --format '{{{{range .Mounts}}}}{{{{.Source}}}} -> {{{{.Destination}}}}\\n{{{{end}}}}'",
]
for c in cmds:
    print("\n$ " + c)
    out, err = run(c)
    print(out)
    if err.strip():
        print("[ERR]", err)
