import paramiko, time

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
P=f"/home/{USER}/{DID}"

def run(cli,cmd,t=300):
    i,o,e=cli.exec_command(cmd,timeout=t)
    out=o.read().decode('utf-8','ignore'); err=e.read().decode('utf-8','ignore')
    code=o.channel.recv_exit_status()
    return code,out,err

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,username=USER,password=PWD,timeout=30)

# 确认两个 build 日志都已 DONE / 杀掉任何残留 build（镜像已 Built）
code,out,err=run(cli, "pgrep -af 'compose.*build' || echo NO_BUILD")
print("[build procs]", out.strip())

code,out,err=run(cli, f"cd {P} && docker compose -f docker-compose.prod.yml up -d --force-recreate h5-web 2>&1", t=300)
print("[up]",code,out,err)

time.sleep(6)
code,out,err=run(cli, "docker ps --format '{{.Names}} {{.Status}}' | grep "+DID)
print("[ps]\n",out)

# gateway 连网络 + reload
code,out,err=run(cli, f"docker network connect {DID}-network gateway-nginx 2>&1 | head -2; docker exec gateway-nginx nginx -t 2>&1 | tail -2; docker exec gateway-nginx nginx -s reload 2>&1; echo RELOAD_DONE")
print("[gateway]\n",out,err)
cli.close()
print("UP_DONE")
