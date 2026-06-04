import asyncio
from app.core.database import async_session
from sqlalchemy import text


async def m():
    async with async_session() as db:
        r = await db.execute(text(
            "SELECT section, COUNT(*) c FROM constitution_content_configs GROUP BY section"))
        print("SEED_ROWS:", [tuple(x) for x in r])
        r2 = await db.execute(text(
            "SELECT constitution_type, title FROM constitution_content_configs WHERE section='meal' AND constitution_type='特禀质'"))
        print("TEBING_MEAL:", [tuple(x) for x in r2])


asyncio.run(m())
