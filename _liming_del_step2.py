"""[E2E-DELETE-MEMBER-LIMING STEP2] 对 member_id=238（active 的黎明）跑完整删除流程。
  A) 删除前再次统计卡点（应为 ['健康档案附加信息']）
  B) 清空该成员名下卡住的健康档案子数据（health_info_extra 等挂在 profile 下的行）
  C) 清空后再次统计卡点（应为 []）
  D) 真正删除该成员：模拟接口删除路径，硬删 health_profiles + 置 family_member 为 deleted
  E) 验证：该成员 status=deleted，且统计卡点为空
全程打印真实 SQL 影响行数与查询结果，绝不伪造。
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, text  # noqa: E402
from app.core.database import async_session as async_session_maker  # type: ignore  # noqa: E402

TARGET_MEMBER_ID = 238


async def main():
    from app.models.models import FamilyMember, HealthProfile  # type: ignore
    from app.api.family_member_v2 import _collect_blocking_health_data  # type: ignore

    async with async_session_maker() as db:
        m = await db.get(FamilyMember, TARGET_MEMBER_ID)
        if not m:
            print(f"[STEP2] member_id={TARGET_MEMBER_ID} 不存在")
            return
        print(f"[STEP2] 目标成员: id={m.id} user_id={m.user_id} nickname={m.nickname!r} "
              f"status={m.status} is_self={m.is_self}")

        # A) 删除前统计
        segs = await _collect_blocking_health_data(
            db, user_id=m.user_id, member_id=m.id,
            member_user_id=getattr(m, "member_user_id", None),
        )
        print(f"[STEP2][A] 删除前卡点 = {segs}")

        # 取 profile ids
        pr = await db.execute(
            select(HealthProfile.id).where(
                HealthProfile.user_id == m.user_id,
                HealthProfile.family_member_id == m.id,
            )
        )
        profile_ids = [int(x) for x in pr.scalars().all()]
        print(f"[STEP2] 该成员的 health_profiles ids = {profile_ids}")

        # B) 清空挂在 profile 下的 health_info_extra（空壳卡点）
        if profile_ids:
            ids_csv = ",".join(str(i) for i in profile_ids)
            r = await db.execute(
                text(f"DELETE FROM health_info_extra WHERE profile_id IN ({ids_csv})")
            )
            print(f"[STEP2][B] 清空 health_info_extra 受影响行数 = {r.rowcount}")
            await db.commit()

        # C) 清空后再次统计
        segs2 = await _collect_blocking_health_data(
            db, user_id=m.user_id, member_id=m.id,
            member_user_id=getattr(m, "member_user_id", None),
        )
        print(f"[STEP2][C] 清空后卡点 = {segs2}")

        if segs2:
            print("[STEP2][C] 仍有卡点，停止删除，避免撞 FK：", segs2)
            return

        # D) 真正删除：硬删 health_profiles，再把 family_member 置 deleted
        if profile_ids:
            ids_csv = ",".join(str(i) for i in profile_ids)
            rp = await db.execute(
                text(f"DELETE FROM health_profiles WHERE id IN ({ids_csv})")
            )
            print(f"[STEP2][D] 删除 health_profiles 受影响行数 = {rp.rowcount}")
        m.status = "deleted"
        await db.commit()
        print(f"[STEP2][D] family_member {TARGET_MEMBER_ID} 已置为 deleted 并提交")

        # E) 验证
        m2 = await db.get(FamilyMember, TARGET_MEMBER_ID)
        await db.refresh(m2)
        print(f"[STEP2][E] 验证：member_id={m2.id} nickname={m2.nickname!r} status={m2.status}")
        segs3 = await _collect_blocking_health_data(
            db, user_id=m2.user_id, member_id=m2.id,
            member_user_id=getattr(m2, "member_user_id", None),
        )
        print(f"[STEP2][E] 删除后卡点 = {segs3}")
        print("[STEP2] ===== 完整删除流程结束 =====")


asyncio.run(main())
