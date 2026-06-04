"""Upload APK to gateway-nginx and verify download URL."""
import os
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

LOCAL_APK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_apk_dl", "app_health_plan_20260603_022916_9e0d.apk")
APK_NAME = os.path.basename(LOCAL_APK)


def main():
    assert os.path.exists(LOCAL_APK), f"missing: {LOCAL_APK}"
    size_mb = os.path.getsize(LOCAL_APK) / 1024 / 1024
    print(f"[0] Local APK: {LOCAL_APK} ({size_mb:.2f} MB)")

    print(f"[1/3] SFTP upload -> {HOST}:/home/ubuntu/{DID}/{APK_NAME}")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)

    def sh(cmd, t=120):
        _, so, se = c.exec_command(cmd, timeout=t)
        out = so.read().decode("utf-8", "ignore")
        err = se.read().decode("utf-8", "ignore")
        if out:
            print(out.rstrip()[-800:])
        if err:
            print("ERR:", err.rstrip()[-300:])
        return out, err

    sh(f"mkdir -p /home/ubuntu/{DID}")

    sftp = c.open_sftp()
    remote_tmp = f"/home/ubuntu/{DID}/{APK_NAME}"
    sftp.put(LOCAL_APK, remote_tmp)
    sftp.close()
    print(f"  + uploaded to {remote_tmp}")

    print(f"[2/3] docker cp -> gateway-nginx:/data/static/apk/{APK_NAME}")
    sh(f"docker cp {remote_tmp} gateway-nginx:/data/static/apk/{APK_NAME}")
    sh(f"docker exec gateway-nginx ls -la /data/static/apk/{APK_NAME}")

    print("[3/3] Verify download URL")
    download_url = f"https://newbb.test.bangbangvip.com/autodev/{DID}/downloads/{APK_NAME}"
    out, _ = sh(f"curl -sk -o /dev/null -w 'http=%{{http_code}} size=%{{size_download}}\\n' -I {download_url}")
    c.close()
    print(f"\n[DONE] Download URL: {download_url}")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_apk_download_url.txt"), "w") as f:
        f.write(download_url)


if __name__ == "__main__":
    main()
