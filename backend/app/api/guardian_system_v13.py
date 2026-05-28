"""[守护人体系 PRD v1.3 / v1.3.1 2026-05-27] 健康档案融合优化 + 统一列表与已绑定/未绑定重构

v1.3.1 关键变更（在 v1.3 基础上做结构性修订）：
- 取消两 Tab（守护中 / 待守护），整页一个大列表 + 两区色块卡组（已绑定 / 未绑定）
- 新增 bind_status (bound / unbound) 字段（v1.3 status: active/not_active 的语义升级，并保留兼容）
- max_guardians 从 membership_plans.max_managed / free_member_quota.max_managed 动态读取（不再写死 10）
- 配额公式：本人豁免；已绑定 + 孤儿 + 邀请中 + 尚未邀请 占名额；暂未响应 / 已解绑 / 已过期 不占名额
- 用户可见层术语清理：禁用 "共管 / 代管 / 已拒绝"，柔化为 "建立于 / 由我代为管理 / 暂未响应"
- 新增 display_substatus_label 字段，前端可直接渲染柔化后的文案
- 列表统一按 created_at ASC 正序（老朋友先）

v1.3 关键变更：
- 信息架构极简：仅保留 守护中 / 待守护 两态 Tab
- 解耦数据模型：邀请生命周期独立字段 invite_lifecycle (never_invited/inviting/accepted/rejected/unbound/expired)
- 强化权限边界：普通守护人对被守护人全只读，所有写操作仅主守护人可执行
- 统一扣费心智：先本人 → 后主代付（默认开关 ON）
- 新增接口：
  · GET  /api/guardian/v13/family/list            列表带 invite_lifecycle / bind_status (v1.3.1)
  · GET  /api/guardian/v13/family/invite-history  邀请记录（被守护人行，单向）
  · POST /api/guardian/v13/family/proxy-pay/toggle 切换 AI 呼叫代付
  · GET  /api/guardian/v13/family/proxy-pay/detail 代付明细
  · POST /api/guardian/v13/family/invite/cancel    取消邀请
  · POST /api/guardian/v13/family/remove           移除被守护人卡片（4 不可删校验）

[PRD-GUARDIAN-V1.3 2026-05-26][PRD-GUARDIAN-V1.3.1 2026-05-27]
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.membership_plan import MembershipPlan, UserMembershipSub
from app.models.models import (
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    GuardianAlertQuotaUsage,
    GuardianProxyPay,
    ManagementOperationLog,
    Notification,
    NotificationType,
    SystemMessage,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guardian/v13", tags=["守护人体系-v1.3"])

# 默认守护人上限（含已守护 + 邀请中）
DEFAULT_MAX_GUARDIANS = 10

# 邀请生命周期常量
LIFECYCLE_NEVER_INVITED = "never_invited"
LIFECYCLE_INVITING = "inviting"
LIFECYCLE_ACCEPTED = "accepted"
LIFECYCLE_REJECTED = "rejected"
LIFECYCLE_UNBOUND = "unbound"
LIFECYCLE_EXPIRED = "expired"

# 邀请有效期 24 小时
INVITE_LIFECYCLE_HOURS = 24


# ─────────── Schemas ───────────


class FamilyListItemV13(BaseModel):
    """v1.3 / v1.3.1 我守护的人列表项"""
    management_id: Optional[int] = None
    manager_user_id: int
    managed_user_id: Optional[int] = None
    managed_member_id: Optional[int] = None
    managed_user_nickname: Optional[str] = None
    relation_label: Optional[str] = None
    role_badge: str = "normal"
    is_primary_guardian: bool = False
    priority_order: int = 100
    # v1.3 字段（保留向前兼容）
    status: str = "not_active"  # active / not_active
    invite_lifecycle: str = LIFECYCLE_NEVER_INVITED
    # [v1.3.1] 新增字段
    bind_status: str = "unbound"  # bound / unbound
    display_substatus_label: str = ""  # 用户可见层柔化文案：建立于 / 邀请中 / 暂未响应 / 已解绑 / 已过期 / 尚未邀请 / 由我代为管理
    is_orphan: bool = False  # 是否为孤儿档案（managed_user_id 为空但 managed_member_id 存在）
    occupies_quota: bool = False  # 是否占用配额（用于前端高亮）
    invite_code: Optional[str] = None
    invite_expires_at: Optional[str] = None
    invite_remaining_hours: Optional[int] = None
    proxy_pay_enabled: bool = False
    has_bound_device: bool = False
    has_active_med_plan: bool = False
    can_remove: bool = False
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# [v1.3.1] 用户可见层术语映射（柔化）：禁用"共管 / 代管 / 已拒绝"
_LIFECYCLE_DISPLAY_LABEL: dict = {
    LIFECYCLE_ACCEPTED: "建立于",
    LIFECYCLE_INVITING: "邀请中",
    LIFECYCLE_REJECTED: "暂未响应",
    LIFECYCLE_UNBOUND: "已解绑",
    LIFECYCLE_EXPIRED: "已过期",
    LIFECYCLE_NEVER_INVITED: "尚未邀请",
}

# [v1.3.1] 占名额口径：
# [BUGFIX-MY-PROFILE-4ITEMS-20260528 修复 3] 仅 bound + inviting（pending 且未过期）占额；
# 已过期/已失效/未响应/未邀请 → 不占额。
# 已绑定/accepted、邀请中 → 占名额
# 暂未响应/rejected、已解绑/unbound、已过期/expired、尚未邀请/never_invited → 不占名额
_OCCUPY_QUOTA_LIFECYCLES = {
    LIFECYCLE_ACCEPTED,
    LIFECYCLE_INVITING,
}


class ProxyPayToggleRequest(BaseModel):
    managed_user_id: int
    enabled: bool


class CancelInviteRequest(BaseModel):
    invite_code: Optional[str] = None
    invitation_id: Optional[int] = None


class RemoveFamilyRequest(BaseModel):
    """移除被守护人卡片"""
    managed_user_id: Optional[int] = None
    managed_member_id: Optional[int] = None
    invitation_id: Optional[int] = None


# ─────────── 工具 ───────────


async def _is_paid_member(db: AsyncSession, user_id: int) -> bool:
    now = datetime.utcnow()
    res = await db.execute(
        select(UserMembershipSub).where(
            UserMembershipSub.user_id == user_id,
            UserMembershipSub.status == "active",
            UserMembershipSub.expire_at > now,
        )
    )
    return res.scalars().first() is not None


async def _get_max_guardians(db: AsyncSession, user_id: int) -> int:
    """[v1.3.1] 获取当前用户可守护人数上限。

    动态读取规则：
    - 会员用户：从 membership_plans.max_managed 取
    - 普通用户（无会员）：从 free_member_quota.max_managed 取
    - 都没有：fallback 到 DEFAULT_MAX_GUARDIANS
    """
    now = datetime.utcnow()
    sub = (await db.execute(
        select(UserMembershipSub).where(
            UserMembershipSub.user_id == user_id,
            UserMembershipSub.status == "active",
            UserMembershipSub.expire_at > now,
        ).order_by(UserMembershipSub.expire_at.desc())
    )).scalars().first()
    if sub:
        plan = await db.get(MembershipPlan, sub.plan_id)
        if plan and getattr(plan, "max_managed", None):
            return int(plan.max_managed or DEFAULT_MAX_GUARDIANS)

    # [v1.3.1] 无会员时读 free_member_quota.max_managed
    try:
        from app.models.membership_plan import FreeMemberQuota  # type: ignore
        quota = (await db.execute(
            select(FreeMemberQuota).order_by(FreeMemberQuota.id.asc())
        )).scalars().first()
        if quota and getattr(quota, "max_managed", None):
            return int(quota.max_managed or DEFAULT_MAX_GUARDIANS)
    except Exception:
        pass
    return DEFAULT_MAX_GUARDIANS


async def _is_unlimited_guardians(db: AsyncSession, user_id: int) -> bool:
    """[BUGFIX-MY-GUARDIAN-CARD-20260528] 判断当前用户是否为"超级 VIP/无上限"等级。

    判定口径：当前生效会员套餐的 `max_managed` 大于等于 9999（按业务约定），
    或套餐 code/name 含 'super_vip' 等关键字 → 视为无上限。
    """
    now = datetime.utcnow()
    sub = (await db.execute(
        select(UserMembershipSub).where(
            UserMembershipSub.user_id == user_id,
            UserMembershipSub.status == "active",
            UserMembershipSub.expire_at > now,
        ).order_by(UserMembershipSub.expire_at.desc())
    )).scalars().first()
    if not sub:
        return False
    plan = await db.get(MembershipPlan, sub.plan_id)
    if not plan:
        return False
    mm = int(getattr(plan, "max_managed", 0) or 0)
    if mm >= 9999:
        return True
    code = (getattr(plan, "code", "") or "").lower()
    name = (getattr(plan, "name", "") or "").lower()
    if "super" in code or "super" in name or "无上限" in (getattr(plan, "name", "") or ""):
        return True
    return False


async def _calc_archive_record_total(
    db: AsyncSession,
    *,
    manager_user_id: int,
    items: list[dict],
) -> int:
    """[BUGFIX-MY-GUARDIAN-CARD-20260528] 计算"我守护对象（不含本人）"的档案记录条数总和。

    口径（按用户需求）：
    - 已绑定家人（managed_user_id 存在且非本人）：按 user_id 维度统计 medical_records 中未删除的条数
    - 已绑定但只有 managed_member_id（孤儿档案）：按 member_id 维度统计
    - 未绑定（邀请中、未注册、暂未响应等）：按用户口径每人占位 1 条计入
    """
    try:
        from app.models.health_archive_v5 import MedicalRecord  # type: ignore
    except Exception:
        MedicalRecord = None  # type: ignore

    total = 0
    for it in items:
        managed_uid = it.get("managed_user_id")
        managed_mid = it.get("managed_member_id")
        bind_status = it.get("bind_status")

        # 跳过本人卡片（本接口列表本就不含本人，但仍兜底过滤）
        if managed_uid and managed_uid == manager_user_id:
            continue

        if bind_status == "bound" and (managed_uid or managed_mid) and MedicalRecord is not None:
            try:
                if managed_uid:
                    cnt_res = await db.execute(
                        select(func.count(MedicalRecord.id)).where(
                            MedicalRecord.user_id == managed_uid,
                            MedicalRecord.is_deleted == 0,
                        )
                    )
                else:
                    cnt_res = await db.execute(
                        select(func.count(MedicalRecord.id)).where(
                            MedicalRecord.member_id == managed_mid,
                            MedicalRecord.is_deleted == 0,
                        )
                    )
                cnt = int(cnt_res.scalar() or 0)
            except Exception:
                cnt = 0
            # 已绑定档案至少占位 1（即使该家人尚无医疗记录，也算 1 条主档案记录）
            total += max(cnt, 1)
        else:
            # 未绑定（邀请中/未注册/暂未响应/已解绑/已过期）按用户口径每人占位 1 条
            total += 1
    return total


async def _is_proxy_pay_enabled(db: AsyncSession, primary_uid: int, managed_uid: int) -> bool:
    """主代付开关默认 ON：无记录视为 ON；显式 disable 才关闭"""
    res = await db.execute(
        select(GuardianProxyPay).where(
            GuardianProxyPay.primary_guardian_user_id == primary_uid,
            GuardianProxyPay.managed_user_id == managed_uid,
        )
    )
    rec = res.scalars().first()
    if rec is None:
        # v1.3：默认 ON
        return True
    return bool(rec.enabled)


async def _has_bound_device(db: AsyncSession, managed_user_id: int) -> bool:
    """检查被守护人是否绑定了硬件设备"""
    try:
        from app.models.devices_v2 import UserDeviceBinding as _UD  # type: ignore
        UserDevice = _UD  # noqa: N806
    except Exception:
        try:
            from app.models.devices_v2 import Device as _UD2  # type: ignore
            UserDevice = _UD2  # noqa: N806
        except Exception:
            return False
    try:
        # 取通用 user_id 字段
        user_field = getattr(UserDevice, "user_id", None) or getattr(UserDevice, "owner_user_id", None)
        if user_field is None:
            return False
        res = await db.execute(
            select(func.count(UserDevice.id)).where(user_field == managed_user_id)
        )
        return int(res.scalar() or 0) > 0
    except Exception:
        return False


async def _has_active_med_plan(db: AsyncSession, managed_user_id: int) -> bool:
    """检查被守护人是否存在在途服药计划"""
    try:
        from app.models.models import MedicationPlan  # type: ignore
    except Exception:
        return False
    try:
        res = await db.execute(
            select(func.count(MedicationPlan.id)).where(
                MedicationPlan.user_id == managed_user_id,
                MedicationPlan.enabled == True,
            )
        )
        return int(res.scalar() or 0) > 0
    except Exception:
        return False


def _calc_invite_lifecycle(inv: FamilyInvitation, now: datetime) -> str:
    """根据邀请记录推导生命周期状态"""
    if not inv:
        return LIFECYCLE_NEVER_INVITED
    s = (inv.status or "").lower()
    if s == "accepted":
        return LIFECYCLE_ACCEPTED
    if s == "rejected":
        return LIFECYCLE_REJECTED
    if s == "cancelled":
        return LIFECYCLE_UNBOUND
    if s == "expired":
        return LIFECYCLE_EXPIRED
    if s == "pending":
        if inv.expires_at and inv.expires_at < now:
            return LIFECYCLE_EXPIRED
        return LIFECYCLE_INVITING
    return LIFECYCLE_NEVER_INVITED


async def assert_can_write_managed(
    db: AsyncSession, current_user_id: int, managed_user_id: int
) -> None:
    """v1.3 权限校验：仅主守护人或本人可对被守护人执行写操作"""
    if current_user_id == managed_user_id:
        return
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user_id,
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
            FamilyManagement.is_primary_guardian == True,
        )
    )
    if not res.scalars().first():
        raise HTTPException(status_code=403, detail="仅主守护人可执行此操作")


# ─────────── 接口 ───────────


@router.get("/family/list")
async def list_family_v13(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.3 §2.1 + PRD-GUARDIAN-V1.3.1 §1/§2/§5.1] 我守护的人列表。

    v1.3.1 关键变更：
    - 取消两 Tab，整页一个大列表（前端按 bind_status 分两区色块卡组渲染）
    - 列表统一按 created_at ASC 正序（老朋友先）
    - 新增字段：bind_status / display_substatus_label / occupies_quota / is_orphan
    - 配额公式：本人豁免；已绑定/孤儿/邀请中/尚未邀请 占名额；暂未响应/已解绑/已过期 不占名额
    - max_guardians 从 membership_plans / free_member_quota 动态读取

    返回字段：
    - items: List[FamilyListItemV13]，按 created_at ASC 排序
    - tab_active_count / tab_pending_count: 保留向前兼容
    - bound_count / unbound_count / quota_used: v1.3.1 新增
    - max_guardians / used / can_invite_count: 配额信息
    """
    now = datetime.utcnow()

    # 1) 拉取已建立关系（active + 历史 inactive/cancelled）
    mgmt_res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
        ).order_by(FamilyManagement.created_at.asc())
    )
    mgmts = mgmt_res.scalars().all()

    # 2) 拉取邀请记录（用于关联 invite_lifecycle）
    inv_res = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.inviter_user_id == current_user.id,
        ).order_by(FamilyInvitation.created_at.desc())
    )
    invitations = inv_res.scalars().all()

    # 自动过期：pending 且超过 24h 的标为 expired
    for inv in invitations:
        if inv.status == "pending" and inv.expires_at and inv.expires_at < now:
            inv.status = "expired"
    await db.flush()

    # 索引：member_id → 最新邀请
    invs_by_member: dict[int, FamilyInvitation] = {}
    invs_by_member_none: list[FamilyInvitation] = []
    for inv in invitations:
        if inv.member_id:
            if inv.member_id not in invs_by_member:
                invs_by_member[inv.member_id] = inv
        else:
            invs_by_member_none.append(inv)

    items: list[dict] = []
    seen_keys: set[str] = set()

    # 处理已有 FamilyManagement 记录
    for mgmt in mgmts:
        managed_user = await db.get(User, mgmt.managed_user_id) if mgmt.managed_user_id else None
        relation_label = None
        member = None
        if mgmt.managed_member_id:
            member = await db.get(FamilyMember, mgmt.managed_member_id)
            if member:
                relation_label = getattr(member, "relation_type_name", None) or getattr(member, "relationship_type", None)

        is_primary = bool(getattr(mgmt, "is_primary_guardian", False))
        status_v13 = "active" if mgmt.status == "active" else "not_active"

        # 推导生命周期：active=accepted；其他根据状态
        if status_v13 == "active":
            lifecycle = LIFECYCLE_ACCEPTED
        else:
            # 历史已解绑/未激活
            lifecycle = LIFECYCLE_UNBOUND if mgmt.status in ("cancelled", "inactive") else LIFECYCLE_NEVER_INVITED

        # 查找最近一次相关邀请（如果有）
        latest_inv = invs_by_member.get(mgmt.managed_member_id) if mgmt.managed_member_id else None
        if latest_inv:
            inv_lc = _calc_invite_lifecycle(latest_inv, now)
            if status_v13 != "active" and inv_lc != LIFECYCLE_ACCEPTED:
                lifecycle = inv_lc

        proxy_pay = False
        if is_primary and status_v13 == "active":
            proxy_pay = await _is_proxy_pay_enabled(db, current_user.id, mgmt.managed_user_id)

        has_device = await _has_bound_device(db, mgmt.managed_user_id) if mgmt.managed_user_id else False
        has_med = await _has_active_med_plan(db, mgmt.managed_user_id) if mgmt.managed_user_id else False

        # 4 项不可删校验
        can_remove = (
            status_v13 != "active"  # 1. 不能为 active
            and not has_device      # 2. 没绑定设备
            and lifecycle != LIFECYCLE_INVITING  # 3. 非邀请中
            and not has_med         # 4. 无在途服药计划
        )

        invite_code = None
        invite_expires = None
        remaining_hours = None
        if lifecycle == LIFECYCLE_INVITING and latest_inv:
            invite_code = latest_inv.invite_code
            invite_expires = latest_inv.expires_at.isoformat() if latest_inv.expires_at else None
            if latest_inv.expires_at:
                delta = latest_inv.expires_at - now
                remaining_hours = max(0, int(delta.total_seconds() // 3600))

        key = f"mgmt:{mgmt.id}"
        seen_keys.add(key)

        # [v1.3.1] bind_status / display_substatus_label / is_orphan / occupies_quota
        is_orphan = bool(mgmt.managed_member_id and not mgmt.managed_user_id)
        bind_status = "bound" if status_v13 == "active" else "unbound"
        if is_orphan and bind_status == "bound":
            display_label = "由我代为管理"
        else:
            display_label = _LIFECYCLE_DISPLAY_LABEL.get(lifecycle, "")
        occupies_quota = (
            (bind_status == "bound") or (lifecycle in _OCCUPY_QUOTA_LIFECYCLES)
        )

        items.append(FamilyListItemV13(
            management_id=mgmt.id,
            manager_user_id=mgmt.manager_user_id,
            managed_user_id=mgmt.managed_user_id,
            managed_member_id=mgmt.managed_member_id,
            managed_user_nickname=(managed_user.nickname if managed_user else None) or (member.nickname if member else None),
            relation_label=relation_label,
            role_badge="primary" if is_primary else "normal",
            is_primary_guardian=is_primary,
            priority_order=int(getattr(mgmt, "priority_order", 100) or 100),
            status=status_v13,
            invite_lifecycle=lifecycle,
            bind_status=bind_status,
            display_substatus_label=display_label,
            is_orphan=is_orphan,
            occupies_quota=occupies_quota,
            invite_code=invite_code,
            invite_expires_at=invite_expires,
            invite_remaining_hours=remaining_hours,
            proxy_pay_enabled=proxy_pay,
            has_bound_device=has_device,
            has_active_med_plan=has_med,
            can_remove=can_remove,
            created_at=mgmt.created_at.isoformat() if mgmt.created_at else None,
        ).model_dump())

    # [BUGFIX-MY-GUARDIAN-CARD-2-20260528] 第 5 点兼容层兜底：
    # 查询当前用户名下、没有任何 FamilyManagement 记录的孤儿 FamilyMember，
    # 让外部"我的家人"Tab 建档后，「我守护的人」也能立即看到。
    try:
        # 已记录过的 member_id（出现在 mgmt 表中即视为已处理）
        seen_member_ids: set[int] = set()
        for mgmt in mgmts:
            if mgmt.managed_member_id:
                seen_member_ids.add(int(mgmt.managed_member_id))

        orphan_q = select(FamilyMember).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status == "active",
            FamilyMember.is_self == False,
        )
        if seen_member_ids:
            orphan_q = orphan_q.where(~FamilyMember.id.in_(seen_member_ids))
        orphan_members = (await db.execute(orphan_q.order_by(FamilyMember.created_at.asc()))).scalars().all()

        for mb in orphan_members:
            # 关联的最新邀请（如果有）
            latest_inv = invs_by_member.get(mb.id)
            if latest_inv:
                lifecycle = _calc_invite_lifecycle(latest_inv, now)
            else:
                lifecycle = LIFECYCLE_NEVER_INVITED

            invite_code_v = None
            invite_expires = None
            remaining_hours = None
            if lifecycle == LIFECYCLE_INVITING and latest_inv:
                invite_code_v = latest_inv.invite_code
                invite_expires = latest_inv.expires_at.isoformat() if latest_inv.expires_at else None
                if latest_inv.expires_at:
                    delta = latest_inv.expires_at - now
                    remaining_hours = max(0, int(delta.total_seconds() // 3600))

            # 孤儿档案（user_id=None）总是未绑定
            display_label = "由我代为管理" if lifecycle == LIFECYCLE_NEVER_INVITED else _LIFECYCLE_DISPLAY_LABEL.get(lifecycle, "")
            occupies_quota = lifecycle in _OCCUPY_QUOTA_LIFECYCLES

            relation_label = getattr(mb, "relationship_type", None)

            items.append(FamilyListItemV13(
                management_id=None,
                manager_user_id=current_user.id,
                managed_user_id=None,
                managed_member_id=mb.id,
                managed_user_nickname=mb.nickname,
                relation_label=relation_label,
                role_badge="normal",
                is_primary_guardian=False,
                priority_order=100,
                status="not_active",
                invite_lifecycle=lifecycle,
                bind_status="unbound",
                display_substatus_label=display_label,
                is_orphan=True,
                occupies_quota=occupies_quota,
                invite_code=invite_code_v,
                invite_expires_at=invite_expires,
                invite_remaining_hours=remaining_hours,
                proxy_pay_enabled=False,
                has_bound_device=False,
                has_active_med_plan=False,
                can_remove=True,
                created_at=mb.created_at.isoformat() if mb.created_at else None,
            ).model_dump())
    except Exception as _e:
        logger.warning("[guardian_v13] orphan family_member 兜底查询失败: %s", _e)

    # 处理"邀请阶段无 member_id"的纯邀请记录（PRD: 待守护-邀请中/已拒绝/已过期/未激活）
    for inv in invitations:
        if inv.member_id:
            continue
        lifecycle = _calc_invite_lifecycle(inv, now)
        # 已被消化为 mgmt 的略过（accepted → 应已 mgmt active）
        if lifecycle == LIFECYCLE_ACCEPTED:
            continue
        invite_code = inv.invite_code if lifecycle == LIFECYCLE_INVITING else None
        invite_expires = inv.expires_at.isoformat() if inv.expires_at and lifecycle == LIFECYCLE_INVITING else None
        remaining_hours = None
        if lifecycle == LIFECYCLE_INVITING and inv.expires_at:
            delta = inv.expires_at - now
            remaining_hours = max(0, int(delta.total_seconds() // 3600))
        # 待守护的卡片：管理员尚未指定具体 user
        # [v1.3.1] 计算 bind_status / display_substatus_label / occupies_quota
        bind_status_inv = "unbound"
        display_label_inv = _LIFECYCLE_DISPLAY_LABEL.get(lifecycle, "")
        occupies_quota_inv = lifecycle in _OCCUPY_QUOTA_LIFECYCLES
        items.append(FamilyListItemV13(
            management_id=None,
            manager_user_id=current_user.id,
            managed_user_id=None,
            managed_member_id=None,
            managed_user_nickname=None,
            relation_label=inv.relation_type,
            role_badge="normal",
            is_primary_guardian=False,
            priority_order=100,
            status="not_active",
            invite_lifecycle=lifecycle,
            bind_status=bind_status_inv,
            display_substatus_label=display_label_inv,
            is_orphan=False,
            occupies_quota=occupies_quota_inv,
            invite_code=invite_code,
            invite_expires_at=invite_expires,
            invite_remaining_hours=remaining_hours,
            proxy_pay_enabled=False,
            has_bound_device=False,
            has_active_med_plan=False,
            can_remove=lifecycle != LIFECYCLE_INVITING,
            created_at=inv.created_at.isoformat() if inv.created_at else None,
        ).model_dump())

    # [v1.3.1] 统一按 created_at ASC 正序（老朋友先）
    def _sort_key(it: dict):
        return it.get("created_at") or ""
    items.sort(key=_sort_key)

    # v1.3 兼容字段：守护中 / 待守护 Tab 计数
    active_count = sum(1 for it in items if it["status"] == "active")
    pending_count = sum(1 for it in items if it["status"] != "active")
    inviting_count = sum(1 for it in items if it["invite_lifecycle"] == LIFECYCLE_INVITING)

    # [v1.3.1] 已绑定 / 未绑定 区计数
    bound_count = sum(1 for it in items if it.get("bind_status") == "bound")
    unbound_count = sum(1 for it in items if it.get("bind_status") == "unbound")
    # [BUGFIX-MY-PROFILE-4ITEMS-20260528 修复 2] X = 已绑定的非本人档案数（方案 A，不含本人）
    # 本接口的 items 本身不含本人虚拟项，所有 bound 项均为"非本人"；保留显式 manager != managed 过滤兜底。
    bound_others_count = sum(
        1 for it in items
        if it.get("bind_status") == "bound"
        and it.get("managed_user_id") != current_user.id
    )
    # [v1.3.1] 占名额数：本人豁免（本接口不包含本人虚拟项，由前端拼接）
    quota_used = sum(1 for it in items if it.get("occupies_quota"))

    max_guardians = await _get_max_guardians(db, current_user.id)
    is_unlimited = await _is_unlimited_guardians(db, current_user.id)
    # [v1.3.1] used 改为 quota_used；can_invite_count 改为 max_guardians - quota_used
    used = quota_used
    if is_unlimited:
        # [BUGFIX-MY-GUARDIAN-CARD-20260528] 超级 VIP 无上限：can_invite_count 用 -1 表示
        can_invite_count = -1
    else:
        can_invite_count = max(0, max_guardians - quota_used)

    # [BUGFIX-MY-GUARDIAN-CARD-20260528] 计算档案记录总数（所有守护对象，不含本人）
    archive_record_total = await _calc_archive_record_total(
        db, manager_user_id=current_user.id, items=items
    )

    return {
        "items": items,
        "total": len(items),
        # v1.3 兼容字段
        "tab_active_count": active_count,
        "tab_pending_count": pending_count,
        "active_count": active_count,
        "inviting_count": inviting_count,
        # [v1.3.1] 新增字段
        "bound_count": bound_count,
        "unbound_count": unbound_count,
        "quota_used": quota_used,
        # [BUGFIX-MY-PROFILE-4ITEMS-20260528 修复 2] 已绑定非本人数（X 口径，不含本人）
        "bound_others_count": bound_others_count,
        # 配额
        "max_guardians": max_guardians,
        "used": used,
        "can_invite_count": can_invite_count,
        "is_paid_member": await _is_paid_member(db, current_user.id),
        # [BUGFIX-MY-GUARDIAN-CARD-20260528] 新增字段
        "is_unlimited": is_unlimited,
        "archive_record_total": archive_record_total,
        "guarded_count": quota_used,  # 别名，便于前端语义化使用
    }


@router.get("/family/invite-history")
async def invite_history_for_managed(
    managed_user_id: Optional[int] = Query(None, description="被守护人 user_id；不传则返回本人双向记录"),
    managed_member_id: Optional[int] = Query(None, description="被守护人 family_member_id（兼容未注册）"),
    relation_type: Optional[str] = Query(None, description="按关系筛选无 user_id 的邀请"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.3 §6.2] 邀请记录（被守护人行，单向）

    仅展示"我对该被守护人发起过的全部邀请"，时间倒序。
    """
    now = datetime.utcnow()

    # 自动过期
    pending_res = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.inviter_user_id == current_user.id,
            FamilyInvitation.status == "pending",
            FamilyInvitation.expires_at < now,
        )
    )
    for inv in pending_res.scalars().all():
        inv.status = "expired"
    await db.flush()

    base = select(FamilyInvitation).where(
        FamilyInvitation.inviter_user_id == current_user.id,
    )
    if managed_member_id:
        base = base.where(FamilyInvitation.member_id == managed_member_id)
    elif managed_user_id:
        # 通过 accepted_by 或 member.user_id 间接匹配
        base = base.where(
            or_(
                FamilyInvitation.accepted_by == managed_user_id,
                # member 关联
                FamilyInvitation.member_id.in_(
                    select(FamilyMember.id).where(
                        FamilyMember.user_id == current_user.id,
                    )
                )
            )
        )
    elif relation_type:
        base = base.where(FamilyInvitation.relation_type == relation_type)

    res = await db.execute(base.order_by(FamilyInvitation.created_at.desc()))
    invs = res.scalars().all()

    status_labels = {
        "pending": ("邀请中", "info"),
        "accepted": ("已同意", "success"),
        "rejected": ("已拒绝", "danger"),
        "expired": ("已过期", "warning"),
        "cancelled": ("已取消", "gray"),
    }
    items = []
    for inv in invs:
        s = inv.status or "pending"
        if s == "pending" and inv.expires_at and inv.expires_at < now:
            s = "expired"
        label, color = status_labels.get(s, (s, "gray"))
        qr_url = f"https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-auth?code={inv.invite_code}" if s == "pending" else None
        items.append({
            "id": inv.id,
            "invite_code": inv.invite_code,
            "relation_type": inv.relation_type,
            "member_id": inv.member_id,
            "status": s,
            "status_label": label,
            "status_color": color,
            "qr_url": qr_url,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        })

    return {
        "items": items,
        "total": len(items),
        "managed_user_id": managed_user_id,
        "managed_member_id": managed_member_id,
    }


@router.post("/family/proxy-pay/toggle")
async def toggle_proxy_pay(
    payload: ProxyPayToggleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.3 §7.2.3] 切换主代付开关（仅主守护人可调用）"""
    await assert_can_write_managed(db, current_user.id, payload.managed_user_id)

    res = await db.execute(
        select(GuardianProxyPay).where(
            GuardianProxyPay.primary_guardian_user_id == current_user.id,
            GuardianProxyPay.managed_user_id == payload.managed_user_id,
        )
    )
    rec = res.scalars().first()
    if not rec:
        rec = GuardianProxyPay(
            primary_guardian_user_id=current_user.id,
            managed_user_id=payload.managed_user_id,
            enabled=bool(payload.enabled),
        )
        db.add(rec)
    else:
        rec.enabled = bool(payload.enabled)
    await db.flush()

    return {
        "managed_user_id": payload.managed_user_id,
        "enabled": bool(payload.enabled),
        "message": "代付已开启" if payload.enabled else "代付已关闭",
    }


@router.get("/family/proxy-pay/detail")
async def proxy_pay_detail(
    managed_user_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.3 §7.2.5] 代付明细（今日/本月代付次数 + 列表）

    仅主守护人或本人可查看。
    """
    await assert_can_write_managed(db, current_user.id, managed_user_id)

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 代付明细：所有以 user_id=current_user.id（主） 但 managed_user_id=被守护人 的扣费记录
    res = await db.execute(
        select(GuardianAlertQuotaUsage).where(
            GuardianAlertQuotaUsage.user_id == current_user.id,
            GuardianAlertQuotaUsage.managed_user_id == managed_user_id,
            GuardianAlertQuotaUsage.used_at >= month_start,
        ).order_by(GuardianAlertQuotaUsage.used_at.desc())
    )
    records = res.scalars().all()

    today_count = sum(1 for r in records if r.used_at and r.used_at >= today_start)
    month_count = len(records)

    enabled = await _is_proxy_pay_enabled(db, current_user.id, managed_user_id)

    items = []
    type_label = {"alert": "紧急 SOS", "ai_remind": "AI 外呼提醒", "ai_call": "AI 呼叫"}
    for r in records[:100]:
        items.append({
            "id": r.id,
            "call_type": r.call_type,
            "call_type_label": type_label.get(r.call_type, r.call_type),
            "used_at": r.used_at.isoformat() if r.used_at else None,
            "managed_user_id": r.managed_user_id,
        })

    return {
        "managed_user_id": managed_user_id,
        "enabled": enabled,
        "today_count": today_count,
        "month_count": month_count,
        "items": items,
    }


@router.post("/family/invite/cancel")
async def cancel_invite(
    payload: CancelInviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.3 §3.2] 取消邀请（仅 inviting 状态可取消）"""
    inv = None
    if payload.invitation_id:
        inv = await db.get(FamilyInvitation, payload.invitation_id)
    elif payload.invite_code:
        res = await db.execute(
            select(FamilyInvitation).where(FamilyInvitation.invite_code == payload.invite_code)
        )
        inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=404, detail="邀请记录不存在")
    if inv.inviter_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能取消自己发起的邀请")
    if inv.status != "pending":
        raise HTTPException(status_code=400, detail=f"当前状态 {inv.status} 不可取消")
    inv.status = "cancelled"
    await db.flush()
    return {"invitation_id": inv.id, "status": "cancelled", "message": "邀请已取消"}


@router.post("/family/remove")
async def remove_family_card(
    payload: RemoveFamilyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.3 §4.3 + BUGFIX-MY-GUARDIAN-CARD-2-20260528] 移除被守护人卡片

    校验 4 项不可删规则（仅在记录"实际仍存在"时校验）：
    1) 关系=active 不可移除（v1.3.1 起已放开，等同先解除守护再清档）
    2) 已绑定硬件设备不可移除
    3) 邀请生命周期=inviting 不可移除
    4) 在途服药计划不可移除

    [BUGFIX-2 2026-05-28]：
    - 第 3、4 点：纯 managed_member（孤儿）/ 已过期 invitation 均可受理移除，
      不再向用户暴露 404；改为幂等返 200，前端按 deleted/should_refresh 字段刷新。
    """
    now = datetime.utcnow()
    deleted_any = False
    delete_types: list[str] = []

    # 分支 A：invitation 直接移除（含 pending/expired/cancelled/rejected）
    if payload.invitation_id:
        inv = await db.get(FamilyInvitation, payload.invitation_id)
        if inv and inv.inviter_user_id == current_user.id:
            # pending 且未过期 → 不允许（提示前端先取消）
            if inv.status == "pending" and inv.expires_at and inv.expires_at >= now:
                raise HTTPException(status_code=400, detail="邀请中状态不允许移除，请先取消邀请")
            # expired/cancelled/rejected/已自动过期的 pending → 软删（cancelled）
            if inv.status == "pending":
                inv.status = "expired"
            inv.status = "cancelled" if inv.status != "expired" else "expired"
            await db.flush()
            deleted_any = True
            delete_types.append("invitation")

    # 分支 B：纯 managed_member（孤儿 FamilyMember 无 FamilyManagement）移除
    if payload.managed_member_id:
        # 关联的 FamilyMember 是否存在
        fm = await db.get(FamilyMember, payload.managed_member_id)
        if fm and fm.user_id == current_user.id and fm.status == "active":
            # 查是否已有对应 FamilyManagement
            mgmt_check = (await db.execute(
                select(FamilyManagement).where(
                    FamilyManagement.manager_user_id == current_user.id,
                    FamilyManagement.managed_member_id == payload.managed_member_id,
                )
            )).scalars().first()
            if not mgmt_check:
                # 纯 FamilyMember 孤儿档案 → 软删 + 同步移除关联邀请
                fm.status = "deleted"
                # 同步移除关联的 invitation
                related_invs = (await db.execute(
                    select(FamilyInvitation).where(
                        FamilyInvitation.inviter_user_id == current_user.id,
                        FamilyInvitation.member_id == payload.managed_member_id,
                    )
                )).scalars().all()
                for r_inv in related_invs:
                    if r_inv.status == "pending":
                        r_inv.status = "cancelled"
                await db.flush()
                deleted_any = True
                delete_types.append("orphan_member")
                return {
                    "removed": True,
                    "deleted": True,
                    "should_refresh": True,
                    "type": "orphan_member",
                    "managed_member_id": payload.managed_member_id,
                    "message": "已移除",
                }

    # 分支 C：通过 managed_user_id / managed_member_id 找 FamilyManagement
    mgmt = None
    if payload.managed_user_id or payload.managed_member_id:
        q = select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
        )
        if payload.managed_user_id:
            q = q.where(FamilyManagement.managed_user_id == payload.managed_user_id)
        if payload.managed_member_id:
            q = q.where(FamilyManagement.managed_member_id == payload.managed_member_id)
        mgmt = (await db.execute(q.order_by(FamilyManagement.created_at.desc()))).scalars().first()

    if not mgmt:
        # [BUGFIX-MY-GUARDIAN-CARD-2-20260528] 第 3、4 点核心改造：
        # 不再返回 404，改为幂等成功 + should_refresh，让前端友好提示并自动刷新列表。
        return {
            "removed": deleted_any,
            "deleted": deleted_any,
            "should_refresh": True,
            "type": ("invitation" if deleted_any else "noop"),
            "message": ("已移除" if deleted_any else "该记录已被移除，列表已刷新"),
        }

    # [BUGFIX-MY-GUARDIAN-CARD-20260528] 不再拦截 active 状态：
    # 用户在"我守护的人"列表对已绑定家人点击移除应直接受理，
    # 等同于"先解除守护再清档"，避免出现"守护中状态不允许移除"的死循环。
    # 但仍保留对硬件设备/在途服药计划的校验，确保不会误删数据。
    was_active = (mgmt.status == "active")

    # 不可删校验 2：硬件设备
    if mgmt.managed_user_id and await _has_bound_device(db, mgmt.managed_user_id):
        raise HTTPException(status_code=400, detail="该家人已绑定硬件设备，请先在设备管理中解绑后再移除")

    # 不可删校验 3：邀请中（仍生效——邀请中应先取消邀请）
    if mgmt.managed_member_id:
        inviting = (await db.execute(
            select(func.count(FamilyInvitation.id)).where(
                FamilyInvitation.inviter_user_id == current_user.id,
                FamilyInvitation.member_id == mgmt.managed_member_id,
                FamilyInvitation.status == "pending",
                FamilyInvitation.expires_at > now,
            )
        )).scalar()
        if int(inviting or 0) > 0:
            raise HTTPException(status_code=400, detail="该家人尚有邀请中的记录，请先取消邀请后再移除")

    # 不可删校验 4：在途服药计划
    if mgmt.managed_user_id and await _has_active_med_plan(db, mgmt.managed_user_id):
        raise HTTPException(status_code=400, detail="该家人存在在途服药计划，请先终止服药计划后再移除")

    # [BUGFIX-MY-GUARDIAN-CARD-20260528] 执行移除：
    # - active → 直接置 removed（等同于"解除守护"）并写解除通知
    # - 其他状态 → 保持原有 removed 软删逻辑
    mgmt.status = "removed"
    mgmt.cancelled_at = now
    mgmt.cancelled_by = current_user.id

    # 如果之前是 active，给被守护人发通知（与 DELETE /api/family/management/{id} 行为对齐）
    if was_active and mgmt.managed_user_id and mgmt.managed_user_id != current_user.id:
        try:
            op_name = current_user.nickname or current_user.phone or "对方"
            db.add(Notification(
                user_id=mgmt.managed_user_id,
                title="守护关系已解除",
                content=f"{op_name} 已解除与您的家庭健康档案守护关系",
                type=NotificationType.system,
                extra_data={
                    "type": "family_management",
                    "action": "management_cancelled",
                    "management_id": mgmt.id,
                    "operator_role": "manager",
                    "via": "guardian_v13_remove",
                },
            ))
        except Exception:
            # 通知失败不影响主流程
            pass

    # 孤儿档案判定：managed_user_id 是否有自有账号（v1.3 简化判断 - managed_member_id 存在但 managed_user_id 为 None 或 user 不存在）
    is_orphan = False
    if mgmt.managed_member_id and not mgmt.managed_user_id:
        is_orphan = True
    elif mgmt.managed_user_id:
        u = await db.get(User, mgmt.managed_user_id)
        if not u or getattr(u, "is_active", True) is False:
            is_orphan = True

    if is_orphan and mgmt.managed_member_id:
        # 删除 family_member（"孤儿档案"L1+L2+L3 全删）
        member = await db.get(FamilyMember, mgmt.managed_member_id)
        if member:
            member.status = "deleted"

    db.add(ManagementOperationLog(
        management_id=mgmt.id,
        operator_user_id=current_user.id,
        operation_type="remove_family_v13",
        operation_detail={
            "is_orphan": is_orphan,
            "managed_user_id": mgmt.managed_user_id,
            "managed_member_id": mgmt.managed_member_id,
        },
    ))
    await db.flush()

    return {
        "removed": True,
        "deleted": True,
        "should_refresh": True,
        "type": "management",
        "management_id": mgmt.id,
        "is_orphan": is_orphan,
        "message": "已移除" + ("（孤儿档案已一并删除）" if is_orphan else "（共管关系已软删，对方档案保留）"),
    }


# ─────────── 内部工具函数 (供其他模块复用) ───────────


async def deduct_quota_with_proxy_pay(
    db: AsyncSession,
    *,
    managed_user_id: int,
    call_type: str = "alert",
) -> dict:
    """[PRD-GUARDIAN-V1.3 §7.2.2] 统一扣费工具：先本人 → 后主代付

    返回：
    {
        "deducted_user_id": int,  # 实际扣费的用户 id
        "is_proxy_pay": bool,     # 是否走了主代付
        "success": bool,          # 是否扣费成功（含额度耗尽）
        "reason": str,            # 失败原因
        "is_orphan": bool,        # 孤儿档案（直接扣主）
    }
    """
    from app.api.guardian_system_v12 import _get_user_quotas, _get_used_count

    now = datetime.utcnow()

    # 1) 判定孤儿档案
    managed_user = await db.get(User, managed_user_id) if managed_user_id else None
    if not managed_user:
        # 找主守护人
        primary = (await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.managed_user_id == managed_user_id,
                FamilyManagement.status == "active",
                FamilyManagement.is_primary_guardian == True,
            )
        )).scalars().first()
        if primary:
            # 孤儿档案 → 直接扣主
            db.add(GuardianAlertQuotaUsage(
                user_id=primary.manager_user_id,
                managed_user_id=managed_user_id,
                used_at=now,
                call_type=call_type,
            ))
            await db.flush()
            return {
                "deducted_user_id": primary.manager_user_id,
                "is_proxy_pay": True,
                "is_orphan": True,
                "success": True,
                "reason": "",
            }
        return {
            "deducted_user_id": None,
            "is_proxy_pay": False,
            "is_orphan": True,
            "success": False,
            "reason": "无主守护人可代付",
        }

    # 2) 先扣本人
    quotas = await _get_user_quotas(db, managed_user_id)
    used = await _get_used_count(db, managed_user_id, call_type)
    quota_key = "emergency_ai_call_count" if call_type == "alert" else "ai_remind_quota"
    total = quotas.get(quota_key, 0)

    if total < 0 or used < total:
        # 本人额度够 → 扣本人
        db.add(GuardianAlertQuotaUsage(
            user_id=managed_user_id,
            managed_user_id=managed_user_id,
            used_at=now,
            call_type=call_type,
        ))
        await db.flush()
        return {
            "deducted_user_id": managed_user_id,
            "is_proxy_pay": False,
            "is_orphan": False,
            "success": True,
            "reason": "",
        }

    # 3) 本人额度耗尽 → 找主守护人
    primary = (await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
            FamilyManagement.is_primary_guardian == True,
        )
    )).scalars().first()
    if not primary:
        return {
            "deducted_user_id": None,
            "is_proxy_pay": False,
            "is_orphan": False,
            "success": False,
            "reason": "本人额度已用完且无主守护人",
        }

    # 4) 主代付开关
    proxy_enabled = await _is_proxy_pay_enabled(db, primary.manager_user_id, managed_user_id)
    if not proxy_enabled:
        return {
            "deducted_user_id": None,
            "is_proxy_pay": False,
            "is_orphan": False,
            "success": False,
            "reason": "本人额度已用完且主守护人已关闭代付",
        }

    # 5) 主额度
    primary_quotas = await _get_user_quotas(db, primary.manager_user_id)
    primary_used = await _get_used_count(db, primary.manager_user_id, call_type)
    primary_total = primary_quotas.get(quota_key, 0)
    if primary_total >= 0 and primary_used >= primary_total:
        return {
            "deducted_user_id": None,
            "is_proxy_pay": False,
            "is_orphan": False,
            "success": False,
            "reason": "主守护人代付额度也已用完",
        }

    # 6) 扣主代付
    db.add(GuardianAlertQuotaUsage(
        user_id=primary.manager_user_id,
        managed_user_id=managed_user_id,
        used_at=now,
        call_type=call_type,
    ))
    await db.flush()

    # 通知被守护人 + 主守护人
    db.add(Notification(
        user_id=managed_user_id,
        title="AI 呼叫额度已由家人代付",
        content="您本月 AI 呼叫额度已用完，已由家人为您代付，请放心使用",
        type=NotificationType.system,
        extra_data={"type": "proxy_pay_deducted_v13"},
    ))
    db.add(Notification(
        user_id=primary.manager_user_id,
        title="您正在为家人代付 AI 呼叫",
        content=f"您正在为 {managed_user.nickname or '家人'} 代付 AI 呼叫",
        type=NotificationType.system,
        extra_data={"type": "proxy_pay_deducted_v13"},
    ))
    await db.flush()

    return {
        "deducted_user_id": primary.manager_user_id,
        "is_proxy_pay": True,
        "is_orphan": False,
        "success": True,
        "reason": "",
    }
