
import asyncio
from datetime import date
from sqlalchemy import select, delete
from app.core.database import async_session
from app.core.security import get_password_hash
from app.models.models import User, FamilyMember, HealthProfile, UserRole

PHONES = ["13900099001", "13900099002", "13900099003"]

async def main():
    async with async_session() as s:
        # 清理
        for ph in PHONES:
            r = await s.execute(select(User).where(User.phone == ph))
            u = r.scalar_one_or_none()
            if u:
                await s.execute(delete(HealthProfile).where(HealthProfile.user_id == u.id))
                await s.execute(delete(FamilyMember).where(FamilyMember.user_id == u.id))
                await s.execute(delete(User).where(User.id == u.id))
        await s.commit()

        # 场景 A：family_members(is_self) 上有 nickname/gender/birthday，HealthProfile 无 self 记录
        u_a = User(phone=PHONES[0], password_hash=get_password_hash("p123"), nickname="A", role=UserRole.user)
        s.add(u_a); await s.flush()
        s.add(FamilyMember(user_id=u_a.id, relationship_type="本人", nickname="陈A", gender="男",
                           birthday=date(1980, 3, 3), is_self=True, status="active"))

        # 场景 B：全空（仅占位）
        u_b = User(phone=PHONES[1], password_hash=get_password_hash("p123"), nickname="B", role=UserRole.user)
        s.add(u_b); await s.flush()
        s.add(FamilyMember(user_id=u_b.id, relationship_type="本人", nickname="本人",
                           is_self=True, status="active"))

        # 场景 C：HealthProfile 有 name/gender，缺 birthday，但 family_members(is_self) 上有 birthday
        u_c = User(phone=PHONES[2], password_hash=get_password_hash("p123"), nickname="C", role=UserRole.user)
        s.add(u_c); await s.flush()
        s.add(FamilyMember(user_id=u_c.id, relationship_type="本人", nickname="本人",
                           birthday=date(1990, 9, 9), is_self=True, status="active"))
        s.add(HealthProfile(user_id=u_c.id, family_member_id=None, name="周C", gender="女", birthday=None))

        await s.commit()
        print("FIXTURE READY:", PHONES)

asyncio.run(main())
