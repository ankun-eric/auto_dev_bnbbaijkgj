import paramiko, json
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

def sh(cmd, t=60):
    si, so, se = cli.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace"), se.read().decode(errors="replace")

o,_ = sh(f"docker exec {DEPLOY_ID}-backend grep -n 'asyncio.wait_for\\|PRESENTATION_CONTAINERS\\|presentation_container' /app/app/api/tcm.py /app/app/api/function_button.py /app/app/api/questionnaire.py 2>&1")
print(o)

cli.close()
