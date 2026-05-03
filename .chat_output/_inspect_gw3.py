import paramiko
HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
def run(cmd):
    print(f"$ {cmd}")
    _, o, e = cli.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", "ignore"))
    er = e.read().decode("utf-8", "ignore")
    if er.strip(): print("STDERR:", er[:500])
run(f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}.conf")
print("\n========= APK ROUTE FILE =========")
run(f"docker exec gateway cat /etc/nginx/conf.d/gateway-routes/{DEPLOY_ID}-apk.conf")
print("\n========= STATIC DIR ON HOST =========")
run(f"ls -la /home/ubuntu/{DEPLOY_ID}/static/ | head -20")
cli.close()
