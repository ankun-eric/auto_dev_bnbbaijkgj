"""Async DB init and admin account check."""
import asyncio
from app.core.database import engine, Base, async_session
from sqlalchemy import inspect, select
from app.models.models import User
from app.core.security import get_password_hash

async def check_tables():
    async with engine.begin() as conn:
        def sync_check(sync_conn):
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            return tables
        tables = await conn.run_sync(sync_check)
        print(f"Existing tables ({len(tables)}): {sorted(tables)}")
        return tables

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created/updated")

async def check_admin():
    from app.models.models import AccountIdentity, IdentityType
    
    async with async_session() as db:
        result = await db.execute(select(User).where(User.phone == "admin"))
        user = result.scalar_one_or_none()
        if user:
            print(f"Admin account EXISTS (id={user.id}, phone={user.phone}, role={user.role})")
            # Ensure identity exists
            id_result = await db.execute(
                select(AccountIdentity).where(AccountIdentity.user_id == user.id)
            )
            identity = id_result.scalar_one_or_none()
            if not identity:
                db.add(AccountIdentity(user_id=user.id, identity_type=IdentityType.user))
                await db.commit()
                print("Added user identity to admin account")
            return True
        else:
            print("Admin account NOT FOUND - creating...")
            user = User(
                phone="admin",
                password_hash=get_password_hash("admin123"),
                nickname="Admin",
                role="user",
                is_superuser=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            # Add identity
            db.add(AccountIdentity(user_id=user.id, identity_type=IdentityType.user))
            await db.commit()
            print(f"Admin account CREATED (id={user.id}, phone={user.phone})")
            return True

async def main():
    print("=== DB Init ===")
    tables = await check_tables()
    await create_tables()
    tables2 = await check_tables()
    print(f"After init: {len(tables)} -> {len(tables2)} tables")
    
    print("\n=== Admin ===")
    await check_admin()
    
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())
