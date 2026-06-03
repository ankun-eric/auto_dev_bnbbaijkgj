"""SCP-like helper using paramiko."""
import sys, os, paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"

def upload(local, remote):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = cli.open_sftp()
    print(f"Uploading {local} -> {remote} ({os.path.getsize(local)} bytes)")
    sftp.put(local, remote)
    sftp.close()
    cli.close()
    print("Done")


if __name__ == "__main__":
    upload(sys.argv[1], sys.argv[2])
