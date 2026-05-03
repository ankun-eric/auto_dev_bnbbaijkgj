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

# Diagnose
o, e, rc = run(f"ls -ld /home/ubuntu/{DEPLOY_ID}/static 2>&1; echo '---'; ls -ld /home/ubuntu/{DEPLOY_ID}/static/downloads 2>&1; echo '---'; ls /home/ubuntu/{DEPLOY_ID}/static/ 2>&1 | head")
print("diag:\n" + o, file=sys.stderr)

host_dir = f"/home/ubuntu/{DEPLOY_ID}/static/downloads"

# create dirs (with sudo if needed)
o, e, rc = run(f"mkdir -p {host_dir} 2>&1 && ls -ld {host_dir}")
print("mkdir1: " + o + " | err: " + e, file=sys.stderr)

if "No such" in o or "Permission" in o or "Permission" in e or rc != 0 or "downloads" not in o:
    o, e, rc = run(f"echo '{PWD}' | sudo -S mkdir -p {host_dir} && echo '{PWD}' | sudo -S chown ubuntu:ubuntu /home/ubuntu/{DEPLOY_ID}/static {host_dir} && ls -ld {host_dir}")
    print("mkdir2(sudo): " + o + " | err: " + e, file=sys.stderr)

# Upload - retry path; if direct write fails, upload to /tmp then sudo cp
remote_path = f"{host_dir}/{fname}"
try:
    sftp = c.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    print("direct sftp ok", file=sys.stderr)
except Exception as ex:
    print(f"direct sftp failed: {ex}; trying /tmp + sudo cp", file=sys.stderr)
    tmp = f"/tmp/{fname}"
    sftp = c.open_sftp()
    sftp.put(local_path, tmp)
    sftp.close()
    o, e, rc = run(f"echo '{PWD}' | sudo -S cp {tmp} {remote_path} && echo '{PWD}' | sudo -S chmod 644 {remote_path} && rm -f {tmp} && echo OK")
    print(f"sudo cp: {o} {e}", file=sys.stderr)

run(f"chmod 644 {remote_path} 2>/dev/null || echo '{PWD}' | sudo -S chmod 644 {remote_path}")

o, _, _ = run(f"ls -la {remote_path}")
print(f"placed: {o}", file=sys.stderr)

url = f"{BASE_URL}/{fname}"
o, _, _ = run(f'curl -skI "{url}" | head -5')
print(f"verify:\n{o}", file=sys.stderr)

c.close()

if "200" in o.split("\n")[0]:
    print(json.dumps({"download_url": url, "filename": fname, "size_bytes": size}, ensure_ascii=False))
else:
    print(json.dumps({"error": f"verify={o.strip()}"}, ensure_ascii=False))
