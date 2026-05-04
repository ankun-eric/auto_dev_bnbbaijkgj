#!/usr/bin/env python3
"""Upload APK to h5-web/public/apk/ static dir."""
import os, sys, paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

APK_NAME = "bini_health_coupon_mall_20260504_130854_91a5.apk"
LOCAL_APK = rf"C:\auto_output\bnbbaijkgj\apk_download\{APK_NAME}"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/h5-web/public/apk"
REMOTE_PATH = f"{REMOTE_DIR}/{APK_NAME}"
TMP_PATH = f"/tmp/{APK_NAME}"


def main():
    if not os.path.isfile(LOCAL_APK):
        print(f"ERROR: missing {LOCAL_APK}")
        sys.exit(2)
    size = os.path.getsize(LOCAL_APK)
    print(f"Local: {LOCAL_APK} ({size} bytes, {size/1024/1024:.2f} MB)")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=60, banner_timeout=60)

    sftp = client.open_sftp()
    print(f"\n[1/3] SFTP put -> {TMP_PATH}")
    sftp.put(LOCAL_APK, TMP_PATH)
    st = sftp.stat(TMP_PATH)
    print(f"      uploaded {st.st_size} bytes")
    sftp.close()

    cmd = (
        f"echo '{PASS}' | sudo -S mkdir -p {REMOTE_DIR} && "
        f"echo '{PASS}' | sudo -S mv {TMP_PATH} {REMOTE_PATH} && "
        f"echo '{PASS}' | sudo -S chmod 644 {REMOTE_PATH} && "
        f"ls -la {REMOTE_PATH}"
    )
    print(f"\n[2/3] mv -> {REMOTE_PATH}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    print(f"exit={rc}")

    if rc != 0:
        client.close()
        sys.exit(1)

    print(f"\n[3/3] Verify HTTP")
    url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/apk/{APK_NAME}"
    cmd2 = f"curl -s -o /dev/null -w '%{{http_code}} %{{size_download}}' -I '{url}'"
    stdin, stdout, stderr = client.exec_command(cmd2, timeout=60)
    print("HTTP_CODE_SIZE:", stdout.read().decode().strip())

    client.close()
    print("\nDONE")


if __name__ == "__main__":
    main()
