"""上传本次 bug 修复涉及的文件到服务器项目目录。"""
import os
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PORT = 22

LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"
REMOTE_ROOT = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

FILES = [
    "h5-web/src/lib/api.ts",
    "h5-web/src/app/merchant/layout.tsx",
    "h5-web/src/app/merchant/m/login/page.tsx",
    "admin-web/src/lib/api.ts",
]


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()
    try:
        for rel in FILES:
            local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
            remote = REMOTE_ROOT + "/" + rel
            size = os.path.getsize(local)
            print(f"uploading {rel} ({size} bytes)")
            sftp.put(local, remote)
            stat = sftp.stat(remote)
            print(f"  done remote size={stat.st_size}")
    finally:
        sftp.close()
        client.close()
    print("ALL OK")


if __name__ == "__main__":
    main()
