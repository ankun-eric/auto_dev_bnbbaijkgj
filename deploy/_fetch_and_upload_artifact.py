"""
从 GitHub Release 下载产物并上传到部署服务器的对应静态目录
"""
import sys
import os
import subprocess
import urllib.request, ssl
import paramiko
from datetime import datetime

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD  = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

# 用法: python _fetch_and_upload_artifact.py <tag> <asset_name> <local_target_name> <category>
#   category: apk | ipa | miniprogram | downloads
TAG = sys.argv[1]
ASSET = sys.argv[2]
TARGET = sys.argv[3]   # 上传到服务器后的文件名
CATEGORY = sys.argv[4] # apk / ipa / miniprogram / downloads

SERVER_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/{CATEGORY}"

def main():
    # 下载产物
    local = TARGET
    print(f"Downloading release {TAG} / {ASSET} -> {local}")
    subprocess.run(["gh","release","download",TAG,"-p",ASSET,"-O",local,"--clobber"], check=True)
    size = os.path.getsize(local)
    print(f"Downloaded {size} bytes")

    # 确保目录存在
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PWD, allow_agent=False, look_for_keys=False)
    i, o, e = c.exec_command(f"mkdir -p {SERVER_DIR} && echo OK")
    print(o.read().decode('utf-8'))
    c.close()

    # SFTP 上传
    t = paramiko.Transport((HOST, PORT))
    t.connect(username=USER, password=PWD)
    sftp = paramiko.SFTPClient.from_transport(t)
    try:
        remote = f"{SERVER_DIR}/{TARGET}"
        print(f"Uploading -> {remote}")
        sftp.put(local, remote)
        sftp.chmod(remote, 0o644)
        print(f"Server size: {sftp.stat(remote).st_size}")
    finally:
        sftp.close()
        t.close()

    url = f"{BASE_URL}/{CATEGORY}/{TARGET}"
    print(f"\nVerify: {url}")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, method='HEAD')
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            print(f"HTTP {r.status}  Content-Length: {r.headers.get('Content-Length')}")
            if r.status == 200:
                print(f"DOWNLOAD_URL={url}")
    except Exception as e:
        print(f"Verify FAIL: {e}")
        sys.exit(2)

    # 删除本地文件
    try:
        os.remove(local)
    except Exception:
        pass

if __name__ == "__main__":
    main()
