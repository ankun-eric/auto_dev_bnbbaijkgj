"""[BUGFIX-FAMILY-STATUS-ROOT-CAUSE-V2 2026-06-03] FamilyMember.status 治本回滚工具

背景：
    之前 4 类事件（邀请过期 / 邀请拒绝 / 邀请取消 / 守护取消）只更新了
    FamilyInvitation 或 FamilyManagement 单边业务表，没有同步把
    FamilyMember.status 改回 unbound，导致库里产生大量"假 bound"脏数据。

治本承诺：
    本模块提供 4 个原子事件方法，调用方必须把"业务表写入" + "回滚 FamilyMember"
    包在【同一个事务】内，保证两表要么一起成功要么一起回滚。

注意：
    本模块只负责【组装 FamilyMember 的目标 status/sub_status 并 add 到 session】，
    真正的事务提交/回滚由调用方控制（一般是 db.commit() 或 with db.begin()）。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import FamilyInvitation, FamilyMember


# ─────────────── 4 类事件 × 对应的目标 sub_status ───────────────

EVENT_INVITATION_EXPIRED = "invited_expired"   # 邀请超过 24h 自动过期
EVENT_INVITATION_REJECTED = "rejected"         # 对方拒绝邀请
EVENT_INVITATION_CANCELLED = "unbinded"        # 邀请人主动取消邀请
EVENT_MANAGEMENT_CANCELLED = "unbinded"        # 守护关系被取消（任一方发起）


async def _resolve_member_from_invitation(
    db: AsyncSession,
    invitation: FamilyInvitation,
) -> Optional[FamilyMember]:
    """从一条邀请记录反查对应的 FamilyMember 卡片。

    优先用 invitation.member_id；若为空（历史数据），用
    (inviter_user_id, invited_user_id/phone) 兜底反查（保守跳过，避免误伤）。
    """
    if invitation.member_id:
        res = await db.execute(
            select(FamilyMember).where(FamilyMember.id == invitation.member_id)
        )
        return res.scalars().first()
    return None


async def rollback_member_for_invitation_event(
    db: AsyncSession,
    invitation: FamilyInvitation,
    event_sub_status: str,
) -> Optional[FamilyMember]:
    """邀请类事件触发后，同步把对应 FamilyMember 回滚为 unbound。

    使用约束：
        必须与"修改 invitation.status"在【同一事务】内调用，调用方负责 commit。

    入参:
        invitation: 已经被业务代码改过 status 的 FamilyInvitation 对象
        event_sub_status: 'invited_expired' / 'rejected' / 'unbinded' 之一

    返回:
        被改动的 FamilyMember 对象（已 add 到 session）；
        若 invitation.member_id 为空或找不到，则返回 None（不阻断业务流）。

    规则:
        - 仅对"非本人 + 当前 status='bound'/'active'"的成员回滚；
        - 已经是 unbound/deleted 的成员不再变动（避免覆盖更准确的子状态）。
    """
    member = await _resolve_member_from_invitation(db, invitation)
    if member is None:
        return None
    if member.is_self:
        return None
    cur_main = (member.status or "").strip()
    if cur_main not in ("bound", "active"):
        return None

    member.status = "unbound"
    member.sub_status = event_sub_status
    db.add(member)
    return member


async def rollback_member_for_management_cancel(
    db: AsyncSession,
    *,
    manager_user_id: int,
    managed_member_id: Optional[int],
    sub_status_override: Optional[str] = None,
) -> Optional[FamilyMember]:
    """守护关系取消事件触发后，同步回滚对应 FamilyMember。

    使用约束:
        必须与"修改 FamilyManagement.status='cancelled'/'cancelled_by_target'"
        在【同一事务】内调用，调用方负责 commit。

    入参:
        manager_user_id: 守护人（卡片所有者 = FamilyMember.user_id）
        managed_member_id: 被守护成员的 FamilyMember.id
        sub_status_override: 可选，默认 'unbinded'；
                             被守护方主动退出场景调用方可传 'unbinded' 即可，
                             保持子状态语义一致。

    返回:
        被改动的 FamilyMember 对象；若找不到匹配成员或不需要变动，返回 None。

    规则:
        - 仅对"非本人 + 当前 status='bound'/'active'"的成员回滚；
        - 已经是 unbound/deleted 的成员不再变动。
    """
    if not managed_member_id:
        return None
    res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == managed_member_id,
            FamilyMember.user_id == manager_user_id,
        )
    )
    member = res.scalars().first()
    if member is None:
        return None
    if member.is_self:
        return None
    cur_main = (member.status or "").strip()
    if cur_main not in ("bound", "active"):
        return None

    member.status = "unbound"
    member.sub_status = sub_status_override or EVENT_MANAGEMENT_CANCELLED
    db.add(member)
    return member


__all__ = [
    "EVENT_INVITATION_EXPIRED",
    "EVENT_INVITATION_REJECTED",
    "EVENT_INVITATION_CANCELLED",
    "EVENT_MANAGEMENT_CANCELLED",
    "rollback_member_for_invitation_event",
    "rollback_member_for_management_cancel",
]
