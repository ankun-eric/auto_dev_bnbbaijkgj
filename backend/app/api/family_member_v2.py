"""[PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29] 健康档案 — 成员卡片状态机 v1.0

核心目标（4 个统一）：
1. **状态统一**：成员卡片状态机收敛为 S0~S7（含本人 S0、已取消 S7）+ R1~R3
2. **入口统一**：废弃"无档案直接发邀请"入口，所有邀请必须先建档案
3. **按钮统一**：每种状态主按钮 1 个 + 次操作收纳
4. **接口统一**：删除收口到唯一接口 `DELETE /api/family/member/{member_id}`，
   返回结构化 `reason_code`

提供的接口：
- `GET    /api/family/member/{member_id}/state`         查询单个成员卡片状态
- `GET    /api/family/member/state/list`                批量列表，返回 7 状态聚合
- `DELETE /api/family/member/{member_id}`               统一删除（含闸门校验）
- `POST   /api/family/member/{member_id}/invite`        重新邀请（cancel 旧 + insert 新 pending）
- `POST   /api/family/member/{member_id}/unbind`        解除守护（S1 → S6）
- `GET    /api/family/member/quota`                     配额详情（X/Y）
- `POST   /api/family/member/admin/cleanup-orphan-invitations` 一次性清理孤儿邀请（管理员）

reason_code 字典：
| reason_code | 含义 |
|---|---|
| `OK` | 删除成功 |
| `HAS_ACTIVE_GUARDIANSHIP` | 处于 S1 已绑定 |
| `HAS_PENDING_INVITATION` | 处于 S3 邀请中 |
| `HAS_BOUND_DEVICE` | 名下有绑定设备 |
| `HAS_ACTIVE_MEDICATION` | 有在途服药计划 |
| `RATE_LIMIT_EXCEEDED` | 当日删除超 5 次 |
| `NOT_FOUND` | 档案不存在或已删 |
| `PERMISSION_DENIED` | 非档案所属用户 |
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    HealthProfile,
    Notification,
    NotificationType,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["健康档案-成员状态机 v1"])

# ──────────── 状态机常量 ────────────
# 正向（我守护的人）
STATE_S0_SELF = "S0"                # 本人
STATE_S1_BOUND = "S1"               # 已绑定·守护中
STATE_S2_NOT_INVITED = "S2"         # 未邀请
STATE_S3_INVITING = "S3"            # 邀请中
STATE_S4_REJECTED = "S4"            # 已拒绝
STATE_S5_EXPIRED = "S5"             # 已过期
STATE_S6_UNBOUND = "S6"             # 已解绑
STATE_S7_CANCELLED = "S7"           # 已取消

# 状态显示名 / 颜色（用于前端渲染）
_STATE_META: dict[str, dict] = {
    STATE_S0_SELF: {"label": "本人", "color": "blue", "primary_action": "view_profile"},
    STATE_S1_BOUND: {"label": "守护中", "color": "green", "primary_action": "view_profile"},
    STATE_S2_NOT_INVITED: {"label": "未邀请", "color": "gray", "primary_action": "invite"},
    STATE_S3_INVITING: {"label": "邀请中", "color": "orange", "primary_action": "view_invite_code"},
    STATE_S4_REJECTED: {"label": "已拒绝", "color": "red", "primary_action": "reinvite"},
    STATE_S5_EXPIRED: {"label": "已过期", "color": "gray", "primary_action": "reinvite"},
    STATE_S6_UNBOUND: {"label": "已解绑", "color": "lightgray", "primary_action": "reinvite"},
    STATE_S7_CANCELLED: {"label": "已取消", "color": "lightgray", "primary_action": "reinvite"},
}

# 占用配额的状态（所有非删除态都占用，与 Q-Final-3 对齐）
QUOTA_OCCUPYING_STATES = {
    STATE_S0_SELF, STATE_S1_BOUND, STATE_S2_NOT_INVITED, STATE_S3_INVITING,
    STATE_S4_REJECTED, STATE_S5_EXPIRED, STATE_S6_UNBOUND, STATE_S7_CANCELLED,
}

# 不允许直接删除的状态
NON_DELETABLE_STATES = {STATE_S0_SELF, STATE_S1_BOUND, STATE_S3_INVITING}

# 删除频次限制：5 次/UID/自然日
DELETE_RATE_LIMIT_PER_DAY = 5
_DELETE_RATE_BUCKET: dict[str, list[datetime]] = {}

# 邀请有效期：24 小时
INVITE_LIFE_HOURS = 24

# 默认上限
DEFAULT_MAX_MEMBERS = 10


# ──────────── Schemas ────────────


class MemberStateItem(BaseModel):
    """单个成员卡片状态"""
    member_id: int
    state: str  # S0~S7
    state_label: str
    state_color: str
    primary_action: str  # view_profile / invite / view_invite_code / reinvite
    nickname: Optional[str] = None
    relationship_type: Optional[str] = None
    is_self: bool = False
    avatar_color_index: int = 0
    # 邀请信息（仅 S3 有效）
    invite_code: Optional[str] = None
    invite_expires_at: Optional[str] = None
    invite_remaining_hours: Optional[int] = None
    # 闸门
    can_delete: bool = False
    delete_block_reason: Optional[str] = None
    # 删除阻塞原因码
    can_unbind: bool = False
    # 邀请记录条数（仅显示菜单项依据）
    invitation_count: int = 0
    # 时间
    created_at: Optional[str] = None


class MemberStateListResponse(BaseModel):
    items: List[MemberStateItem]
    total: int
    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 字段口径统一为「含本人」：
    # quota_used = 已建档家庭成员总数（含本人卡）
    # quota_max  = 家庭守护成员总人数上限（含本人）= membership_plans.max_managed 原值
    quota_used: int
    quota_max: int
    quota_remaining: int
    guarded_count: int  # 仅 S1 计入
    state_counts: dict


class DeleteResponseData(BaseModel):
    member_id: int
    deleted_tables: List[str]
    reason_code: str = "OK"


class DeleteSuccessResponse(BaseModel):
    success: bool = True
    data: DeleteResponseData


class DeleteErrorDetail(BaseModel):
    reason_code: str
    message: str
    block_field: Optional[str] = None


class DeleteRequest(BaseModel):
    reason: Optional[str] = "user_initiated"
    force: bool = False


class ReinviteRequest(BaseModel):
    pass  # 暂无附加参数


class ReinviteResponse(BaseModel):
    invitation_id: int
    invite_code: str
    member_id: int
    expires_at: str
    qr_url: Optional[str] = None
    cancelled_count: int = 0  # 旧记录被取消数量


class UnbindRequest(BaseModel):
    pass


class QuotaResponse(BaseModel):
    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 字段口径统一为「含本人」
    quota_max: int           # 上限（含本人）= 数据库 max_managed 原值
    quota_used: int          # 已建档案数（含本人卡）
    quota_remaining: int     # 剩余可添加
    guarded_count: int       # 实际守护中（S1）
    self_member_id: Optional[int] = None


# ──────────── 工具函数 ────────────


def _gen_invite_code(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _get_max_members(db: AsyncSession, user_id: int) -> int:
    """[PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30]
    返回家庭守护成员总人数上限（**含本人**），与数据库 max_managed 原值一致。
    - _get_max_guardians 内部已 -1 转为"不含本人上限"供配额比较使用；
    - 本函数 +1 还原为"含本人上限"，对外暴露给前端原样展示。
    - 不限档 -1 透传。
    """
    try:
        from app.api.guardian_system_v13 import _get_max_guardians  # type: ignore
        raw = await _get_max_guardians(db, user_id)
        if raw == -1:
            return -1
        return int(raw) + 1
    except Exception:
        return DEFAULT_MAX_MEMBERS


async def _has_bound_device(db: AsyncSession, member_id: int, member_user_id: Optional[int]) -> bool:
    """检查档案名下是否有绑定设备（家庭成员维度或对应注册账号维度）"""
    # 1) home_safety 设备绑定（按 member_id）
    try:
        from app.api.home_safety_v1 import HomeSafetyDeviceBinding  # type: ignore
        # member_id 字段（v2.1+ 新增）
        if hasattr(HomeSafetyDeviceBinding, "member_id"):
            r = await db.execute(
                select(func.count(HomeSafetyDeviceBinding.id)).where(
                    HomeSafetyDeviceBinding.member_id == member_id,
                )
            )
            if int(r.scalar() or 0) > 0:
                return True
    except Exception:
        pass

    # 2) 普通 user_device_bindings（按 member_user_id）
    if member_user_id:
        try:
            from app.models.devices_v2 import UserDeviceBinding  # type: ignore
            r = await db.execute(
                select(func.count(UserDeviceBinding.id)).where(
                    UserDeviceBinding.user_id == member_user_id,
                )
            )
            if int(r.scalar() or 0) > 0:
                return True
        except Exception:
            pass
    return False


async def _has_active_medication(db: AsyncSession, member_id: int, member_user_id: Optional[int]) -> bool:
    """检查档案名下是否有在途服药计划"""
    try:
        from app.models.models import MedicationPlan  # type: ignore
    except Exception:
        return False

    try:
        # 按 user_id 维度
        if member_user_id:
            r = await db.execute(
                select(func.count(MedicationPlan.id)).where(
                    MedicationPlan.user_id == member_user_id,
                    MedicationPlan.enabled == True,  # noqa: E712
                )
            )
            if int(r.scalar() or 0) > 0:
                return True
        # 按 member_id 维度（如果 MedicationPlan 模型有此字段）
        if hasattr(MedicationPlan, "family_member_id"):
            r = await db.execute(
                select(func.count(MedicationPlan.id)).where(
                    MedicationPlan.family_member_id == member_id,
                    MedicationPlan.enabled == True,  # noqa: E712
                )
            )
            if int(r.scalar() or 0) > 0:
                return True
    except Exception:
        pass
    return False


def _check_delete_rate_limit(user_id: int) -> bool:
    """5 次/UID/自然日。返回 True 表示通过；False 表示超限。"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    key = str(user_id)
    bucket = _DELETE_RATE_BUCKET.get(key, [])
    # 清理过期
    bucket = [t for t in bucket if t >= today_start]
    if len(bucket) >= DELETE_RATE_LIMIT_PER_DAY:
        _DELETE_RATE_BUCKET[key] = bucket
        return False
    bucket.append(now)
    _DELETE_RATE_BUCKET[key] = bucket
    return True


async def _resolve_member_state(
    db: AsyncSession,
    *,
    user_id: int,
    member: FamilyMember,
    invitations_by_member: dict[int, list[FamilyInvitation]],
    mgmt_by_member: dict[int, FamilyManagement],
    now: datetime,
) -> tuple[str, Optional[FamilyInvitation]]:
    """计算成员的状态机 state（S0~S7），返回 (state, related_invitation)"""
    if member.is_self:
        return STATE_S0_SELF, None

    mgmt = mgmt_by_member.get(member.id)
    invs = invitations_by_member.get(member.id, [])
    # 自动过期标记（不写库，只用于判定）
    for inv in invs:
        if inv.status == "pending" and inv.expires_at and inv.expires_at < now:
            # 视作 expired，但不在此处改库，由 list 接口主动 flush
            pass

    # 取最新一条邀请
    latest_inv = invs[0] if invs else None

    # 优先级：active mgmt > pending invitation > 历史
    if mgmt and mgmt.status == "active":
        return STATE_S1_BOUND, latest_inv

    if mgmt and mgmt.status == "removed":
        # S6 已解绑
        return STATE_S6_UNBOUND, latest_inv

    if latest_inv:
        s = (latest_inv.status or "").lower()
        if s == "pending":
            if latest_inv.expires_at and latest_inv.expires_at < now:
                return STATE_S5_EXPIRED, latest_inv
            return STATE_S3_INVITING, latest_inv
        if s == "rejected":
            return STATE_S4_REJECTED, latest_inv
        if s == "expired":
            return STATE_S5_EXPIRED, latest_inv
        if s == "cancelled":
            return STATE_S7_CANCELLED, latest_inv

    # 没有 mgmt 也没有 invitation → 仅有档案 = S2 未邀请
    return STATE_S2_NOT_INVITED, latest_inv


def _state_to_item(
    *,
    member: FamilyMember,
    state: str,
    inv: Optional[FamilyInvitation],
    invitation_count: int,
    now: datetime,
    can_delete: bool,
    delete_block_reason: Optional[str],
    can_unbind: bool,
) -> MemberStateItem:
    meta = _STATE_META[state]
    invite_code = None
    invite_expires = None
    remaining_hours = None
    if state == STATE_S3_INVITING and inv:
        invite_code = inv.invite_code
        invite_expires = inv.expires_at.isoformat() if inv.expires_at else None
        if inv.expires_at:
            delta = inv.expires_at - now
            remaining_hours = max(0, int(delta.total_seconds() // 3600))
    return MemberStateItem(
        member_id=member.id,
        state=state,
        state_label=meta["label"],
        state_color=meta["color"],
        primary_action=meta["primary_action"],
        nickname=member.nickname,
        relationship_type=member.relationship_type,
        is_self=bool(member.is_self),
        avatar_color_index=int(member.avatar_color_index or 0) % 5,
        invite_code=invite_code,
        invite_expires_at=invite_expires,
        invite_remaining_hours=remaining_hours,
        can_delete=can_delete,
        delete_block_reason=delete_block_reason,
        can_unbind=can_unbind,
        invitation_count=invitation_count,
        created_at=member.created_at.isoformat() if member.created_at else None,
    )


# ──────────── 接口 ────────────


@router.get("/api/family/member/state/list", response_model=MemberStateListResponse)
async def list_member_states(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-FAMILY-MEMBER-STATE-MACHINE-V1] 列表：返回当前用户名下所有 family_member 的状态机 state。

    返回字段：
    - items: List[MemberStateItem]，按 created_at ASC 排序，本人卡片始终置顶
    [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 字段口径统一为「含本人」：
    - quota_used: 已建档家庭成员总数（含本人卡）
    - quota_max: 含本人上限（与 membership_plans.max_managed 数据库原值一致，-1=不限）
    - quota_remaining: 剩余可添加
    - guarded_count: S1 已绑定数（实际守护中）
    - state_counts: 各 state 的统计
    """
    now = datetime.utcnow()

    # 1) 全部 family_member（含本人，排除 deleted）
    mb_res = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status != "deleted",
        ).order_by(FamilyMember.is_self.desc(), FamilyMember.created_at.asc())
    )
    members = mb_res.scalars().all()

    member_ids = [m.id for m in members]

    # 2) FamilyManagement（按 managed_member_id 索引）
    mgmts = []
    if member_ids:
        mg_res = await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == current_user.id,
                FamilyManagement.managed_member_id.in_(member_ids),
            ).order_by(FamilyManagement.created_at.desc())
        )
        mgmts = mg_res.scalars().all()
    mgmt_by_member: dict[int, FamilyManagement] = {}
    for m in mgmts:
        if m.managed_member_id and m.managed_member_id not in mgmt_by_member:
            mgmt_by_member[m.managed_member_id] = m

    # 3) FamilyInvitation（按 member_id 索引，desc）
    invs = []
    if member_ids:
        iv_res = await db.execute(
            select(FamilyInvitation).where(
                FamilyInvitation.inviter_user_id == current_user.id,
                FamilyInvitation.member_id.in_(member_ids),
            ).order_by(FamilyInvitation.created_at.desc())
        )
        invs = iv_res.scalars().all()

    # 自动过期：pending 且超时
    for inv in invs:
        if inv.status == "pending" and inv.expires_at and inv.expires_at < now:
            inv.status = "expired"
    if invs:
        await db.flush()

    invs_by_member: dict[int, list[FamilyInvitation]] = {}
    for inv in invs:
        invs_by_member.setdefault(inv.member_id, []).append(inv)

    items: list[MemberStateItem] = []
    state_counts: dict[str, int] = {s: 0 for s in _STATE_META.keys()}

    for mb in members:
        state, inv = await _resolve_member_state(
            db,
            user_id=current_user.id,
            member=mb,
            invitations_by_member=invs_by_member,
            mgmt_by_member=mgmt_by_member,
            now=now,
        )
        state_counts[state] = state_counts.get(state, 0) + 1

        # 闸门
        can_delete = state not in NON_DELETABLE_STATES
        delete_block_reason = None
        if not can_delete:
            if state == STATE_S0_SELF:
                delete_block_reason = "本人档案不可删除"
            elif state == STATE_S1_BOUND:
                delete_block_reason = "请先解除守护关系"
            elif state == STATE_S3_INVITING:
                delete_block_reason = "请先取消邀请"

        # 设备/服药校验（仅 S2/S4/S5/S6/S7 才需要校验）
        if can_delete and state != STATE_S0_SELF:
            if await _has_bound_device(db, mb.id, mb.member_user_id):
                can_delete = False
                delete_block_reason = "请先解绑该成员名下设备"
            elif await _has_active_medication(db, mb.id, mb.member_user_id):
                can_delete = False
                delete_block_reason = "请先终止服药计划"

        can_unbind = (state == STATE_S1_BOUND)
        # S1 解除守护也要校验设备
        if can_unbind:
            if await _has_bound_device(db, mb.id, mb.member_user_id):
                can_unbind = False

        invitation_count = len(invs_by_member.get(mb.id, []))

        items.append(_state_to_item(
            member=mb,
            state=state,
            inv=inv,
            invitation_count=invitation_count,
            now=now,
            can_delete=can_delete,
            delete_block_reason=delete_block_reason,
            can_unbind=can_unbind,
        ))

    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 配额口径统一为「含本人」：
    # quota_used = 已建档家庭成员总数（含本人卡）
    # quota_max  = 含本人上限（与数据库 max_managed 原值一致，-1=不限）
    quota_max = await _get_max_members(db, current_user.id)
    total_count = len(members)  # 已含本人
    quota_used = total_count
    if quota_max == -1:
        quota_remaining = 9999  # 不限
    else:
        quota_remaining = max(0, quota_max - quota_used)
    guarded_count = state_counts.get(STATE_S1_BOUND, 0)

    return MemberStateListResponse(
        items=items,
        total=len(items),
        quota_used=quota_used,
        quota_max=quota_max,
        quota_remaining=quota_remaining,
        guarded_count=guarded_count,
        state_counts=state_counts,
    )


@router.get("/api/family/member/quota", response_model=QuotaResponse)
async def get_member_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §5] 配额查询接口。

    [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 字段口径统一为「含本人」：
    - quota_max: 上限（含本人，来自 membership_plan.max_managed / free_member_quota 原值，-1=不限）
    - quota_used: 已建档案数（含本人卡，统计 family_member where deleted_at is null）
    - quota_remaining: 剩余可添加 = max - used（不限时返回 9999）
    - guarded_count: 实际守护中 = count(family_management where status='active')
    - self_member_id: 本人 family_member.id
    """
    quota_max = await _get_max_members(db, current_user.id)

    # quota_used 改为含本人卡总数
    r = await db.execute(
        select(func.count(FamilyMember.id)).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status != "deleted",
        )
    )
    quota_used = int(r.scalar() or 0)

    r2 = await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    guarded_count = int(r2.scalar() or 0)

    self_member = (await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.is_self == True,  # noqa: E712
            FamilyMember.status != "deleted",
        )
    )).scalars().first()

    if quota_max == -1:
        quota_remaining = 9999
    else:
        quota_remaining = max(0, quota_max - quota_used)

    return QuotaResponse(
        quota_max=quota_max,
        quota_used=quota_used,
        quota_remaining=quota_remaining,
        guarded_count=guarded_count,
        self_member_id=self_member.id if self_member else None,
    )


@router.delete("/api/family/member/{member_id}")
async def delete_member_unified(
    member_id: int,
    payload: Optional[DeleteRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §6.1] 统一删除接口（唯一）。

    返回结构化 reason_code：
    - 成功：{"success": true, "data": {"member_id": ..., "deleted_tables": [...], "reason_code": "OK"}}
    - 失败：HTTP 400 + detail: {"reason_code": "...", "message": "...", "block_field": "..."}

    闸门规则：
    1) S0 本人 → PERMISSION_DENIED
    2) S1 已绑定 → HAS_ACTIVE_GUARDIANSHIP
    3) S3 邀请中 → HAS_PENDING_INVITATION
    4) 名下有绑定设备 → HAS_BOUND_DEVICE
    5) 有在途服药计划 → HAS_ACTIVE_MEDICATION
    6) 频次：5 次/UID/日 → RATE_LIMIT_EXCEEDED
    7) NOT_FOUND / PERMISSION_DENIED 标准
    """
    payload = payload or DeleteRequest()
    now = datetime.utcnow()

    # 频次校验
    if not payload.force and not _check_delete_rate_limit(current_user.id):
        raise HTTPException(
            status_code=429,
            detail={
                "reason_code": "RATE_LIMIT_EXCEEDED",
                "message": "操作频繁，请明日再试",
                "block_field": "rate_limit",
            },
        )

    member = await db.get(FamilyMember, member_id)
    if not member or member.status == "deleted":
        raise HTTPException(
            status_code=404,
            detail={
                "reason_code": "NOT_FOUND",
                "message": "该档案不存在或已被删除",
                "block_field": "member",
            },
        )

    if member.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "reason_code": "PERMISSION_DENIED",
                "message": "您没有权限操作该档案",
                "block_field": "user_id",
            },
        )

    if member.is_self:
        raise HTTPException(
            status_code=400,
            detail={
                "reason_code": "PERMISSION_DENIED",
                "message": "本人档案不可删除",
                "block_field": "is_self",
            },
        )

    # 1) S1 校验：active 守护关系
    active_mgmt = (await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_member_id == member_id,
            FamilyManagement.status == "active",
        )
    )).scalars().first()
    if active_mgmt and not payload.force:
        raise HTTPException(
            status_code=400,
            detail={
                "reason_code": "HAS_ACTIVE_GUARDIANSHIP",
                "message": "请先解除守护关系",
                "block_field": "guardianship",
            },
        )

    # 2) S3 校验：pending 邀请且未过期
    pending_inv = (await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.inviter_user_id == current_user.id,
            FamilyInvitation.member_id == member_id,
            FamilyInvitation.status == "pending",
            FamilyInvitation.expires_at > now,
        )
    )).scalars().first()
    if pending_inv and not payload.force:
        raise HTTPException(
            status_code=400,
            detail={
                "reason_code": "HAS_PENDING_INVITATION",
                "message": "请先取消邀请",
                "block_field": "invitation",
            },
        )

    # 3) 设备校验
    if await _has_bound_device(db, member_id, member.member_user_id) and not payload.force:
        raise HTTPException(
            status_code=400,
            detail={
                "reason_code": "HAS_BOUND_DEVICE",
                "message": "请先解绑该成员名下设备",
                "block_field": "device",
            },
        )

    # 4) 服药校验
    if await _has_active_medication(db, member_id, member.member_user_id) and not payload.force:
        raise HTTPException(
            status_code=400,
            detail={
                "reason_code": "HAS_ACTIVE_MEDICATION",
                "message": "请先终止服药计划",
                "block_field": "medication",
            },
        )

    # ── 执行删除 ──
    deleted_tables: list[str] = []

    # a) 软删 family_member
    member.status = "deleted"
    deleted_tables.append("family_member")

    # b) 软删 health_profile
    hp_res = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == current_user.id,
            HealthProfile.family_member_id == member_id,
        )
    )
    for hp in hp_res.scalars().all():
        await db.delete(hp)
        if "health_profile" not in deleted_tables:
            deleted_tables.append("health_profile")

    # c) 取消所有未结束的 invitation（pending/rejected/expired → cancelled，accepted 保留审计）
    inv_res = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.inviter_user_id == current_user.id,
            FamilyInvitation.member_id == member_id,
            FamilyInvitation.status.in_(["pending", "rejected", "expired"]),
        )
    )
    for inv in inv_res.scalars().all():
        inv.status = "cancelled"
        if "family_invitation" not in deleted_tables:
            deleted_tables.append("family_invitation")

    # d) 软删 family_management（不再 active）
    mg_res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_member_id == member_id,
            FamilyManagement.status != "removed",
        )
    )
    for mg in mg_res.scalars().all():
        mg.status = "removed"
        mg.cancelled_at = now
        mg.cancelled_by = current_user.id
        if "family_management" not in deleted_tables:
            deleted_tables.append("family_management")

    await db.flush()

    return {
        "success": True,
        "data": {
            "member_id": member_id,
            "deleted_tables": deleted_tables,
            "reason_code": "OK",
        },
    }


@router.post("/api/family/member/{member_id}/invite", response_model=ReinviteResponse)
async def reinvite_member(
    member_id: int,
    payload: Optional[ReinviteRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §6.4] 重新邀请。

    逻辑：
    1) 查询该 member_id 名下所有 invitation in (pending, rejected, expired)
    2) 全部置为 cancelled（保留审计痕迹）
    3) INSERT 一条 status=pending 的新邀请记录
    4) 生成新邀请码 + 二维码 URL
    """
    now = datetime.utcnow()
    member = await db.get(FamilyMember, member_id)
    if not member or member.status == "deleted":
        raise HTTPException(status_code=404, detail="该档案不存在或已被删除")
    if member.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="您没有权限操作该档案")
    if member.is_self:
        raise HTTPException(status_code=400, detail="本人档案不可邀请")

    # 不允许对 S1 已绑定再邀
    active_mgmt = (await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_member_id == member_id,
            FamilyManagement.status == "active",
        )
    )).scalars().first()
    if active_mgmt:
        raise HTTPException(status_code=400, detail="该档案已绑定守护关系，无需重新邀请")

    # 取消所有 pending/rejected/expired
    inv_res = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.inviter_user_id == current_user.id,
            FamilyInvitation.member_id == member_id,
            FamilyInvitation.status.in_(["pending", "rejected", "expired"]),
        )
    )
    cancelled_count = 0
    for inv in inv_res.scalars().all():
        inv.status = "cancelled"
        cancelled_count += 1

    # 创建新邀请
    new_code = _gen_invite_code()
    new_inv = FamilyInvitation(
        invite_code=new_code,
        inviter_user_id=current_user.id,
        member_id=member_id,
        status="pending",
        expires_at=now + timedelta(hours=INVITE_LIFE_HOURS),
        relation_type=member.relationship_type,
        nickname=member.nickname or "",
    )
    db.add(new_inv)
    await db.flush()

    qr_url = (
        f"https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/"
        f"family-auth?code={new_code}"
    )

    return ReinviteResponse(
        invitation_id=new_inv.id,
        invite_code=new_code,
        member_id=member_id,
        expires_at=new_inv.expires_at.isoformat(),
        qr_url=qr_url,
        cancelled_count=cancelled_count,
    )


@router.post("/api/family/member/{member_id}/unbind")
async def unbind_member(
    member_id: int,
    payload: Optional[UnbindRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §3.1] 解除守护：S1 → S6。

    校验：
    - 该档案当前必须是 S1（active 守护关系）
    - 名下无设备
    """
    now = datetime.utcnow()
    member = await db.get(FamilyMember, member_id)
    if not member or member.status == "deleted":
        raise HTTPException(status_code=404, detail="该档案不存在或已被删除")
    if member.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="您没有权限操作该档案")

    # 找 active 关系
    mgmt = (await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_member_id == member_id,
            FamilyManagement.status == "active",
        )
    )).scalars().first()
    if not mgmt:
        raise HTTPException(status_code=400, detail="该档案未处于守护中状态")

    # 设备校验
    if await _has_bound_device(db, member_id, member.member_user_id):
        raise HTTPException(status_code=400, detail="请先解绑该成员名下设备")

    mgmt.status = "removed"
    mgmt.cancelled_at = now
    mgmt.cancelled_by = current_user.id

    # 通知被守护人
    if mgmt.managed_user_id and mgmt.managed_user_id != current_user.id:
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
                    "via": "family_member_v2_unbind",
                },
            ))
        except Exception:
            pass

    await db.flush()

    return {
        "success": True,
        "data": {
            "member_id": member_id,
            "management_id": mgmt.id,
            "new_state": STATE_S6_UNBOUND,
            "message": "已解除守护",
        },
    }


@router.post("/api/family/member/admin/cleanup-orphan-invitations")
async def cleanup_orphan_invitations(
    dry_run: bool = Query(True, description="是否仅试运行（不写库）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §7.1] 一次性清理脚本：

    1) 物理删除孤儿邀请（无 member_id 且非 pending）
    2) 对老用户的 pending 孤儿，统一置 cancelled 并下发系统通知

    仅允许超级管理员（或者部署期间执行）调用。普通用户调用返回 403。
    """
    # 简化权限：仅 superuser
    is_admin = bool(getattr(current_user, "is_admin", False) or getattr(current_user, "is_superuser", False))
    if not is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可执行")

    # 1) 待物理删除（非 pending 的孤儿）
    target_q = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.member_id.is_(None),
            FamilyInvitation.status != "pending",
        )
    )
    target_invs = target_q.scalars().all()

    # 2) pending 孤儿
    pending_q = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.member_id.is_(None),
            FamilyInvitation.status == "pending",
        )
    )
    pending_invs = pending_q.scalars().all()

    deleted_count = 0
    cancelled_count = 0
    notified_users: set[int] = set()

    if not dry_run:
        for inv in target_invs:
            await db.delete(inv)
            deleted_count += 1
        for inv in pending_invs:
            inv.status = "cancelled"
            cancelled_count += 1
            if inv.inviter_user_id and inv.inviter_user_id not in notified_users:
                try:
                    db.add(Notification(
                        user_id=inv.inviter_user_id,
                        title="邀请已自动取消",
                        content="由于功能升级，请重新发起邀请",
                        type=NotificationType.system,
                        extra_data={"type": "orphan_invitation_cleanup"},
                    ))
                    notified_users.add(inv.inviter_user_id)
                except Exception:
                    pass
        await db.flush()
    else:
        deleted_count = len(target_invs)
        cancelled_count = len(pending_invs)

    return {
        "success": True,
        "dry_run": dry_run,
        "deleted_count": deleted_count,
        "cancelled_count": cancelled_count,
        "notified_users": len(notified_users),
    }
