"""上传修复后的迁移脚本，重启 backend，安装 pytest 跑测试"""
import os
import time
import paramiko

PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{PROJECT_ID}"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def run(cmd, timeout=600):
    _, out, err = cli.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace")
    e = err.read().decode("utf-8", errors="replace")
    rc = out.channel.recv_exit_status()
    return rc, o, e

sftp = cli.open_sftp()
print("=== 上传修复后的清理迁移脚本 ===")
sftp.put(
    "backend/app/services/family_member_nickname_cleanup_migration.py",
    f"{PROJ_DIR}/backend/app/services/family_member_nickname_cleanup_migration.py",
)
sftp.close()

print("=== 重启 backend（不重新构建，因为只改了 py 文件） ===")
rc, o, e = run(f"cd {PROJ_DIR} && docker compose restart backend 2>&1", timeout=120)
print(o[-500:])

print("=== 等待迁移完成 ===")
time.sleep(15)

print("=== 查清理迁移日志 ===")
rc, o, _ = run(
    f"docker logs --since=2m {PROJECT_ID}-backend 2>&1 | grep -E 'family_member_nickname_cleanup'"
)
print(o)

print("=== 校验脏数据 + 列状态 ===")
rc, o, _ = run(
    f"docker exec {PROJECT_ID}-db mysql -uroot -pbini_health_2026 -t -e "
    f"\"SELECT COUNT(*) AS empty_nick FROM family_members WHERE nickname IS NULL OR TRIM(nickname)='';\" "
    f"bini_health 2>/dev/null"
)
print(o)
rc, o, _ = run(
    f"docker exec {PROJECT_ID}-db mysql -uroot -pbini_health_2026 -t -e "
    f"\"SHOW COLUMNS FROM family_members LIKE 'nickname';\" "
    f"bini_health 2>/dev/null"
)
print(o)

print("=== 在 backend 容器内安装 pytest ===")
rc, o, _ = run(
    f"docker exec {PROJECT_ID}-backend sh -c "
    f"'pip install --no-cache-dir pytest pytest-asyncio aiosqlite -i https://mirrors.cloud.tencent.com/pypi/simple --quiet 2>&1 | tail -10'",
    timeout=300,
)
print(o[-1500:])

print("=== 跑新增测试用例 ===")
rc, o, _ = run(
    f"docker exec {PROJECT_ID}-backend sh -c "
    f"'cd /app && python -m pytest tests/test_family_nickname_notnull_20260530.py -v --tb=short 2>&1' | tail -80",
    timeout=300,
)
print(o)

print("=== 跑 family 主测试集回归 ===")
rc, o, _ = run(
    f"docker exec {PROJECT_ID}-backend sh -c "
    f"'cd /app && python -m pytest tests/test_family.py tests/test_family_member_v2_20260518.py -v --tb=line 2>&1' | tail -100",
    timeout=600,
)
print(o[-4000:])

cli.close()
