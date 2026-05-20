import paramiko, time
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=60)
def sh(c,t=120):
    si,so,se=cli.exec_command(c,timeout=t)
    return so.read().decode(errors='replace'),so.channel.recv_exit_status()

# 触发编译（next dev 是按需编译的）
for i in range(3):
    o,_=sh(f"curl -s -L -o /dev/null -w '%{{http_code}}|t=%{{time_total}}' --max-time 60 '{BASE}/admin/system/seed-import/'")
    print(f"try {i+1}: {o.strip()}")
    time.sleep(2)
o,_=sh(f"curl -s -L --max-time 60 '{BASE}/admin/system/seed-import/' | head -c 500")
print("\n--- response head ---");print(o)
# admin 容器日志
o,_=sh(f"docker logs --tail 50 {DEPLOY_ID}-admin 2>&1 | tail -40")
print("--- admin recent logs ---");print(o)
cli.close()
