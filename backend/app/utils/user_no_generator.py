import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User

MAX_RETRIES = 5


async def generate_unique_user_no(db: AsyncSession) -> str:
    for _ in range(MAX_RETRIES):
        user_no = str(random.randint(10000000, 99999999))
        result = await db.execute(
            select(User.id).where(User.user_no == user_no).limit(1)
        )
        if result.scalar_one_or_none() is None:
            return user_no
    raise RuntimeError("无法生成唯一用户编号，请稍后重试")
