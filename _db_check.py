import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

async def main():
    engine = create_async_engine(
        'mysql+aiomysql://root:bini_health_2026@localhost:3306/bini_health',
        echo=False,
        connect_args={'connect_timeout': 5}
    )
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text('SELECT 1'))
            row = result.fetchone()
            sys.stdout.write(f'DB连接成功: {row}\n')
            sys.stdout.flush()
    except Exception as e:
        sys.stdout.write(f'DB连接失败: {type(e).__name__}: {e}\n')
        sys.stdout.flush()
        await engine.dispose()
        return

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT id, user_id, family_member_id, name, gender, birth_date FROM health_profiles WHERE user_id = 18 AND family_member_id IS NULL")
        )
        rows = result.fetchall()
        sys.stdout.write(f'\nuser_id=18 AND family_member_id IS NULL 的记录数: {len(rows)}\n')
        for row in rows:
            sys.stdout.write(f'  id={row[0]}, user_id={row[1]}, family_member_id={row[2]}, name={row[3]}, gender={row[4]}, birth_date={row[5]}\n')
        sys.stdout.flush()

        result2 = await session.execute(
            text("SELECT id, user_id, family_member_id, name FROM health_profiles WHERE user_id = 18")
        )
        rows2 = result2.fetchall()
        sys.stdout.write(f'\nuser_id=18 的全部记录数: {len(rows2)}\n')
        for row in rows2:
            sys.stdout.write(f'  id={row[0]}, user_id={row[1]}, family_member_id={row[2]}, name={row[3]}\n')
        sys.stdout.flush()

    await engine.dispose()

asyncio.run(main())
