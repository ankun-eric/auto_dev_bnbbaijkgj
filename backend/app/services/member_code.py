"""Bug #6 修复：会员码生成规则。

字符集：23456789ABCDEFGHJKLMNPQRSTUVWXYZ（32 位，剔除易混淆字符 0/O/1/I/L）
长度：6 位
冲突重试上限：10 次
存储/展示：统一大写。
"""
from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User

MEMBER_CODE_CHARSET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
MEMBER_CODE_LENGTH = 6
MEMBER_CODE_MAX_RETRIES = 10


def generate_member_code() -> str:
    """生成一个 6 位会员码，字符取自 MEMBER_CODE_CHARSET。"""
    return "".join(secrets.choice(MEMBER_CODE_CHARSET) for _ in range(MEMBER_CODE_LENGTH))


async def _is_code_taken(db: AsyncSession, code: str) -> bool:
    result = await db.execute(
        select(User.id).where(User.member_card_no == code)
    )
    return result.scalar_one_or_none() is not None


async def allocate_unique_member_code(
    db: AsyncSession,
    max_retries: int = MEMBER_CODE_MAX_RETRIES,
) -> str:
    """分配一个不冲突的会员码；重试上限达到后抛出 RuntimeError。"""
    last_candidate: Optional[str] = None
    for _ in range(max_retries):
        candidate = generate_member_code()
        last_candidate = candidate
        if not await _is_code_taken(db, candidate):
            return candidate
    raise RuntimeError(
        f"allocate_unique_member_code: exceeded {max_retries} retries, last={last_candidate}"
    )
