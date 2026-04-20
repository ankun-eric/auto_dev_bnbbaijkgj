"""
上传 tcm-optim-v1 APK 到远程服务器 static downloads 目录。
"""
import os
import sys
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

LOCAL_APK = os.path.join(os.path.dirname(__file__), "apk_dist", "bini_health_tcm-optim-v1.apk")
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}/gateway-nginx/static/apk"
REMOTE_FILE = f"{REMOTE_DIR}/bini_health_tcm-optim-v1.apk"
LATEST_LINK = f"{REMOTE_DIR}/bini_health.apk"


def run(ssh, cmd):
    print(f"  $ {cmd}")
    _, out, err = ssh.exec_command(cmd)
    o = out.read().decode("utf-8", errors="replace").strip()
    e = err.read().decode("utf-8", errors="replace").strip()
    if o:
        print(o)
    if e:
        print("[stderr]", e)
    return out.channel.recv_exit_status()


def main():
    if not os.path.exists(LOCAL_APK):
        print("[ERROR] APK 不存在:", LOCAL_APK)
        sys.exit(1)

    size = os.path.getsize(LOCAL_APK)
    print(f"[LOCAL] {LOCAL_APK}  size={size/1024/1024:.2f} MB")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, PORT, USER, PASS, timeout=30)
    print(f"[SSH ] connected to {HOST}")

    run(ssh, f"mkdir -p {REMOTE_DIR}")

    sftp = ssh.open_sftp()
    print(f"[SFTP] uploading -> {REMOTE_FILE}")
    t0 = time.time()
    sftp.put(LOCAL_APK, REMOTE_FILE)
    sftp.close()
    print(f"[SFTP] done in {time.time()-t0:.1f}s")

    run(ssh, f"ls -lh {REMOTE_FILE}")
    run(ssh, f"cp -f {REMOTE_FILE} {LATEST_LINK}")
    run(ssh, f"ls -lh {LATEST_LINK}")

    # 外部链接验证
    url = f"https://{HOST}/autodev/{DEPLOY_ID}/apk/bini_health_tcm-optim-v1.apk"
    url_latest = f"https://{HOST}/autodev/{DEPLOY_ID}/apk/bini_health.apk"
    for u in [url, url_latest]:
        run(ssh, f'curl -sI -o /dev/null -w "%{{http_code}}  %{{size_download}}  {u}\\n" "{u}"')

    ssh.close()
    print("\n[DONE] APK uploaded.")
    print("  - ", url)
    print("  - ", url_latest)


if __name__ == "__main__":
    main()
