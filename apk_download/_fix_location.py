import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888')

commands = [
    "mkdir -p /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk",
    "cp /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_20260428_010702_622e.apk /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/app_20260428_010702_622e.apk",
    "chmod 644 /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/app_20260428_010702_622e.apk",
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/",
]

for cmd in commands:
    print(f"\n=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    print(f"Exit: {exit_code}")

ssh.close()
print("\nDone - APK moved to correct static directory")
