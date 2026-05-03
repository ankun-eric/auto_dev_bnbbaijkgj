import os, sys, json, paramiko

PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

# Find the zip just created
zips = sorted([f for f in os.listdir(PROJECT_ROOT) if f.startswith("miniprogram_book_after_pay_") and f.endswith(".zip")])
fname = zips[-1]
local_path = os.path.join(PROJECT_ROOT, fname)
size = os.path.getsize(local_path)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PWD, timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    o = stdout.read().decode("utf-8", errors="replace")
    e = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, o, e

# Target dir per nginx alias rule
target_dir = "/data/static/downloads"
rc, o, e = run(f"ls -ld {target_dir} 2>&1; ls {target_dir}/ | head -5")
print("target_dir info:\n" + o, file=sys.stderr)

# Upload via SFTP - needs sudo? Check writability
rc, o, e = run(f"test -w {target_dir} && echo WRITABLE || echo NO")
print(f"writable: {o}", file=sys.stderr)

remote_path = f"{target_dir}/{fname}"
upload_ok = False
if "WRITABLE" in o:
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    upload_ok = True
else:
    # Try sudo - upload to /tmp first, then sudo mv
    tmp_path = f"/tmp/{fname}"
    sftp = client.open_sftp()
    sftp.put(local_path, tmp_path)
    sftp.close()
    rc, o, e = run(f"echo '{PWD}' | sudo -S cp {tmp_path} {remote_path} && echo '{PWD}' | sudo -S chmod 644 {remote_path} && rm -f {tmp_path} && echo OK")
    print(f"sudo mv: {o} {e}", file=sys.stderr)
    if "OK" in o:
        upload_ok = True

if upload_ok:
    run(f"chmod 644 {remote_path} 2>/dev/null || true")

# Verify
url = f"{BASE_URL}/{fname}"
rc, o, e = run(f'curl -skI "{url}" | head -3')
print(f"verify:\n{o}", file=sys.stderr)

client.close()

if upload_ok and "200" in o.split("\n")[0]:
    print(json.dumps({"download_url": url, "filename": fname, "size_bytes": size}, ensure_ascii=False))
else:
    print(json.dumps({"error": f"upload_ok={upload_ok}, verify={o.strip()}"}, ensure_ascii=False))
