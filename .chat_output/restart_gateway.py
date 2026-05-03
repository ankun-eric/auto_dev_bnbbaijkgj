import paramiko, json, os, sys
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"

zips = sorted([f for f in os.listdir(PROJECT_ROOT) if f.startswith("miniprogram_book_after_pay_") and f.endswith(".zip")])
fname = zips[-1]
size = os.path.getsize(os.path.join(PROJECT_ROOT, fname))

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PWD,timeout=30,allow_agent=False,look_for_keys=False)
def run(cmd):
    si,so,se=c.exec_command(cmd, timeout=60)
    return so.read().decode(errors='replace')+se.read().decode(errors='replace')

# Confirm file is on host
print(run(f"ls -la /home/ubuntu/{DEPLOY_ID}/static/downloads/"))

# Restart gateway container to refresh bind mount
print("=== restart gateway ===")
print(run(f"echo '{PWD}' | sudo -S docker restart gateway 2>&1"))

# wait briefly
import time; time.sleep(3)

print(run("docker exec gateway ls -la /data/static/ /data/static/downloads/ 2>&1 | head"))

# verify
url = f"{BASE_URL}/{fname}"
o = run(f'curl -skI "{url}" | head -5')
print("verify:\n" + o)

c.close()

if "200" in o.split("\n")[0]:
    print(json.dumps({"download_url": url, "filename": fname, "size_bytes": size}, ensure_ascii=False))
else:
    print(json.dumps({"error": f"verify={o.strip()}"}, ensure_ascii=False))
