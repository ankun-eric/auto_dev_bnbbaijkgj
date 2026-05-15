#!/usr/bin/env python3
"""修复脏数据 + 在后端容器中跑修复脚本"""
import paramiko
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30,
            allow_agent=False, look_for_keys=False)

def run(cmd, timeout=120):
    print(f">>> {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", "replace")
    print(out)
    err = stderr.read().decode("utf-8", "replace")
    if err.strip(): print("[err]", err[:500])

# 先写一个修复脚本到服务器
script = '''
import asyncio, sys
sys.path.insert(0, "/app")
from app.core.database import engine
from sqlalchemy import text

async def fix():
    async with engine.begin() as c:
        for tbl in ("chat_function_buttons", "body_part_dict", "health_check_template"):
            r = await c.execute(text(f"UPDATE {tbl} SET created_at=COALESCE(created_at, NOW()), updated_at=COALESCE(updated_at, NOW()) WHERE created_at IS NULL OR updated_at IS NULL"))
            print(tbl, "affected:", r.rowcount)
        rr = await c.execute(text("SELECT id,name,created_at,updated_at FROM body_part_dict LIMIT 3"))
        for row in rr: print("part:", row)
        rr = await c.execute(text("SELECT id,name,created_at,updated_at FROM health_check_template LIMIT 3"))
        for row in rr: print("tpl:", row)

asyncio.run(fix())
'''
import base64
b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
run(f"echo {b64} | base64 -d > /tmp/_hsc_fix.py")
run(f"docker cp /tmp/_hsc_fix.py {PROJECT_ID}-backend:/tmp/_hsc_fix.py")
run(f"docker exec -w /app {PROJECT_ID}-backend python /tmp/_hsc_fix.py")
ssh.close()
