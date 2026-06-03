"""[PRD-FAMILY-V3-STATE-MODEL-V1 2026-06-03] V3 终版 — 家庭成员主+子状态聚合模块

PRD 第 1.1 节锁定决策：
- 主状态枚举：unbound / bound / deleted
- 子状态枚举：not_applied / applying / rejected / unbinded / invited_expired
            / bound / self_deleted / admin_deleted

本模块在不强制改 schema（兼容期 30 天）的前提下,基于现有 FamilyMember.status
+ FamilyManagement / FamilyInvitation 推导出 V3 主+子状态,供前端在「老人 Tab」
渲染 Hero 卡片 + 「他的守护人」卡片视图时使用。

迁移路径：
1. 当前阶段（阶段 1）：本服务为只读推导器,旧 status 字段仍是真值来源
2. 后续阶段：family_members 表加 main_status/sub_status 列后,本服务会做双写读
3. 30 天后：旧 status 字段下线,本服务直接读新列
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
    # 配套展示字段
    can_reinvite: bool      # 是否可显示"重新邀请"按钮(状态非 bound/applying)
    can_edit: bool          # 是否可显示"编辑"按钮(非 deleted)
    show_simplified_view: bool  # 解绑后是否进入极简视图(只剩 Hero+他的守护人卡片)


# ─────────────── 主推导函数 ───────────────

async def derive_v3_state(
    db: AsyncSession,
    *,
    member: FamilyMember,
    now: Optional[datetime] = None,
) -> V3StateInfo:
    """根据 family_members + family_management + family_invitations 推导 V3 主+子状态。

    输入：单个 member 实体(已含 user_id, status, member_user_id 等字段)
    输出：V3StateInfo
    """
    if now is None:
        now = datetime.utcnow()

    # 0. 本人卡片不参与 V3 状态机(直接给一个特殊 sentinel)
    if member.is_self:
        return V3StateInfo(
            main_status="bound",
            sub_status="bound",
            can_reinvite=False,
            can_edit=True,
            show_simplified_view=False,
        )

    # 1. 旧 status 软删除映射
    if member.status in ("deleted", "removed"):
        return V3StateInfo(
            main_status="deleted",
            sub_status="self_deleted",
            can_reinvite=True,         # PRD 决策点 17: deleted 卡片仍可重新邀请
            can_edit=False,
            show_simplified_view=True,
        )

    # 2. 检查是否有 active 守护关系(=> bound/bound)
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

    # 3. 检查是否有已 cancelled 的守护关系(=> unbound/unbinded)
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
            show_simplified_view=True,  # 解绑后进入极简视图
        )

    # 4. 检查邀请状态
    inv_q = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.inviter_user_id == member.user_id,
            FamilyInvitation.member_id == member.id,
        ).order_by(FamilyInvitation.created_at.desc())
    )
    invitations = list(inv_q.scalars().all())
    latest_pending = None
    has_rejected = False
    has_expired = False
    for inv in invitations:
        if inv.status == "pending":
            if inv.expires_at and inv.expires_at > now:
                latest_pending = inv
                break
            else:
                has_expired = True
        elif inv.status == "rejected":
            has_rejected = True
        elif inv.status == "expired":
            has_expired = True

    if latest_pending:
        return V3StateInfo(
            main_status="unbound",
            sub_status="applying",
            can_reinvite=False,
            can_edit=True,
            show_simplified_view=False,
        )
    if has_rejected:
        return V3StateInfo(
            main_status="unbound",
            sub_status="rejected",
            can_reinvite=True,
            can_edit=True,
            show_simplified_view=False,
        )
    if has_expired:
        return V3StateInfo(
            main_status="unbound",
            sub_status="invited_expired",
            can_reinvite=True,
            can_edit=True,
            show_simplified_view=False,
        )

    # 5. 一切皆无 => 未发起过申请
    return V3StateInfo(
        main_status="unbound",
        sub_status="not_applied",
        can_reinvite=True,
        can_edit=True,
        show_simplified_view=False,
    )


__all__ = ["V3StateInfo", "MainStatus", "SubStatus", "derive_v3_state"]
