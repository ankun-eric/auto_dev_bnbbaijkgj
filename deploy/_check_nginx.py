import paramiko
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=30)

cmds = [
    "docker ps --format '{{.Names}}' | grep -i nginx",
    "ls /home/ubuntu/gateway-nginx/ 2>&1 || ls /home/ubuntu/ | grep -i nginx",
    "find /home/ubuntu -maxdepth 3 -name 'gateway*' 2>/dev/null",
    "docker ps --format '{{.Names}}'",
]
for c in cmds:
    print(f"\n>>> {c}")
    _, stdout, _ = cli.exec_command(c)
    print(stdout.read().decode('utf-8', errors='ignore'))
cli.close()
