import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASSWORD="Newbang888"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PASSWORD,timeout=30)
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
cmds=[
 "docker exec gateway ls /etc/nginx/conf.d/ 2>&1 | head -30",
 f"docker exec gateway ls /etc/nginx/conf.d/{DID}.conf 2>&1; echo ---; docker exec gateway cat /etc/nginx/conf.d/{DID}.conf 2>&1 | head -120",
 f"ls /etc/nginx/conf.d/{DID}.conf 2>&1; echo ---; cat /etc/nginx/conf.d/{DID}.conf 2>&1 | head -120",
 "ls /etc/nginx/conf.d/gateway-routes/ 2>&1 | head -30",
 f"cat /etc/nginx/conf.d/gateway-routes/{DID}.conf 2>&1 | head -120",
 "ls /etc/nginx/conf.d/routes/ 2>&1 | head -30",
 f"cat /etc/nginx/conf.d/routes/{DID}.conf 2>&1 | head -120",
 # check what curl sees with full URL
 f"curl -skI https://newbb.test.bangbangvip.com/autodev/{DID}/app_pointsskin_20260514_180959_434b.apk 2>&1 | head -20",
 f"curl -sk -o /dev/null -w 'STATUS=%{{http_code}}\\nSIZE=%{{size_download}}\\n' https://newbb.test.bangbangvip.com/autodev/{DID}/app_pointsskin_20260514_180959_434b.apk -r 0-0",
 f"curl -sI -o /dev/null -w 'STATUS=%{{http_code}}\\n' http://localhost/autodev/{DID}/app_paymentconfig_20260503_231130_e313.apk",
]
for c in cmds:
    print(f"\n$ {c}")
    stdin,stdout,stderr=ssh.exec_command(c,timeout=30)
    out=stdout.read().decode('utf-8',errors='replace'); err=stderr.read().decode('utf-8',errors='replace')
    if out: print(out)
    if err: print("STDERR:",err)
ssh.close()
