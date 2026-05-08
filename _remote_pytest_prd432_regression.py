"""[PRD-432] 回归测试：在 backend 容器内运行 PRD-420 + Bug-419 + ai_home_config 关键回归用例"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PWD, timeout=30)


def run(cmd, t=300):
    print(f"\n>>> {cmd[:140]}")
    s, o, e = ssh.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out:
        print(out[-4000:])
    if err:
        print("STDERR:", err[-500:])
    rc = o.channel.recv_exit_status()
    print(f"<<< exit={rc}")
    return rc, out, err


# 检查列已迁移
run(
    f"docker exec {DEPLOY_ID}-backend bash -lc \"python -c 'import asyncio; from app.core.database import async_session; from sqlalchemy import text\\n"
    "async def m():\\n"
    "    async with async_session() as db:\\n"
    "        for col in [\\\"past_history_is_none\\\",\\\"allergy_is_none\\\",\\\"medication_is_none\\\"]:\\n"
    "            r = await db.execute(text(f\\\"SHOW COLUMNS FROM health_profiles LIKE \\\\\\'{col}\\\\\\'\\\"))\\n"
    "            rows = r.all()\\n"
    "            print(col, len(rows))\\n"
    "        r = await db.execute(text(\\\"SHOW COLUMNS FROM chat_messages LIKE \\\\\\'consultant_target_id\\\\\\'\\\"))\\n"
    "        print(\\\"consultant_target_id\\\", len(r.all()))\\n"
    "asyncio.run(m())\n"
    "'\"",
    t=60,
)

# 关键回归
run(
    f"docker exec -w /app {DEPLOY_ID}-backend python -m pytest tests/test_prd420_consult_target_picker.py tests/test_bug419_chat_sessions.py tests/test_ai_home_config.py -v --no-header 2>&1 | tail -80",
    t=300,
)

ssh.close()
