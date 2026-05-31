"""上传 APK 到 gateway-nginx /data/static/apk/"""
import paramiko
from pathlib import Path

HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PWD = "Newbang888"
PID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PID}"
GW = "gateway-nginx"

fname = "app_invite_bugfix_20260531_234323_073d.apk"
local = Path(__file__).parent / fname

ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
def run(cmd, t=600):
    i, o, e = ssh.exec_command(cmd, timeout=t)
    return o.read().decode(), e.read().decode()

print(f"[1/3] 上传 {fname} ({local.stat().st_size/1024/1024:.1f} MB)")
remote_tmp = f"/tmp/{fname}"
sftp = ssh.open_sftp(); sftp.put(str(local), remote_tmp); sftp.close()

print("[2/3] 放入 gateway-nginx /data/static/apk/")
run(f"docker exec {GW} mkdir -p /data/static/apk")
o, e = run(f"docker cp {remote_tmp} {GW}:/data/static/apk/{fname}")
print(o, e)
run(f"rm -f {remote_tmp}")

print("[3/3] 验证下载")
url = f"{BASE_URL}/downloads/{fname}"
o, _ = run(f"curl -sIo /dev/null -w '%{{http_code}}' {url}")
print(f"HTTP={o.strip()}")
print(f"URL: {url}")
with open(Path(__file__).parent / "_apk_invite_bugfix_url.txt", "w") as f:
    f.write(url)
ssh.close()
