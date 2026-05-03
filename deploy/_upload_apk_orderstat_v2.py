"""上传新构建的 APK 到服务器 static/apk/ 并验证可下载"""
import paramiko, os, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

LOCAL_APK = r"C:\auto_output\bnbbaijkgj\apk_download\bini_health_android-orderstat-fulfillment-v20260504-014202-3a07.apk"
REMOTE_NAME = "app_orderstat_fulfillment_20260504_014200_3a07.apk"
REMOTE_PATH = f"/home/ubuntu/{DEPLOY_ID}/static/apk/{REMOTE_NAME}"

assert os.path.isfile(LOCAL_APK), f"local apk not found: {LOCAL_APK}"
size_mb = os.path.getsize(LOCAL_APK) / 1024 / 1024
print(f"local apk size: {size_mb:.2f} MB")

t = paramiko.Transport((HOST, 22))
t.connect(username=USER, password=PWD)
sftp = paramiko.SFTPClient.from_transport(t)
print(f"uploading -> {REMOTE_PATH}")
sftp.put(LOCAL_APK, REMOTE_PATH)
attr = sftp.stat(REMOTE_PATH)
print(f"uploaded, remote size: {attr.st_size/1024/1024:.2f} MB")
sftp.close()
t.close()

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=30)
_, stdout, _ = cli.exec_command(f"ls -lh {REMOTE_PATH}")
print("remote ls:", stdout.read().decode())
_, stdout, _ = cli.exec_command(f"sha256sum {REMOTE_PATH} | cut -c1-16")
print("sha256 prefix:", stdout.read().decode().strip())
_, stdout, _ = cli.exec_command(
    f"strings {REMOTE_PATH} 2>/dev/null | grep -E '上门服务|到店服务|快递配送|到店核销|线上服务|其他服务' | head -10"
)
chinese = stdout.read().decode().strip()
print("Chinese strings inside APK:")
print(chinese if chinese else "  (none found in plain strings; encoded/compressed)")
cli.close()

print(f"\nDONE. Public URL: https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/apk/{REMOTE_NAME}")
