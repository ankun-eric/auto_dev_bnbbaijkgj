import paramiko

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
P=f"/home/{USER}/{DID}"

def run(cli,cmd,t=120):
    i,o,e=cli.exec_command(cmd,timeout=t)
    return o.read().decode('utf-8','ignore'), e.read().decode('utf-8','ignore')

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,username=USER,password=PWD,timeout=30)
for c in [
  f"ls {P}/docker-compose*.yml",
  f"grep -n 'h5' {P}/docker-compose.prod.yml | head -20",
  f"sed -n '80,170p' {P}/docker-compose.prod.yml",
  f"cd {P} && git remote -v && git log -1 --oneline",
  "docker network ls | grep "+DID,
]:
    print("### ",c)
    o,e=run(cli,c); print(o)
    if e.strip(): print("ERR",e)
    print("="*50)
cli.close()
