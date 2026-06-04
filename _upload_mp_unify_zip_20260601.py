"""上传 AI 首页统一版小程序 zip 到服务器 backend 容器 /app/uploads/ 并验证下载链接"""
import os
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(LOCAL_ROOT, "_mp_unify_zip_name.txt")) as f:
    ZIP = f.read().strip()

local_zip = os.path.join(LOCAL_ROOT, ZIP)
remote_tmp = f"/home/ubuntu/{DEPLOY_ID}/{ZIP}"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)


def run(cmd, timeout=300):
    _i, o, e = cli.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    return o.channel.recv_exit_status(), out, err


sftp = cli.open_sftp()
sftp.put(local_zip, remote_tmp)
sftp.close()
print(f"[sftp] uploaded -> {remote_tmp}")

c, o, e = run(f"docker cp {remote_tmp} {BACKEND}:/app/uploads/{ZIP}")
print(f"[docker cp] exit={c} {e.strip()[:200]}")
c, o, e = run(f"docker exec {BACKEND} ls -l /app/uploads/{ZIP}")
print("[verify in-container]", o.strip(), e.strip())
# 清理临时文件
run(f"rm -f {remote_tmp}")
cli.close()

print(f"\nDOWNLOAD_URL={BASE_URL}/uploads/{ZIP}")
