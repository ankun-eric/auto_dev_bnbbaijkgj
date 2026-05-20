import paramiko
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

def sh(cmd, t=60):
    si, so, se = cli.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace"), se.read().decode(errors="replace")

o,_ = sh(f"docker exec {DEPLOY_ID}-backend find / -name 'questionnaire.py' -path '*/api/*' 2>/dev/null")
print("=== questionnaire.py 路径 ===")
print(o)

o,_ = sh(f"docker exec {DEPLOY_ID}-backend find / -name 'tcm.py' -path '*/api/*' 2>/dev/null")
print("=== tcm.py 路径 ===")
print(o)

o,_ = sh(f"docker exec {DEPLOY_ID}-backend find / -name 'function_button.py' -path '*/api/*' 2>/dev/null")
print("=== function_button.py 路径 ===")
print(o)

cli.close()
