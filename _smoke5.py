import paramiko
HOST = "newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/{USER}/{DEPLOY_ID}"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

def sh(cmd):
    si,so,se = cli.exec_command(cmd, timeout=120)
    return so.read().decode(errors="replace"), se.read().decode(errors="replace"), so.channel.recv_exit_status()

# 1) 检查上传文件是否存在
print("=== upload dir ===")
o,_,_ = sh(f"ls -la {REMOTE_BASE}/backend/app/api/ 2>&1 | head -20")
print(o)

# 2) 检查上传 tcm.py 是否含修复
o,_,_ = sh(f"grep -c 'asyncio.wait_for' {REMOTE_BASE}/backend/app/api/tcm.py 2>&1")
print("tcm.py wait_for count(remote upload):", o.strip())

# 3) 再次 docker cp 测试一个文件
o,e,c = sh(f"docker cp {REMOTE_BASE}/backend/app/api/tcm.py {DEPLOY_ID}-backend:/app/app/api/tcm.py")
print(f"docker cp tcm.py -> exit={c} out={o!r} err={e!r}")

o,_,_ = sh(f"docker exec {DEPLOY_ID}-backend grep -c 'asyncio.wait_for' /app/app/api/tcm.py")
print("inside container wait_for count:", o.strip())

cli.close()
