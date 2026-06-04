# -*- coding: utf-8 -*-
"""通过 backend 容器在线上实测删除家庭成员的统计逻辑。
将一段 Python 代码 base64 编码后传入容器执行，规避 PowerShell 中文/引号转义问题。
"""
import base64
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
CT = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

# 在容器内执行的脚本：找“黎明”，统计其名下子数据，并模拟删除接口的拦截判定
REMOTE = r'''
import asyncio
from sqlalchemy import select, text
from app.core.database import async_session
from app.models.models import FamilyMember

async def main():
    async with async_session() as db:
        rows = (await db.execute(text(
            "SELECT id, user_id, nickname, member_user_id, status "
            "FROM family_members WHERE nickname LIKE :kw"
        ), {"kw": "%\u9ece\u660e%"})).fetchall()
        print("=== family_members LIKE 黎明 ===")
        for r in rows:
            print(dict(r._mapping))
        if not rows:
            print("没有找到名字含‘黎明’的家庭成员")
            return
        # 取第一条非 deleted 的来实测统计
        target = None
        for r in rows:
            m = r._mapping
            if m["status"] != "deleted":
                target = m
                break
        if target is None:
            target = rows[0]._mapping
            print("注意：黎明档案已是 deleted 状态")
        mid = target["id"]; uid = target["user_id"]; muid = target["member_user_id"]
        print(f"\n=== 实测 _collect_blocking_health_data member_id={mid} user_id={uid} ===")
        from app.api.family_member_v2 import _collect_blocking_health_data
        segs = await _collect_blocking_health_data(db, user_id=uid, member_id=mid, member_user_id=muid)
        print("blocking segments =>", segs)
        if segs:
            print("预期提示 =>", "该成员名下还有" + "\u3001".join(segs) + "\uff0c\u8bf7\u5148\u6e05\u7a7a\u540e\u518d\u5220\u9664\u3002")
        else:
            print("统计为空：按当前逻辑会放行删除（不应再撞兜底报错）")

        # 同时把该 profile 下所有对 health_profiles 有外键的子表行数列出来，排查是否有漏统计的表
        pr = (await db.execute(text(
            "SELECT id FROM health_profiles WHERE user_id=:u AND family_member_id=:m"
        ), {"u": uid, "m": mid})).fetchall()
        pids = [x._mapping["id"] for x in pr]
        print("\nprofile_ids =>", pids)
        if pids:
            fk = (await db.execute(text(
                "SELECT conrelid::regclass AS child_table "
                "FROM pg_constraint "
                "WHERE contype='f' AND confrelid='health_profiles'::regclass"
            ))).fetchall()
            print("\n=== 所有引用 health_profiles 的子表 ===")
            for f in fk:
                t = str(f._mapping["child_table"])
                try:
                    cnt = (await db.execute(text(
                        f"SELECT count(*) c FROM {t} WHERE profile_id = ANY(:p)"
                    ), {"p": pids})).fetchone()._mapping["c"]
                except Exception as e:
                    cnt = f"(查不了:{e})"
                print(f"  {t}: {cnt}")

asyncio.run(main())
'''

def run(cmd, timeout=180):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    cli.close()
    return out, err

b64 = base64.b64encode(REMOTE.encode("utf-8")).decode("ascii")
cmd = (
    f"docker exec {CT} sh -c "
    f"'echo {b64} | base64 -d > /tmp/_chk.py && cd /app && PYTHONPATH=/app python /tmp/_chk.py'"
)
out, err = run(cmd)
print("=== STDOUT ===")
print(out)
if err.strip():
    print("=== STDERR ===")
    print(err)
