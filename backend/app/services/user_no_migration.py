import logging
import random

from sqlalchemy import select, func

from app.core.database import async_session as _async_session
from app.models.models import User

logger = logging.getLogger(__name__)


async def migrate_existing_users_user_no() -> None:
    """为所有 user_no 为空的存量用户生成唯一8位编号"""
    try:
        async with _async_session() as db:
            result = await db.execute(
                select(User).where(
                    (User.user_no.is_(None)) | (User.user_no == "")
                )
            )
            users = result.scalars().all()
            if not users:
                return

            existing_result = await db.execute(
                select(User.user_no).where(User.user_no.isnot(None))
            )
            existing_nos = {row[0] for row in existing_result.all() if row[0]}

            count = 0
            for user in users:
                for _ in range(10):
                    user_no = str(random.randint(10000000, 99999999))
                    if user_no not in existing_nos:
                        user.user_no = user_no
                        existing_nos.add(user_no)
                        count += 1
                        break
                else:
                    logger.warning("无法为用户 %s 生成唯一编号", user.id)

            await db.commit()
            if count:
                logger.info("已为 %d 个存量用户生成 user_no", count)
    except Exception as e:
        logger.error("user_no 迁移异常（不影响启动）: %s", e)
