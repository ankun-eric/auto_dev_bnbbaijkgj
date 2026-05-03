import os, sys, json, paramiko

PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

zips = sorted([f for f in os.listdir(PROJECT_ROOT) if f.startswith("miniprogram_book_after_pay_") and f.endswith(".zip")])
fname = zips[-1]
local_path = os.path.join(PROJECT_ROOT, fname)
size = os.path.getsize(local_path)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd):
    si, so, se = c.exec_command(cmd)
    return so.read().decode(errors="replace"), se.read().decode(errors="replace"), so.channel.recv_exit_status()

# Real host path that maps to /data/static/downloads inside nginx container
host_dir = f"/home/ubuntu/{DEPLOY_ID}/static/downloads"

# Ensure dir exists
o, _, _ = run(f"mkdir -p {host_dir} && ls -ld {host_dir}")
print(f"mkdir: {o}", file=sys.stderr)

remote_path = f"{host_dir}/{fname}"
sftp = c.open_sftp()
sftp.put(local_path, remote_path)
sftp.close()
run(f"chmod 644 {remote_path}")

o, _, _ = run(f"ls -la {remote_path}")
print(f"placed: {o}", file=sys.stderr)

# Verify URL
url = f"{BASE_URL}/{fname}"
o, _, _ = run(f'curl -skI "{url}" | head -5')
print(f"verify:\n{o}", file=sys.stderr)

c.close()

if "200" in o.split("\n")[0]:
    print(json.dumps({"download_url": url, "filename": fname, "size_bytes": size}, ensure_ascii=False))
else:
    print(json.dumps({"error": f"verify={o.strip()}"}, ensure_ascii=False))
