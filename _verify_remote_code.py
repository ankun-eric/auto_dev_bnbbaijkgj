import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com','22','ubuntu','Newbang888')
CTR = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

for cmd in [
    # main.py 是否含 family_self_backfill_migration
    f"docker exec {CTR} grep -n 'family_self_backfill_migration' /app/app/main.py || echo NOT_FOUND_main",
    # chat.py 是否含 _ensure_self_family_member
    f"docker exec {CTR} grep -n '_ensure_self_family_member' /app/app/api/chat.py || echo NOT_FOUND_chat",
    # 报告解读引擎 import
    f"docker exec {CTR} grep -n 'run_report_interpret_stream' /app/app/services/report_interpret_engine.py | head -3 || echo NOT_FOUND_engine",
    # 回填迁移文件存在
    f"docker exec {CTR} ls -la /app/app/services/family_self_backfill_migration.py 2>&1 | head -3",
    # schema 含 intent 字段
    f"docker exec {CTR} grep -n 'intent: Optional' /app/app/schemas/chat.py || echo NOT_FOUND_schema",
]:
    _, out, _ = c.exec_command(cmd)
    print(f"$ {cmd}")
    print(out.read().decode()[:600])

c.close()
