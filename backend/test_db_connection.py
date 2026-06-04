import asyncio
from sqlalchemy import text
from app.core.database import async_session

async def test():
    async with async_session() as db:
        result = await db.execute(text("SELECT 1"))
        print("数据库连接成功:", result.scalar())

asyncio.run(test())
