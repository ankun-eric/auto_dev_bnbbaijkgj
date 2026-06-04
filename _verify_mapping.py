import paramiko

HOST="newbb.test.bangbangvip.com"; PORT=22; USER="ubuntu"; PWD="Newbang888"

def run(cli,cmd,timeout=60):
    i,o,e=cli.exec_command(cmd,timeout=timeout)
    return o.read().decode("utf-8","ignore"), e.read().decode("utf-8","ignore")

cli=paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,PORT,USER,PWD,timeout=30)

# Which container has /data/static/apk and matches the host miniprogram dir?
# Check the apk dir inode count inside gateway vs host miniprogram dir
out,_=run(cli,"docker exec gateway-nginx ls /data/static/apk/")
print("### gateway /data/static/apk"); print(out)

out,_=run(cli,"ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram/")
print("### host static/miniprogram"); print(out)

# find which container binds that host path
out,_=run(cli,"for c in $(docker ps --format '{{.Names}}'); do docker inspect $c --format '{{.Name}} {{json .Mounts}}' | grep -l static >/dev/null 2>&1; docker inspect $c --format '{{.Name}}: {{range .Mounts}}{{.Source}}->{{.Destination}} {{end}}' | grep -i 'static' ; done; echo DONE")
print("### containers mounting static"); print(out)

cli.close()
