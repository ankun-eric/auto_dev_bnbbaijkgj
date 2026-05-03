"""Move zip into static/downloads/ (where existing nginx alias points) and verify."""
import paramiko, time, sys

FNAME = "miniprogram_20260503_212049_9128.zip"
URL = f"https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/{FNAME}"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd):
    si, so, se = cli.exec_command(cmd, timeout=60)
    out = so.read().decode("utf-8", errors="replace")
    err = se.read().decode("utf-8", errors="replace")
    return so.channel.recv_exit_status(), out, err

base = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

# Ensure downloads dir exists
run(f"mkdir -p {base}/static/downloads")

# Move (or copy) the file from static/ -> static/downloads/
rc, out, err = run(f"mv -f {base}/static/{FNAME} {base}/static/downloads/{FNAME}")
print("mv:", rc, out, err)

rc, out, _ = run(f"ls -la {base}/static/downloads/{FNAME}")
print("ls after move:", out)

# Quick test from server first
rc, out, _ = run(f"curl -skI -o /dev/null -w '%{{http_code}}' '{URL}'")
print("server-side curl status:", out.strip())

rc, out, _ = run(f"curl -skI '{URL}'")
print("server-side headers:")
print(out)

cli.close()
