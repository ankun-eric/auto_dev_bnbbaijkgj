import paramiko
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=60)
def sh(c,t=60):
    si,so,se=cli.exec_command(c,timeout=t)
    return so.read().decode(errors='replace'),se.read().decode(errors='replace')
try:
    o,_=sh(f"docker exec {DEPLOY_ID}-admin env | grep -E 'NEXT|BASE'")
    print("--- admin env ---");print(o)
    # 容器内直接访问
    o,_=sh(f"docker exec {DEPLOY_ID}-admin sh -c \"wget -q -O - http://127.0.0.1:3000/autodev/{DEPLOY_ID}/admin/system/seed-import 2>&1 | head -30\"")
    print("--- wget /autodev/.../admin/system/seed-import ---");print(o[:1000])
    o,_=sh(f"docker exec {DEPLOY_ID}-admin sh -c \"wget -q -O - http://127.0.0.1:3000/autodev/{DEPLOY_ID}/admin/questionnaire-templates 2>&1 | head -3\"")
    print("--- wget questionnaire-templates (working ref) ---");print(o[:500])
finally:cli.close()
