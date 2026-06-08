import asyncio
from app.core.database import Base, engine

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('增量建表完成（已存在的表已跳过）')

asyncio.run(migrate())
