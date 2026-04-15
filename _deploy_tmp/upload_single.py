import paramiko
import sys

host = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]
local_file = sys.argv[4]
remote_file = sys.argv[5]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, password=password, timeout=30)
sftp = client.open_sftp()
sftp.put(local_file, remote_file)
sftp.close()
client.close()
print(f"Uploaded {local_file} -> {remote_file}")
