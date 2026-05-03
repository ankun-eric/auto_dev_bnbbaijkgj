"""卡到期触达任务（PRD v2.0 第 5 期）

- 扫描到期前 7 / 3 / 1 天的卡
- 写入 messages / notifications 站内消息
- （可选）发送微信小程序模板消息（仅有 openid 用户）

调度入口：建议挂入项目既有的 APScheduler / Celery Beat（每日 03:00 执行 `run_card_expiry_notify`）
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    CardDefinition,
    Notification,
    NotificationType,
    User,
    UserCard,
    UserCardStatus,
)


logger = logging.getLogger(__name__)


async def scan_expiring_cards(db: AsyncSession) -> List[UserCard]:
    """查询 valid_to 落在 today+1 / today+3 / today+7 范围内的 active 卡。"""
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    targets: List[datetime] = []
    for days in (1, 3, 7):
        d = today + timedelta(days=days)
        targets.append(d)

    out: List[UserCard] = []
    for d in targets:
        next_day = d + timedelta(days=1)
        res = await db.execute(
            select(UserCard).where(
                UserCard.status == UserCardStatus.active,
                UserCard.valid_to >= d,
                UserCard.valid_to < next_day,
            )
        )
        out.extend(res.scalars().all())
    return out


async def send_expiry_notify(db: AsyncSession, user_card: UserCard) -> bool:
    """发送站内消息（如果用户有 openid，可在此扩展模板消息发送）。

    幂等：通过比对 Notification 中相同 user_id + content 关键词来去重。
    """
    cd_q = await db.execute(
        select(CardDefinition).where(CardDefinition.id == user_card.card_definition_id)
    )
    cd = cd_q.scalar_one_or_none()
    if not cd:
        return False

    days = (user_card.valid_to - datetime.utcnow()).days
    title = f"您的卡「{cd.name}」即将到期"
    content = (
        f"您持有的「{cd.name}」将于 {user_card.valid_to.strftime('%Y-%m-%d')} 到期，"
        f"剩余 {max(0, days)} 天，请及时使用或续卡。"
    )
    # 简单去重：相同 user 同一卡同 days 不再发
    dup_key = f"card_expiry:{user_card.id}:{days}"
    dup_q = await db.execute(
        select(Notification).where(
            Notification.user_id == user_card.user_id,
            Notification.title == title,
            Notification.content.like(f"%{dup_key}%"),
        )
    )
    if dup_q.scalar_one_or_none():
        return False

    n = Notification(
        user_id=user_card.user_id,
        title=title,
        content=content + f"\n\n[ref:{dup_key}]",
        type=NotificationType.system,
        is_read=False,
    )
    db.add(n)
    await db.flush()
    return True


async def run_card_expiry_notify(db: AsyncSession) -> int:
    cards = await scan_expiring_cards(db)
    sent = 0
    for uc in cards:
        try:
            ok = await send_expiry_notify(db, uc)
            if ok:
                sent += 1
        except Exception as e:
            logger.exception("send_expiry_notify failed for user_card_id=%s: %s", uc.id, e)
    return sent
