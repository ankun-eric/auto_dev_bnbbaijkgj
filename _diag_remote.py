import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASSWORD="Newbang888"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PASSWORD,timeout=30)
cmds=[
 "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 | head -40",
 "docker ps --format '{{.Names}}\t{{.Ports}}' | grep -i 6b099ed3 || echo 'no docker for this id'",
 "docker ps --format '{{.Names}}' | head -30",
 "ls /etc/nginx/conf.d/ 2>/dev/null || echo no_conf_d",
 "docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null || echo no_gateway_nginx",
 "docker exec gateway-nginx cat /etc/nginx/conf.d/autodev.conf 2>/dev/null | head -80 || true",
 "curl -sI -o /dev/null -w 'STATUS=%{http_code}\\n' http://localhost/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ 2>&1 || true",
]
for c in cmds:
    print(f"\n$ {c}")
    stdin,stdout,stderr=ssh.exec_command(c,timeout=30)
    out=stdout.read().decode('utf-8',errors='replace'); err=stderr.read().decode('utf-8',errors='replace')
    if out: print(out)
    if err: print("STDERR:",err)
ssh.close()
