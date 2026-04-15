import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

gateway_conf = open(r"C:\auto_output\bnbbaijkgj\gateway-routes.conf", "r").read()

sftp = ssh.open_sftp()
host_conf_path = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
print(f"Writing config to {host_conf_path} ...")
with sftp.open(host_conf_path, "w") as f:
    f.write(gateway_conf)
sftp.close()
print("Config written!")

print("\nTesting nginx config...")
stdin, stdout, stderr = ssh.exec_command("docker exec gateway nginx -t 2>&1", timeout=30)
out = stdout.read().decode("utf-8", errors="replace")
ec = stdout.channel.recv_exit_status()
print(out.strip())
print(f"Exit: {ec}")

if ec == 0 or "successful" in out.lower():
    print("\nReloading nginx...")
    stdin, stdout, stderr = ssh.exec_command("docker exec gateway nginx -s reload 2>&1", timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    ec = stdout.channel.recv_exit_status()
    print(out.strip())
    print(f"Nginx reload exit: {ec}")
else:
    print("ERROR: nginx test failed, not reloading!")

ssh.close()
print("\nDone!")
