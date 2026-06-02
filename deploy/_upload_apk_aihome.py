"""上传 AI 首页优化 APK 到服务器并放入 gateway-nginx 静态下载目录。"""
import os
import sys
import paramiko

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sshlib import HOST, PORT, USER, PASSWORD, DEPLOY_ID, run  # noqa: E402

APK_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apk_dl",
                         "app_aihome_20260602-095121_387c.apk")
APK_NAME = os.path.basename(APK_LOCAL)
REMOTE_HOME_DIR = f"/home/ubuntu/{DEPLOY_ID}"
REMOTE_HOME_PATH = f"{REMOTE_HOME_DIR}/{APK_NAME}"
GW_CONTAINER = "gateway-nginx"
GW_TARGET = f"/data/static/apk/{APK_NAME}"


def main():
    size = os.path.getsize(APK_LOCAL)
    print(f"Local APK: {APK_LOCAL} ({size} bytes)")

    # ensure remote dir
    code, out, err = run(f"mkdir -p {REMOTE_HOME_DIR}")
    print("mkdir:", code, out, err)

    # SFTP upload
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=60)
    try:
        sftp = c.open_sftp()
        print(f"Uploading to {REMOTE_HOME_PATH} ...")
        sftp.put(APK_LOCAL, REMOTE_HOME_PATH)
        st = sftp.stat(REMOTE_HOME_PATH)
        print(f"Uploaded remote size: {st.st_size}")
        sftp.close()
        assert st.st_size == size, "size mismatch after upload"
    finally:
        c.close()

    # ensure apk dir inside container
    code, out, err = run(f"docker exec {GW_CONTAINER} mkdir -p /data/static/apk")
    print("container mkdir:", code, out, err)

    # docker cp into gateway-nginx
    code, out, err = run(
        f"docker cp {REMOTE_HOME_PATH} {GW_CONTAINER}:{GW_TARGET}", timeout=300)
    print("docker cp:", code, out, err)
    if code != 0:
        sys.exit(f"docker cp failed: {err}")

    # verify inside container
    code, out, err = run(f"docker exec {GW_CONTAINER} ls -l {GW_TARGET}")
    print("container ls:", code, out, err)

    print("UPLOAD_DONE")
    print("APK_NAME=" + APK_NAME)


if __name__ == "__main__":
    main()
