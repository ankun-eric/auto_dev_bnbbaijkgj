import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Bangbang987", timeout=30)

deploy_id = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

cmds = [
    f"cat /home/ubuntu/gateway/conf.d/{deploy_id}.conf",
    f"ls /home/ubuntu/{deploy_id}/",
]
for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"STDERR: {err}")

ssh.close()
