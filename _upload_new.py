#!/usr/bin/env python3
"""Upload renamed APK to server static/apk and verify URL."""
import os
import sys
import urllib.request
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

LOCAL_APK = r"C:\auto_output\bnbbaijkgj\apk_download\bini_health_android-datemode-v20260504-105800-cd58.apk"
APK_NAME = "bini_health_datemode_20260504_105800_cd58.apk"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk"
REMOTE_PATH = f"{REMOTE_DIR}/{APK_NAME}"
URL = f"https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/{APK_NAME}"


def main():
    if not os.path.isfile(LOCAL_APK):
        print(f"ERROR missing local: {LOCAL_APK}")
        sys.exit(2)
    size = os.path.getsize(LOCAL_APK)
    print(f"Local: {LOCAL_APK} ({size} bytes)")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60, banner_timeout=60)

    sftp = c.open_sftp()
    print(f"\n[1/3] SFTP -> {REMOTE_PATH}")
    sftp.put(LOCAL_APK, REMOTE_PATH)
    st = sftp.stat(REMOTE_PATH)
    print(f"      uploaded {st.st_size} bytes")
    sftp.close()

    cmd = f"chmod 644 {REMOTE_PATH} && ls -la {REMOTE_PATH}"
    print(f"\n[2/3] $ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=30)
    rc = o.channel.recv_exit_status()
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err:
        print("ERR:", err)
    c.close()

    print(f"\n[3/3] HTTP HEAD {URL}")
    req = urllib.request.Request(URL, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            clen = resp.headers.get("Content-Length", "?")
            print(f"  HTTP {code}  Content-Length={clen}")
            sys.exit(0 if code == 200 else 1)
    except urllib.error.HTTPError as he:
        print(f"  HTTP {he.code} {he.reason}")
        sys.exit(1)
    except Exception as ex:
        print(f"  ERROR {ex}")
        sys.exit(1)


if __name__ == "__main__":
    main()
