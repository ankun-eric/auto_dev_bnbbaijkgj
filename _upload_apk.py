#!/usr/bin/env python3
"""Upload APK to server: project dir + /data/static/apk/ (via tmp + sudo mv)."""
import sys
import os
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

LOCAL_APK = r"C:\auto_output\bnbbaijkgj\apk_download\bini_health_android-v20260504-023553-87ac.apk"
APK_NAME = "bini_health_android-v20260504-023553-87ac.apk"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_PATH = f"{PROJECT_DIR}/{APK_NAME}"
STATIC_APK_PATH = f"/data/static/apk/{APK_NAME}"
TMP_PATH = f"/tmp/{APK_NAME}"


def main():
    if not os.path.isfile(LOCAL_APK):
        print(f"ERROR: local file missing: {LOCAL_APK}")
        sys.exit(2)
    size = os.path.getsize(LOCAL_APK)
    print(f"Local file: {LOCAL_APK} ({size} bytes)")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=60, banner_timeout=60)

    sftp = client.open_sftp()

    print(f"\n[1/3] SFTP -> {PROJECT_PATH}")
    sftp.put(LOCAL_APK, PROJECT_PATH)
    st = sftp.stat(PROJECT_PATH)
    print(f"      uploaded {st.st_size} bytes")

    print(f"\n[2/3] SFTP -> {TMP_PATH} (then sudo mv)")
    sftp.put(LOCAL_APK, TMP_PATH)
    st = sftp.stat(TMP_PATH)
    print(f"      uploaded {st.st_size} bytes to /tmp")

    sftp.close()

    cmd = (
        f"echo '{PASS}' | sudo -S mv {TMP_PATH} {STATIC_APK_PATH} "
        f"&& echo '{PASS}' | sudo -S chmod 644 {STATIC_APK_PATH} "
        f"&& echo '{PASS}' | sudo -S chown root:root {STATIC_APK_PATH} "
        f"&& ls -la {STATIC_APK_PATH}"
    )
    print(f"\n[3/3] SUDO MV -> {STATIC_APK_PATH}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err:
        print("STDERR:", err)
    print(f"exit={rc}")

    client.close()
    sys.exit(0 if rc == 0 else 1)


if __name__ == "__main__":
    main()
