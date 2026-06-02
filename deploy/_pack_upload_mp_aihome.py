"""上传小程序 AI 首页分享包到 gateway-nginx 容器下载目录。"""
import os
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    zip_name = sys.argv[1]
    local_path = os.path.join(ROOT, zip_name)
    if not os.path.isfile(local_path):
        print("LOCAL FILE NOT FOUND:", local_path)
        sys.exit(1)
    size = os.path.getsize(local_path)
    print("LOCAL", local_path, size, "bytes")

    remote_dir = "/home/ubuntu/%s" % DEPLOY_ID
    remote_tmp = "%s/%s" % (remote_dir, zip_name)

    # 1) SFTP upload
    t = paramiko.Transport((HOST, PORT))
    t.connect(username=USER, password=PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(t)
    try:
        try:
            sftp.stat(remote_dir)
        except IOError:
            sftp.mkdir(remote_dir)
        sftp.put(local_path, remote_tmp)
        st = sftp.stat(remote_tmp)
        print("UPLOADED", remote_tmp, st.st_size, "bytes")
    finally:
        sftp.close()
        t.close()

    # 2) docker cp into gateway-nginx
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    try:
        cmd = "docker cp %s gateway-nginx:/data/static/apk/%s && docker exec gateway-nginx ls -l /data/static/apk/%s" % (
            remote_tmp, zip_name, zip_name)
        stdin, stdout, stderr = c.exec_command(cmd, timeout=120)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        print("DOCKER CP EXIT", code)
        print(out)
        if err:
            print("STDERR:", err)
        # cleanup temp
        c.exec_command("rm -f %s" % remote_tmp)
    finally:
        c.close()


if __name__ == "__main__":
    main()
