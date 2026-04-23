import asyncio
from app.models.models import User, UserRole
from app.core.database import async_session as SessionLocal
from app.core.security import get_password_hash as hash_password
from sqlalchemy import select


async def main():
    async with SessionLocal() as s:
        r = await s.execute(select(User).where(User.role == UserRole.admin))
        admins = r.scalars().all()
        for u in admins[:5]:
            print("EXISTING", u.id, u.phone, u.nickname, u.is_superuser)
        phone = "13800050505"
        r2 = await s.execute(select(User).where(User.phone == phone))
        u = r2.scalar_one_or_none()
        if not u:
            u = User(
                phone=phone,
                nickname="SmokeAdmin",
                role=UserRole.admin,
                is_superuser=True,
                status="active",
                password_hash=hash_password("Smoke123!"),
            )
            s.add(u)
            await s.commit()
            await s.refresh(u)
            print("CREATED", u.id, phone, "Smoke123!")
        else:
            u.password_hash = hash_password("Smoke123!")
            u.role = UserRole.admin
            u.is_superuser = True
            u.status = "active"
            await s.commit()
            print("UPDATED", u.id, phone, "Smoke123!")


if __name__ == "__main__":
    asyncio.run(main())
