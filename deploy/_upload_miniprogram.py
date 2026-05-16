"""
上传小程序 zip 到服务器
"""
import paramiko
import sys
import os
import urllib.request, ssl

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD  = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
ZIP_NAME = sys.argv[1]
SERVER_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"

def main():
    if not os.path.isfile(ZIP_NAME):
        print(f"File not found: {ZIP_NAME}")
        sys.exit(1)

    # 确保目录存在
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PWD, allow_agent=False, look_for_keys=False)
    i, o, e = cli.exec_command(f"mkdir -p {SERVER_DIR} && ls -la {SERVER_DIR}/ 2>&1 | head -5")
    out = o.read().decode('utf-8', 'replace')
    print(out)
    cli.close()

    t = paramiko.Transport((HOST, PORT))
    t.connect(username=USER, password=PWD)
    sftp = paramiko.SFTPClient.from_transport(t)
    try:
        remote_path = f"{SERVER_DIR}/{ZIP_NAME}"
        print(f"Uploading {ZIP_NAME} ({os.path.getsize(ZIP_NAME)} bytes) -> {remote_path}")
        sftp.put(ZIP_NAME, remote_path)
        sftp.chmod(remote_path, 0o644)
        print(f"Uploaded. Server-side size: {sftp.stat(remote_path).st_size}")
    finally:
        sftp.close()
        t.close()

    url = f"{BASE_URL}/miniprogram/{ZIP_NAME}"
    print(f"\nVerifying: {url}")
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            print(f"HTTP {r.status}  Content-Length: {r.headers.get('Content-Length')}")
            if r.status == 200:
                print(f"DOWNLOAD_URL={url}")
                return
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
