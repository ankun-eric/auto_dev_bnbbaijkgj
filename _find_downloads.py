import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
def run(cli,cmd,t=60):
    i,o,e=cli.exec_command(cmd,timeout=t)
    return o.read().decode('utf-8','ignore'), e.read().decode('utf-8','ignore')
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,username=USER,password=PWD,timeout=30)
for c in [
  "docker exec gateway-nginx sh -c 'ls -la /usr/share/nginx/html/ 2>/dev/null | head; echo ---; ls /usr/share/nginx/html/autodev/'+DID+'/downloads 2>/dev/null | tail -5'",
  "docker inspect gateway-nginx --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'",
  "grep -rn 'downloads' /home/"+USER+"/gateway* 2>/dev/null | head; docker exec gateway-nginx sh -c \"grep -rn 'downloads' /etc/nginx/ 2>/dev/null | head\"",
]:
    print("###",c); o,e=run(cli,c); print(o); 
    if e.strip(): print("ERR",e)
    print("="*50)
cli.close()
