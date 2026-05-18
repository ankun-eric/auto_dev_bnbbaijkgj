"""[PRD-FAMILY-GUARDIAN-V1] 家庭体检异常·守护推送 - 核心服务。

包含：
- 守护者集合算法（建档人 ∪ 双向共管对方 − 被守护者本人）
- 5 分钟同 report_date 窗口去重（内存版，无 Redis 也能用）
- 体检异常聚合推送：写 family_alert_logs + SystemMessage
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AlertMessageTemplate,
    FamilyAlertLog,
    FamilyManagement,
    FamilyMember,
    SystemMessage,
    User,
)

logger = logging.getLogger(__name__)

# 进程内去重缓存（无 Redis 时的降级方案）
# key = (member_id, report_date_str) -> expires_at
_DEDUP_CACHE: dict[tuple[int, str], datetime] = {}
_DEDUP_LOCK = asyncio.Lock()
_DEDUP_TTL_SEC = 300

DEFAULT_RELATIONSHIP = "家人"


def _normalize_relationship(member: FamilyMember) -> str:
    """家庭成员的关系称谓回退顺序：relationship_type → nickname → 默认值。"""
    if member is None:
        return DEFAULT_RELATIONSHIP
    raw = (getattr(member, "relationship_type", None) or "").strip()
    if raw:
        # 常见 type → 中文称谓
        mapping = {
            "father": "父亲",
            "mother": "母亲",
            "child": "孩子",
            "spouse": "配偶",
            "grandfather": "爷爷",
            "grandmother": "奶奶",
            "self": "本人",
            "other": "家人",
        }
        return mapping.get(raw.lower(), raw)
    return DEFAULT_RELATIONSHIP


async def guardians_of(db: AsyncSession, member: FamilyMember) -> set[int]:
    """守护者集合 = 建档人 ∪ 双向共管对方 − 被守护者本人。

    对应 PRD §2.1 算法定义，覆盖三类场景：
      A) 子女拍照上传 / 老人零参与 → 仅返回建档人
      B) 子女发起邀请→老人接受 → 返回建档子女
      C) 老人发起邀请→子女接受（老年大学主流）→ 反向 union 后返回子女
    """
    result: set[int] = set()
    if member is None:
        return result

    if getattr(member, "user_id", None):
        result.add(member.user_id)

    # 正向：managed_member_id == member.id
    rows = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_member_id == member.id,
            FamilyManagement.status == "active",
        )
    )
    for fm in rows.scalars():
        if fm.manager_user_id:
            result.add(fm.manager_user_id)
        # 双向共管：managed_user_id 也是潜在守护者
        if fm.managed_user_id and fm.managed_user_id != getattr(member, "member_user_id", None):
            result.add(fm.managed_user_id)

    # 反向：场景 C - 老人发起，managed_user_id 视为 manager 角色
    # 这里通过查找该 member 对应的 user（即老人 user_id == member.user_id），
    # 把以老人为 manager 的 family_management 中的 managed_user_id 也纳入
    if getattr(member, "user_id", None):
        rows = await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == member.user_id,
                FamilyManagement.status == "active",
            )
        )
        for fm in rows.scalars():
            if fm.managed_user_id:
                result.add(fm.managed_user_id)

    # 排除被守护者本人
    self_uid = getattr(member, "member_user_id", None) or getattr(member, "user_id", None)
    # 仅在 member 表示老人（is_self 或 member_user_id 与 user_id 不一致）时排除
    member_user_id = getattr(member, "member_user_id", None)
    if member_user_id:
        result.discard(member_user_id)

    return result


async def _check_and_set_dedup(member_id: int, report_date) -> bool:
    """5 分钟去重：成功设置返回 True；命中已有去重 key 返回 False。"""
    rd_str = ""
    try:
        rd_str = report_date.isoformat() if report_date else "none"
    except Exception:
        rd_str = str(report_date)
    key = (int(member_id), rd_str)
    now = datetime.utcnow()
    async with _DEDUP_LOCK:
        # 清理过期
        expired = [k for k, exp in _DEDUP_CACHE.items() if exp <= now]
        for k in expired:
            _DEDUP_CACHE.pop(k, None)
        if key in _DEDUP_CACHE:
            return False
        _DEDUP_CACHE[key] = now + timedelta(seconds=_DEDUP_TTL_SEC)
        return True


def _render(template: str, ctx: dict) -> str:
    """极简三占位渲染：仅替换 {relationship} {nickname} {count}。"""
    out = template or ""
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", str(v))
    return out


async def _fetch_template(db: AsyncSession, code: str) -> Optional[AlertMessageTemplate]:
    res = await db.execute(
        select(AlertMessageTemplate).where(
            AlertMessageTemplate.code == code,
            AlertMessageTemplate.is_active.is_(True),
        )
    )
    return res.scalar_one_or_none()


async def push_aggregated_alert(
    db: AsyncSession,
    member: FamilyMember,
    abnormal_count: int,
    report_id: Optional[int] = None,
    report_date=None,
    severity: str = "warning",
) -> dict:
    """对一份体检报告，按守护者集合聚合下发推送（每报告 1 条/守护者）。

    返回：{"guardians": [...], "sent": N, "deduped": bool}
    """
    if abnormal_count is None or abnormal_count <= 0:
        return {"guardians": [], "sent": 0, "deduped": False, "reason": "no_abnormal"}

    if not await _check_and_set_dedup(member.id, report_date):
        return {"guardians": [], "sent": 0, "deduped": True}

    guardians = await guardians_of(db, member)
    if not guardians:
        return {"guardians": [], "sent": 0, "deduped": False, "reason": "no_guardian"}

    relationship = _normalize_relationship(member)
    nickname = getattr(member, "nickname", None) or "家人"
    ctx = {"relationship": relationship, "nickname": nickname, "count": abnormal_count}

    tpl = await _fetch_template(db, "checkup_abnormal_mini")
    title = _render(tpl.title if tpl else "体检异常提醒", ctx)
    content = _render(
        tpl.content if tpl else "您的{relationship}{nickname}的体检报告有 {count} 项异常",
        ctx,
    )

    sent = 0
    now = datetime.utcnow()
    for uid in guardians:
        # 写系统消息（小程序站内信通道）
        sys_msg = SystemMessage(
            message_type="family_checkup_abnormal",
            recipient_user_id=uid,
            sender_user_id=member.user_id,
            title=title,
            content=content,
            related_business_id=str(report_id) if report_id else None,
            related_business_type="checkup_report",
            click_action="/checkup-detail",
            click_action_params={"report_id": report_id, "member_id": member.id},
        )
        db.add(sys_msg)

        # 写推送日志（管理后台可查）
        log = FamilyAlertLog(
            member_id=member.id,
            guardian_user_id=uid,
            report_id=report_id,
            severity=severity,
            abnormal_count=abnormal_count,
            template_code=(tpl.code if tpl else "checkup_abnormal_mini"),
            channel=(tpl.channel if tpl else "mini_subscribe"),
            delivery_status="sent",
            pushed_at=now,
        )
        db.add(log)
        sent += 1

    await db.flush()
    return {"guardians": list(guardians), "sent": sent, "deduped": False, "title": title, "content": content}


async def list_alert_logs_for_user(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """当前用户作为守护者收到的推送列表。"""
    from sqlalchemy import func
    total_q = await db.execute(
        select(func.count(FamilyAlertLog.id)).where(FamilyAlertLog.guardian_user_id == user_id)
    )
    total = total_q.scalar() or 0
    rows = await db.execute(
        select(FamilyAlertLog)
        .where(FamilyAlertLog.guardian_user_id == user_id)
        .order_by(FamilyAlertLog.pushed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for log in rows.scalars():
        items.append({
            "id": log.id,
            "member_id": log.member_id,
            "report_id": log.report_id,
            "severity": log.severity,
            "abnormal_count": log.abnormal_count,
            "channel": log.channel,
            "delivery_status": log.delivery_status,
            "pushed_at": log.pushed_at.isoformat() if log.pushed_at else None,
            "clicked_at": log.clicked_at.isoformat() if log.clicked_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
