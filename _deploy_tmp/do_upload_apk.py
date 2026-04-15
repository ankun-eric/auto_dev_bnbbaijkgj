import paramiko
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
APK_LOCAL = r"C:\auto_output\bnbbaijkgj\_deploy_tmp\apk_download\app_20260415_003629_8c83.apk"
APK_NAME = "app_20260415_003629_8c83.apk"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/static"
REMOTE_PATH = f"{REMOTE_DIR}/{APK_NAME}"

local_size = os.path.getsize(APK_LOCAL)
print(f"Local APK size: {local_size} bytes ({local_size/1024/1024:.1f} MB)")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=30)

sftp = ssh.open_sftp()
print(f"Uploading {APK_NAME} to {REMOTE_PATH}...")

sftp.put(APK_LOCAL, REMOTE_PATH, callback=lambda transferred, total: print(f"\r  Progress: {transferred/1024/1024:.1f}/{total/1024/1024:.1f} MB", end="", flush=True) if transferred % (10*1024*1024) < 1024*1024 else None)

print(f"\nUpload complete!")

remote_stat = sftp.stat(REMOTE_PATH)
print(f"Remote file size: {remote_stat.st_size} bytes")

if remote_stat.st_size == local_size:
    print("Size verification: OK")
else:
    print(f"Size mismatch! Local: {local_size}, Remote: {remote_stat.st_size}")

sftp.close()
ssh.close()
print("Done!")
