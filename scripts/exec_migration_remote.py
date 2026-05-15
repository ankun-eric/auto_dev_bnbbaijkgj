#!/usr/bin/env python3
"""手动在远程 backend 容器内执行迁移，看具体报错。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

INNER_SCRIPT = '''import asyncio, logging, sys
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
sys.path.insert(0, "/app")
from app.core.database import async_session
from app.services.prd_aichat_capsule_v2_migration import run_migration_with_session

async def main():
    try:
        stats = await run_migration_with_session(async_session)
        print("STATS:", stats)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("ERR:", repr(e))

asyncio.run(main())
'''


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)
    # 通过 sftp 上传到主机，再 docker cp 进容器
    sftp = c.open_sftp()
    with sftp.open("/tmp/_mig.py", "w") as f:
        f.write(INNER_SCRIPT)
    sftp.close()
    cmds = [
        f"docker cp /tmp/_mig.py {DEPLOY_ID}-backend:/tmp/_mig.py",
        f"docker exec {DEPLOY_ID}-backend python /tmp/_mig.py",
    ]
    for cmd in cmds:
        print("==>", cmd)
        _, o, e = c.exec_command(cmd)
        print("STDOUT:", o.read().decode("utf-8", errors="replace"))
        print("STDERR:", e.read().decode("utf-8", errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
