"""在远程后端容器中运行新增的回调 dataType 测试用例。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    return c


def run(c, cmd, timeout=600):
    print(f"$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    print(f"(rc={rc})\n")
    return rc, out, err


def main():
    c = conn()
    # 检查 DB 是否已加 data_type 列（在容器内通过 sqlalchemy inspect）
    print("=== Step 1: 检查 home_safety_callback_log 的 data_type 列 ===")
    run(c, f"""docker exec {DEPLOY_ID}-backend python -c "
import asyncio
from sqlalchemy import inspect
from app.core.database import engine
async def main():
    async with engine.connect() as conn:
        def _list(sc):
            insp = inspect(sc)
            cols = [c['name'] for c in insp.get_columns('home_safety_callback_log')]
            return cols
        cols = await conn.run_sync(_list)
        print('CALLBACK_LOG_COLS=', cols)
        print('HAS_data_type=', 'data_type' in cols)
asyncio.run(main())
" 2>&1""")

    print("=== Step 2: 在容器内运行新测试 ===")
    run(c, f"docker exec {DEPLOY_ID}-backend bash -lc 'cd /app && python -m pytest tests/test_home_safety_callback_datatype_v1.py -v --tb=short 2>&1'", timeout=600)


if __name__ == "__main__":
    main()
