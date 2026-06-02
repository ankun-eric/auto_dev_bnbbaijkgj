"""[BUGFIX-FAMILY-DUPLICATE-BIND-V1 2026-06-02] 家庭成员重复绑定判重服务。

解决的 Bug：同一个客户（S1）扫了管理者名下 A 成员的邀请二维码绑定成功后，
又能扫该管理者名下 B 成员的二维码再次绑定，导致同一个人在同一管理者名下
被重复绑成两条 FamilyManagement 记录。

修复口径（已与产品敲定）：
- "同一个人"判定：用户 ID 相同 **或** 手机号相同，任一命中即视为同一人。
- 唯一性范围：**同一管理者名下唯一**，不做全局唯一（别的管理者发的邀请照样能绑）。
- 命中即拦截，统一文案："您已是该家庭的成员，无法重复绑定。"

所有产生绑定关系（写入 FamilyManagement(status="active")）的入口统一复用本函数，
从根上堵死重复绑定，避免判重逻辑散落多份。
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import FamilyManagement, User

logger = logging.getLogger(__name__)

DUPLICATE_BIND_DETAIL = "您已是该家庭的成员，无法重复绑定。"


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    """规范化手机号用于比对：去除首尾空白，空串视为 None。"""
    if phone is None:
        return None
    p = str(phone).strip()
    return p or None


async def is_duplicate_bind(
    db: AsyncSession,
    manager_user_id: int,
    managed_user_id: int,
    managed_phone: Optional[str] = None,
) -> bool:
    """判断 managed_user_id（被守护人）是否已在 manager_user_id 名下存在 active 绑定。

    判重维度（任一命中即为重复）：
      1) 用户 ID 相同：已存在一条 manager_user_id 名下 active 且 managed_user_id 一致的记录；
      2) 手机号相同：已存在一条 manager_user_id 名下 active 的记录，其被守护人对应的
         User.phone 与当前接受者手机号一致（覆盖"同一人换了账号但手机号一致"的情况）。

    参数：
      - manager_user_id: 邀请发起人 / 守护者（绑定关系中的 manager）。
      - managed_user_id: 当前接受邀请的人（绑定关系中的 managed）。
      - managed_phone: 当前接受者手机号，用于手机号维度判重；为空则跳过手机号判重。

    返回：True 表示重复（应拦截），False 表示可放行。
    """
    # 维度 1：用户 ID 精确判重（最常见、最快命中）
    exact = await db.execute(
        select(FamilyManagement.id).where(
            FamilyManagement.manager_user_id == manager_user_id,
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
        ).limit(1)
    )
    if exact.scalar_one_or_none() is not None:
        return True

    # 维度 2：手机号判重（同一人换了账号但手机号一致的漏网情况）
    phone = _normalize_phone(managed_phone)
    if phone:
        phone_hit = await db.execute(
            select(FamilyManagement.id)
            .join(User, User.id == FamilyManagement.managed_user_id)
            .where(
                FamilyManagement.manager_user_id == manager_user_id,
                FamilyManagement.status == "active",
                User.phone == phone,
            )
            .limit(1)
        )
        if phone_hit.scalar_one_or_none() is not None:
            return True

    return False
