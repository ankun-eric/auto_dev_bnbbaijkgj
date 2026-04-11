import paramiko
import sys
import os

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Bangbang987"
REMOTE_BASE = "/home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
LOCAL_BASE = r"C:\auto_output\bnbbaijkgj"

def upload_file(local_rel_path):
    local_path = os.path.join(LOCAL_BASE, local_rel_path.replace("/", os.sep))
    remote_path = f"{REMOTE_BASE}/{local_rel_path}"
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()
    
    sftp.put(local_path, remote_path)
    print(f"Uploaded: {local_rel_path}")
    
    sftp.close()
    ssh.close()

if __name__ == "__main__":
    for f in sys.argv[1:]:
        upload_file(f)
