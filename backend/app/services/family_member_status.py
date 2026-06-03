"""[PRD-FAMILY-V3-STATUS-INPLACE-UPGRADE 2026-06-03] V3 终版 — 家庭成员主+子状态聚合模块

升级说明：
- V1 阶段(应急修复)：本服务为"只读推导器"，基于老 status 字段实时算 V3 主+子状态
- V2 阶段(当前)：family_members 表已原地升级，status 直接存 bound/unbound/deleted，
  sub_status 直接存 8 种子状态。本模块改为"直接读库 + 邀请过期兜底"。

返回的 V3StateInfo 字段含义：
- main_status: bound / unbound / deleted
- sub_status:  bound / not_applied / applying / rejected / unbinded
              / invited_expired / self_deleted / admin_deleted
- can_reinvite:        是否可显示「重新邀请」按钮
- can_edit:            是否可显示「编辑」按钮
- show_simplified_view: 是否进入解绑后极简视图(只剩 Hero+他的守护人卡片)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import FamilyInvitation, FamilyManagement, FamilyMember

# ─────────────── V3 状态枚举 ───────────────

MainStatus = Literal["unbound", "bound", "deleted"]
SubStatus = Literal[
    "not_applied",       # 还没发出邀请
    "applying",          # 邀请中,24h 倒计时
    "rejected",          # 对方拒绝
    "unbinded",          # 已解绑（双方任一发起）
    "invited_expired",   # 邀请 24h 未响应自动过期
    "bound",             # 已绑定
    "self_deleted",      # 守护人主动删除卡片
    "admin_deleted",     # 后台管理员删除
]


class V3StateInfo(TypedDict):
    main_status: MainStatus
    sub_status: SubStatus
    can_reinvite: bool
    can_edit: bool
    show_simplified_view: bool


# ─────────────── 主状态读取 ───────────────

# 老枚举到新枚举的兜底映射(防止迁移期残留)
_LEGACY_STATUS_MAP = {
    "active": ("bound", "bound"),
    "removed": ("deleted", "self_deleted"),
}


def _normalize_status(member: FamilyMember) -> tuple[str, str]:
    """把成员状态归一化到 V3 新枚举(兼容老数据)。"""
    raw_main = (member.status or "bound").strip()
    raw_sub = (getattr(member, "sub_status", None) or "").strip()

    if raw_main in _LEGACY_STATUS_MAP:
        main, default_sub = _LEGACY_STATUS_MAP[raw_main]
        return main, (raw_sub or default_sub)

    if raw_main == "deleted":
        return "deleted", (raw_sub or "self_deleted")
    if raw_main == "unbound":
        return "unbound", (raw_sub or "unbinded")
    if raw_main == "bound":
        return "bound", (raw_sub or "bound")

    # 兜底:未知值当 bound
    return "bound", (raw_sub or "bound")


async def derive_v3_state(
    db: AsyncSession,
    *,
    member: FamilyMember,
    now: Optional[datetime] = None,
) -> V3StateInfo:
    """根据 family_members.status/sub_status(治本后真值)推导 V3 状态。

    特殊兜底:
    - 本人卡片永远 bound/bound
    - 当 main_status='bound' 且数据库里没有 active 守护关系时,
      实时探测邀请记录,可能上浮 applying / rejected / invited_expired
      (这是 cron 没跑到的兜底,保证视图层不出错)
    """
    if now is None:
        now = datetime.utcnow()

    # 0. 本人卡片
    if member.is_self:
        return V3StateInfo(
            main_status="bound",
            sub_status="bound",
            can_reinvite=False,
            can_edit=True,
            show_simplified_view=False,
        )

    main, sub = _normalize_status(member)

    # 1. deleted 主状态:直接定型,进入极简视图
    if main == "deleted":
        return V3StateInfo(
            main_status="deleted",
            sub_status=sub if sub in ("self_deleted", "admin_deleted") else "self_deleted",
            can_reinvite=True,          # PRD 决策点 17: deleted 卡片仍可重新邀请
            can_edit=False,
            show_simplified_view=True,
        )

    # 2. unbound 主状态:已解绑,进入极简视图
    if main == "unbound":
        # 实时探测邀请是否在进行中(unbound 的子状态可能从 unbinded 升级为 applying)
        live_sub = await _probe_invitation_substatus(db, member=member, now=now)
        if live_sub:
            return V3StateInfo(
                main_status="unbound",
                sub_status=live_sub,
                can_reinvite=(live_sub != "applying"),
                can_edit=True,
                show_simplified_view=(live_sub == "unbinded"),
            )
        return V3StateInfo(
            main_status="unbound",
            sub_status=sub if sub in (
                "not_applied", "applying", "rejected",
                "unbinded", "invited_expired",
            ) else "unbinded",
            can_reinvite=(sub != "applying"),
            can_edit=True,
            show_simplified_view=(sub == "unbinded"),
        )

    # 3. bound 主状态:校验 active 守护关系是否真的存在(应急兜底)
    active_mgmt = (await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == member.user_id,
            FamilyManagement.managed_member_id == member.id,
            FamilyManagement.status == "active",
        )
    )).scalars().first()
    if active_mgmt:
        return V3StateInfo(
            main_status="bound",
            sub_status="bound",
            can_reinvite=False,
            can_edit=True,
            show_simplified_view=False,
        )

    # 4. 标记为 bound 但实际无 active 守护关系:进入容错推导
    #    - 探测到邀请记录   → 用邀请态(applying / rejected / invited_expired)
    #    - 探测到 cancelled 关系 → unbinded
    #    - 都没有           → not_applied(全新卡片,还没发过邀请)
    live_sub = await _probe_invitation_substatus(db, member=member, now=now)
    if live_sub:
        return V3StateInfo(
            main_status="unbound",
            sub_status=live_sub,
            can_reinvite=(live_sub != "applying"),
            can_edit=True,
            show_simplified_view=(live_sub == "unbinded"),
        )
    cancelled_mgmt = (await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == member.user_id,
            FamilyManagement.managed_member_id == member.id,
            FamilyManagement.status.in_(("cancelled", "removed", "cancelled_by_target")),
        )
    )).scalars().first()
    if cancelled_mgmt:
        return V3StateInfo(
            main_status="unbound",
            sub_status="unbinded",
            can_reinvite=True,
            can_edit=True,
            show_simplified_view=True,
        )
    return V3StateInfo(
        main_status="unbound",
        sub_status="not_applied",
        can_reinvite=True,
        can_edit=True,
        show_simplified_view=False,
    )


async def _probe_invitation_substatus(
    db: AsyncSession,
    *,
    member: FamilyMember,
    now: datetime,
) -> Optional[SubStatus]:
    """实时探测邀请态:applying / rejected / invited_expired / not_applied。
    返回 None 表示没有任何邀请记录。"""
    inv_q = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.inviter_user_id == member.user_id,
            FamilyInvitation.member_id == member.id,
        ).order_by(FamilyInvitation.created_at.desc())
    )
    invitations = list(inv_q.scalars().all())
    if not invitations:
        return None

    has_rejected = False
    has_expired = False
    for inv in invitations:
        if inv.status == "pending":
            if inv.expires_at and inv.expires_at > now:
                return "applying"
            has_expired = True
        elif inv.status == "rejected":
            has_rejected = True
        elif inv.status == "expired":
            has_expired = True

    if has_rejected:
        return "rejected"
    if has_expired:
        return "invited_expired"
    return "not_applied"


__all__ = ["V3StateInfo", "MainStatus", "SubStatus", "derive_v3_state"]
