import paramiko
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=30)

cmds = [
    f"cat /home/ubuntu/{DEPLOY_ID}/gateway-routes.conf",
    "ls /home/ubuntu/gateway/conf.d/gateway-routes/ | head -20",
    f"ls /home/ubuntu/gateway/conf.d/gateway-routes/ | grep '{DEPLOY_ID[:8]}'",
    f"cat /home/ubuntu/gateway/conf.d/gateway-routes/{DEPLOY_ID}.conf 2>/dev/null || echo NO_PROJECT_ROUTE",
]
for c in cmds:
    print(f"\n>>> {c}")
    _, stdout, _ = cli.exec_command(c)
    print(stdout.read().decode('utf-8', errors='ignore'))
cli.close()
