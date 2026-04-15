import paramiko
import sys
import os

host = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]
local_tar = sys.argv[4]
remote_dir = sys.argv[5]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, password=password, timeout=30)

stdin, stdout, stderr = client.exec_command(f"mkdir -p {remote_dir}")
stdout.channel.recv_exit_status()

sftp = client.open_sftp()
remote_tar = remote_dir + '/deploy.tar'
file_size = os.path.getsize(local_tar)
print(f"Uploading {local_tar} ({file_size / 1024 / 1024:.1f} MB) to {remote_tar}...")

transferred = [0]
def progress(sent, total):
    pct = sent * 100 // total
    if pct % 10 == 0 and sent != transferred[0]:
        print(f"  {pct}% ({sent // 1024} KB / {total // 1024} KB)")
        transferred[0] = sent

sftp.put(local_tar, remote_tar, callback=progress)
sftp.close()
print("Upload complete!")

print("Extracting on server...")
stdin, stdout, stderr = client.exec_command(
    f"cd {remote_dir} && tar -xf deploy.tar && rm deploy.tar && echo 'Extract done'"
)
out = stdout.read().decode()
err = stderr.read().decode()
print(out)
if err:
    print("STDERR:", err)

print("Listing remote directory:")
stdin, stdout, stderr = client.exec_command(f"ls -la {remote_dir}")
print(stdout.read().decode())

client.close()
