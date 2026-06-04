"""GitHub 从服务器不可达，降级：直接 SFTP 上传本次改动的两个 H5 源文件到服务器。"""
import sys, paramiko
sys.path.insert(0, "deploy")
from _sshlib import HOST, PORT, USER, PASSWORD, DEPLOY_ID

PROJ = f"/home/ubuntu/{DEPLOY_ID}"
FILES = [
    "h5-web/src/app/health-profile/page.tsx",
    "h5-web/src/app/health-profile/archive-list/page.tsx",
]

t = paramiko.Transport((HOST, PORT))
t.connect(username=USER, password=PASSWORD)
sftp = paramiko.SFTPClient.from_transport(t)
for rel in FILES:
    local = rel.replace("/", "\\")
    remote = f"{PROJ}/{rel}"
    sftp.put(local, remote)
    print("uploaded:", remote)
sftp.close()
t.close()
print("DONE")
