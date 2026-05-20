"""快速拷贝单个文件并重启"""
import sys, paramiko, time
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888")
sftp = ssh.open_sftp()
UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
files = sys.argv[1:] or ["backend/app/api/products.py"]
for rel in files:
    remote = f"/home/ubuntu/{UUID}/{rel}"
    sftp.put(rel, remote)
    parts = rel.split("/", 1)
    in_container = f"/app/{parts[1]}"
    ssh.exec_command(f"docker cp '{remote}' '{UUID}-backend:{in_container}'")[1].read()
    print(f"copied {rel}")
ssh.exec_command(f"docker restart {UUID}-backend")[1].read()
time.sleep(8)
print("restarted")
ssh.close()
