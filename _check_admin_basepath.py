import paramiko
HOST="newbb.test.bangbangvip.com";USER="ubuntu";PWD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
def sh(cli,cmd,t=60):
    si,so,se=cli.exec_command(cmd,timeout=t)
    return so.read().decode(errors='replace'),se.read().decode(errors='replace'),so.channel.recv_exit_status()
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,username=USER,password=PWD,timeout=60)
try:
    o,_,_=sh(cli,f"docker exec {DEPLOY_ID}-admin cat /app/next.config.js 2>/dev/null || docker exec {DEPLOY_ID}-admin cat /app/next.config.mjs 2>/dev/null")
    print("--- next.config ---");print(o[:2000])
    o,_,_=sh(cli,f"docker exec {DEPLOY_ID}-admin sh -c 'curl -sv http://127.0.0.1:3000/ 2>&1 | head -30'")
    print("--- curl admin / ---");print(o[:1500])
    # 尝试不带 /admin
    o,_,_=sh(cli,f"docker exec {DEPLOY_ID}-admin sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\" http://127.0.0.1:3000/system/seed-import'")
    print("admin 内 /system/seed-import (no /admin):",o.strip())
    o,_,_=sh(cli,f"docker exec {DEPLOY_ID}-admin sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\" http://127.0.0.1:3000/questionnaire-templates'")
    print("admin 内 /questionnaire-templates:",o.strip())
    # gateway nginx 配置
    o,_,_=sh(cli,f"docker ps --filter name=gateway -q | head -1")
    gw=o.strip()
    if gw:
        o,_,_=sh(cli,f"docker exec {gw} sh -c 'cat /etc/nginx/conf.d/*.conf 2>/dev/null | grep -A2 -B1 \"{DEPLOY_ID}\" | head -80'")
        print("--- gateway nginx for our deploy ---");print(o[:3000])
finally:cli.close()
