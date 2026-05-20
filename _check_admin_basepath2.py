import paramiko
HOST="newbb.test.bangbangvip.com";USER="ubuntu";PWD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
def sh(cli,cmd,t=60):
    si,so,se=cli.exec_command(cmd,timeout=t)
    return so.read().decode(errors='replace'),se.read().decode(errors='replace'),so.channel.recv_exit_status()
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,username=USER,password=PWD,timeout=60)
try:
    o,_,_=sh(cli,f"docker exec {DEPLOY_ID}-admin sh -c 'cat /app/next.config.js 2>/dev/null; cat /app/next.config.mjs 2>/dev/null; cat /app/next.config.ts 2>/dev/null'")
    print("--- next.config ---");print(o)
    o,_,_=sh(cli,f"docker exec {DEPLOY_ID}-admin sh -c 'ls /app/src/app/'")
    print("--- src/app ---");print(o)
    o,_,_=sh(cli,f"docker exec {DEPLOY_ID}-admin sh -c 'ls \"/app/src/app/(admin)/system\"'")
    print("--- (admin)/system ---");print(o)
    o,_,_=sh(cli,f"docker exec {DEPLOY_ID}-admin sh -c 'ls \"/app/src/app/(admin)\"'")
    print("--- (admin) dir ---");print(o)
finally:cli.close()
