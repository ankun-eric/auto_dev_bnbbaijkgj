"""把 backend 全部修改文件再 docker cp 一次，并 restart"""
import paramiko, os, io, tarfile, time
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE=f"/home/{USER}/{DEPLOY_ID}"
LOCAL = os.path.dirname(os.path.abspath(__file__))

BACKEND_FILES = [
    "backend/app/models/models.py",
    "backend/app/schemas/function_button.py",
    "backend/app/api/function_button.py",
    "backend/app/api/questionnaire.py",
    "backend/app/api/tcm.py",
    "backend/app/main.py",
    "backend/app/services/prd_questionnaire_autonext_v1_migration.py",
]

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

def sh(cmd, t=180):
    si,so,se = cli.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace"), se.read().decode(errors="replace"), so.channel.recv_exit_status()

# tar 上传
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tf:
    for rel in BACKEND_FILES:
        tf.add(os.path.join(LOCAL, rel), arcname=rel)
buf.seek(0)
data = buf.read()
print(f"tar size = {len(data)/1024:.1f} KiB")

sftp = cli.open_sftp()
with sftp.open(f"{REMOTE_BASE}/_be2.tar.gz", "wb") as f:
    f.write(data)
sftp.close()

o,e,c = sh(f"cd {REMOTE_BASE} && tar -xzf _be2.tar.gz && ls -la backend/app/api/tcm.py backend/app/api/function_button.py backend/app/api/questionnaire.py")
print(o, e)

# docker cp 每个
for rel in BACKEND_FILES:
    in_container = "/app/" + rel.replace("backend/", "")
    o,e,c = sh(f"docker cp {REMOTE_BASE}/{rel} {DEPLOY_ID}-backend:{in_container}")
    print(f"cp {rel} -> exit={c} err={e!r}")

# restart
print("restart backend ...")
o,e,c = sh(f"docker restart {DEPLOY_ID}-backend", t=120)
print(o, e)

# wait & verify
time.sleep(15)
o,_,_ = sh(f"docker logs --tail 200 {DEPLOY_ID}-backend 2>&1 | tail -n 80")
print("--- backend logs ---")
print(o)

# 校验关键代码
o,_,_ = sh(f"docker exec {DEPLOY_ID}-backend grep -c 'asyncio.wait_for' /app/app/api/tcm.py")
print("tcm wait_for:", o.strip())
o,_,_ = sh(f"docker exec {DEPLOY_ID}-backend grep -c 'PRESENTATION_CONTAINERS' /app/app/api/function_button.py")
print("fb PRESENTATION_CONTAINERS:", o.strip())
o,_,_ = sh(f"docker exec {DEPLOY_ID}-backend grep -c 'presentation_container' /app/app/api/questionnaire.py")
print("qn presentation_container:", o.strip())

cli.close()
print("done")
