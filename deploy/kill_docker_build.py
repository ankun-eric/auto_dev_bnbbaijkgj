import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)
_, o, _ = c.exec_command(
    "docker ps --filter ancestor=flutter-builder:latest -q | xargs -r docker kill 2>&1; "
    "pkill -f flutter_build_v3.sh 2>&1; "
    "echo done; "
    "docker ps --filter ancestor=flutter-builder:latest"
)
print(o.read().decode())
c.close()
