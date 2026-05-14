"""Check gateway volume mounts and existing miniprogram dir."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"


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
    "docker inspect gateway --format '{{json .Mounts}}' | python3 -m json.tool 2>/dev/null || docker inspect gateway --format '{{json .Mounts}}'",
    "docker exec gateway ls -la /data/static/ 2>&1 | head -20",
    "docker exec gateway ls /data/static/miniprogram/ 2>&1 | head -20",
    # Verify an existing known file URL responds with 200
    "curl -Is 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/' | head -3",
]
for c in cmds:
    print("\n$ " + c)
    out, err = run(c)
    print(out)
    if err.strip():
        print("[ERR]", err)
