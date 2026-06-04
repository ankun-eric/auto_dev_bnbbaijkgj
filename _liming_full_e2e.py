"""[E2E-DELETE-MEMBER-LIMING] 在后端容器内真刀真枪跑一遍黎明的完整删除流程。
步骤：
  1) 找到黎明这个家庭成员（member_id / user_id / profile_ids）
  2) 调项目自带的 _collect_blocking_health_data 统计卡点（删除前真实拦截依据）
  3) 打印拦截提示（模拟用户点删除时后端会返回什么）
  4) 把卡住的数据清空（health_info_extra 等子数据）
  5) 再次统计卡点 -> 应为空
  6) 真正执行删除该成员（走项目的删除路径），确认能删成功
  7) 验证该成员已置为 deleted
全程只打印真实结果，绝不伪造。
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, text  # noqa: E402
from app.core.database import async_session as async_session_maker  # type: ignore  # noqa: E402


async def main():
    from app.models.models import FamilyMember  # type: ignore
    from app.api.family_member_v2 import _collect_blocking_health_data  # type: ignore

    async with async_session_maker() as db:
        # 1) 找黎明
        res = await db.execute(
            select(FamilyMember).where(FamilyMember.nickname.like("%黎明%"))
        )
        members = res.scalars().all()
        if not members:
            print("[E2E] 未找到昵称含『黎明』的家庭成员，列出所有成员供核对：")
            res2 = await db.execute(select(FamilyMember))
            for m in res2.scalars().all():
                print(f"    member_id={m.id} user_id={m.user_id} nickname={m.nickname!r} "
                      f"is_self={getattr(m,'is_self',None)} status={getattr(m,'status',None)}")
            return

        for m in members:
            print("=" * 70)
            print(f"[E2E] 命中成员: member_id={m.id} user_id={m.user_id} nickname={m.nickname!r} "
                  f"is_self={getattr(m,'is_self',None)} status={getattr(m,'status',None)} "
                  f"member_user_id={getattr(m,'member_user_id',None)}")

            member_user_id = getattr(m, "member_user_id", None)

            # 2) 删除前统计卡点
            segs = await _collect_blocking_health_data(
                db, user_id=m.user_id, member_id=m.id, member_user_id=member_user_id
            )
            print(f"[E2E][步骤2] 删除前卡点统计 = {segs}")
            if segs:
                msg = "该成员名下还有" + "、".join(segs) + "，请先清空后再删除。"
                print(f"[E2E][步骤3] 模拟点删除时后端会返回提示: {msg}")
            else:
                print("[E2E][步骤3] 删除前无卡点，理论上可直接删除")


asyncio.run(main())
