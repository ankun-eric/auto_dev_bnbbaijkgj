import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

deploy_id = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

cmds = [
    f"docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null",
    f"docker exec gateway-nginx cat /etc/nginx/conf.d/autodev-{deploy_id}.conf 2>/dev/null",
    f"docker inspect gateway-nginx --format '{{{{.Mounts}}}}' 2>/dev/null",
    f"docker inspect gateway-nginx --format '{{{{json .Mounts}}}}' 2>/dev/null",
]
for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"STDERR: {err}")

ssh.close()
