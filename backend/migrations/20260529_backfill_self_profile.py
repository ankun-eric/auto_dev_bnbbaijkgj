"""[BUG_FIX 2026-05-29] 旧用户本人健康档案数据回填迁移

目的：将旧用户散落在 family_members(is_self=1) / users 的本人资料，
     回填到 health_profiles(family_member_id IS NULL) 那条记录上，
     使他们打开"健康档案"页时不再因数据落库位置差异被误弹"完善资料"。

执行规则：
1. 遍历所有 users
2. 若该 user 在 health_profiles 已存在 family_member_id IS NULL 且 name/gender/birthday 三项齐全 → 跳过
3. 否则从兜底数据源补齐：family_members(is_self=1) 的 nickname / gender / birthday
4. 凑齐三项才写入；不足三项则只补齐已有的字段（不强制创建空记录）
5. 幂等：可重复执行；只补全空字段，不覆盖既有非空字段

用法：
    docker exec -it 6b099ed3-7175-4a78-91f4-44570c84ed27-backend \
        python /app/migrations/20260529_backfill_self_profile.py
或在容器内：python migrations/20260529_backfill_self_profile.py
"""
import asyncio
import sys
import os

# 让脚本既能在 backend/ 内运行，也能在容器内 /app 下运行
HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
for p in (PARENT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session as async_session_maker  # noqa: E402
from app.models.models import FamilyMember, HealthProfile, User  # noqa: E402


PLACEHOLDER_NAMES = {"本人", "我", "self", "Self", "ME", "Me", "me", ""}


def _is_name_empty(name):
    if name is None:
        return True
    s = str(name).strip()
    if not s:
        return True
    if s in PLACEHOLDER_NAMES:
        return True
    return False


async def backfill():
    stats = {"users": 0, "skipped_complete": 0, "updated": 0, "created": 0, "still_partial": 0}

    async with async_session_maker() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        stats["users"] = len(users)

        for u in users:
            res_hp = await db.execute(
                select(HealthProfile).where(
                    HealthProfile.user_id == u.id,
                    HealthProfile.family_member_id.is_(None),
                )
            )
            hp = res_hp.scalar_one_or_none()

            name_ok = bool(hp is not None and not _is_name_empty(hp.name))
            gender_ok = bool(hp is not None and hp.gender and str(hp.gender).strip())
            birthday_ok = bool(hp is not None and hp.birthday is not None)

            if name_ok and gender_ok and birthday_ok:
                stats["skipped_complete"] += 1
                continue

            res_fm = await db.execute(
                select(FamilyMember).where(
                    FamilyMember.user_id == u.id,
                    FamilyMember.is_self.is_(True),
                )
            )
            self_fm = res_fm.scalar_one_or_none()

            cand_name = None
            cand_gender = None
            cand_birthday = None

            if self_fm is not None:
                if self_fm.nickname and not _is_name_empty(self_fm.nickname):
                    cand_name = str(self_fm.nickname).strip()
                if self_fm.gender and str(self_fm.gender).strip():
                    cand_gender = str(self_fm.gender).strip()
                if self_fm.birthday is not None:
                    cand_birthday = self_fm.birthday

            if cand_name is None:
                rn = getattr(u, "real_name", None) or getattr(u, "nickname", None)
                if rn and not _is_name_empty(rn):
                    cand_name = str(rn).strip()
            if cand_gender is None:
                ug = getattr(u, "gender", None)
                if ug and str(ug).strip():
                    cand_gender = str(ug).strip()
            if cand_birthday is None:
                ub = getattr(u, "birthday", None)
                if ub is not None:
                    cand_birthday = ub

            new_name = cand_name if not name_ok else None
            new_gender = cand_gender if not gender_ok else None
            new_birthday = cand_birthday if not birthday_ok else None

            if new_name is None and new_gender is None and new_birthday is None:
                stats["still_partial"] += 1
                continue

            if hp is None:
                hp = HealthProfile(user_id=u.id, family_member_id=None)
                db.add(hp)
                stats["created"] += 1
            else:
                stats["updated"] += 1

            if new_name and _is_name_empty(hp.name):
                hp.name = new_name
            if new_gender and not (hp.gender and str(hp.gender).strip()):
                hp.gender = new_gender
            if new_birthday and hp.birthday is None:
                hp.birthday = new_birthday

        await db.commit()

    print("[BACKFILL DONE]", stats)
    return stats


if __name__ == "__main__":
    asyncio.run(backfill())
