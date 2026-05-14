import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASSWORD="Newbang888"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PASSWORD,timeout=30)
cmds=[
 "cat /etc/nginx/conf.d/gateway-routes/6b099ed3-7175-4a78-91f4-44570c84ed27-apk.conf",
 "docker exec gateway ls /etc/nginx/conf.d/gateway-routes/ 2>&1 | head -20",
 "docker exec gateway cat /etc/nginx/conf.d/gateway-routes/6b099ed3-7175-4a78-91f4-44570c84ed27-apk.conf 2>&1",
 "docker exec gateway grep -r 'include.*gateway-routes' /etc/nginx/ 2>&1 | head -10",
 "docker exec gateway cat /etc/nginx/nginx.conf 2>&1 | head -80",
 # is the apk being served via the main conf? Check directapk in the older bak
 "docker exec gateway cat /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf.bak.directapk.1777815377 2>&1 | head -80",
 # check existing payment apk URL alternate paths
 "curl -sk -o /dev/null -w 'STATUS=%{http_code}\\n' https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/app_paymentconfig_20260503_231130_e313.apk -r 0-0",
 "docker inspect gateway --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'",
]
for c in cmds:
    print(f"\n$ {c}")
    stdin,stdout,stderr=ssh.exec_command(c,timeout=30)
    out=stdout.read().decode('utf-8',errors='replace'); err=stderr.read().decode('utf-8',errors='replace')
    if out: print(out)
    if err: print("STDERR:",err)
ssh.close()
