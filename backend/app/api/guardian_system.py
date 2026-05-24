"""[守护人体系 PRD v1.1 2026-05-25]

实现内容：
- 主守护人 / 普通守护人角色管理
- 主守护人转移（现任主守护人发起 + 被守护人同意）
- 数量上限按会员等级（免费 3 / 付费 10）
- 异常告警串行外呼策略与额度耗尽降级
- 邀请记录列表查询（已生效 / 已过期 / 已作废 / 待确认）

字段说明：
- family_management.is_primary_guardian: 是否为主守护人（每个被守护人最多 1 个）
- family_management.priority_order: 串行外呼优先级（数字越小越优先）
- guardian_transfer_requests: 主守护人转移请求表
- guardian_alert_quota_usage: 异常告警免费额度使用记录
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    GuardianAlertQuotaUsage,
    GuardianTransferRequest,
    ManagementOperationLog,
    Notification,
    NotificationType,
    SystemMessage,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["守护人体系"])

# 默认免费会员可拥有的守护人数（被守护人维度）
FREE_MAX_GUARDIANS = 3
# 默认付费会员可拥有的守护人数
PAID_MAX_GUARDIANS = 10
# 单个用户最多守护的人数
MAX_GUARDING = 10
# 免费会员每月免费电话告警额度（次）
FREE_ALERT_CALL_QUOTA = 5
# 串行外呼无应答超时秒数
RING_NO_ANSWER_SECONDS = 60


# ─────────── Schemas ───────────

class GuardianRoleResponse(BaseModel):
    """守护人角色信息（含主/普通 + 付费/免费徽章）"""
    management_id: int
    manager_user_id: int
    manager_nickname: Optional[str] = None
    manager_phone: Optional[str] = None
    managed_user_id: int
    managed_user_nickname: Optional[str] = None
    managed_member_id: Optional[int] = None
    is_primary_guardian: bool = False
    priority_order: int = 100
    is_paid_member: bool = False
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GuardianTransferInitRequest(BaseModel):
    """发起主守护人转移请求"""
    target_management_id: int = Field(..., description="接任人对应的 family_management.id")


class GuardianTransferRequestResponse(BaseModel):
    id: int
    managed_user_id: int
    from_management_id: int
    to_management_id: int
    from_user_nickname: Optional[str] = None
    to_user_nickname: Optional[str] = None
    status: str  # pending/approved/cancelled/expired
    created_at: datetime
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdatePriorityRequest(BaseModel):
    """被守护人调整其守护人的串行外呼顺序"""
    items: List[dict] = Field(..., description="[{management_id, priority_order}]")


class AlertQuotaResponse(BaseModel):
    """异常告警免费电话额度查询"""
    user_id: int
    is_paid_member: bool
    monthly_free_quota: int  # 每月免费额度
    used_this_month: int  # 本月已用
    remaining: int  # 剩余
    can_receive_call: bool  # 是否还能接收电话告警


class InvitationRecordResponse(BaseModel):
    """邀请记录列表项（含过期/作废/生效状态展示）"""
    invite_code: str
    inviter_user_id: int
    member_id: int
    member_nickname: Optional[str] = None
    relation_type: Optional[str] = None
    status: str  # pending / accepted / expired / cancelled
    status_label: str  # 待确认 / 已生效 / 已过期 / 已作废
    expires_at: datetime
    accepted_by_nickname: Optional[str] = None
    accepted_at: Optional[datetime] = None
    created_at: datetime
    can_reinvite: bool = False  # 过期/作废可以一键重新发送


# ─────────── 工具函数 ───────────


async def _is_paid_member(db: AsyncSession, user_id: int) -> bool:
    """[PRD-GUARDIAN-V1] 判断用户是否为付费会员（查询 user_memberships 表，若不存在视为免费）"""
    try:
        from sqlalchemy import text
        res = await db.execute(text(
            "SELECT 1 FROM user_memberships "
            "WHERE user_id=:uid AND status='active' "
            "  AND (expires_at IS NULL OR expires_at > NOW()) LIMIT 1"
        ).bindparams(uid=user_id))
        return res.scalar() is not None
    except Exception as e:
        logger.warning("[Guardian] check paid member fail, fallback free: %s", e)
        return False


async def _get_max_guardians(db: AsyncSession, managed_user_id: int) -> int:
    """[PRD-GUARDIAN-V1] 根据被守护人的会员等级返回守护人数量上限"""
    if await _is_paid_member(db, managed_user_id):
        return PAID_MAX_GUARDIANS
    return FREE_MAX_GUARDIANS


async def _ensure_primary_guardian(db: AsyncSession, managed_user_id: int) -> None:
    """[PRD-GUARDIAN-V1] 确保被守护人有主守护人；若无则将最早绑定的设为主"""
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
        ).order_by(FamilyManagement.created_at.asc())
    )
    rows = res.scalars().all()
    if not rows:
        return
    has_primary = any(bool(getattr(r, "is_primary_guardian", False)) for r in rows)
    if not has_primary:
        rows[0].is_primary_guardian = True
        if not getattr(rows[0], "priority_order", None):
            rows[0].priority_order = 0
        await db.flush()


# ─────────── 接口 ───────────


@router.get("/api/guardian/list", response_model=dict)
async def list_my_guardians(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 我的守护人列表（含主/普通 + 付费/免费 徽章）"""
    await _ensure_primary_guardian(db, current_user.id)
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == current_user.id,
            FamilyManagement.status == "active",
        ).order_by(
            FamilyManagement.priority_order.asc().nullslast(),
            FamilyManagement.created_at.asc(),
        )
    )
    items = []
    for mgmt in res.scalars().all():
        manager = (await db.execute(
            select(User).where(User.id == mgmt.manager_user_id)
        )).scalar_one_or_none()
        items.append(GuardianRoleResponse(
            management_id=mgmt.id,
            manager_user_id=mgmt.manager_user_id,
            manager_nickname=manager.nickname if manager else None,
            manager_phone=manager.phone if manager else None,
            managed_user_id=mgmt.managed_user_id,
            managed_user_nickname=current_user.nickname,
            managed_member_id=mgmt.managed_member_id,
            is_primary_guardian=bool(getattr(mgmt, "is_primary_guardian", False)),
            priority_order=int(getattr(mgmt, "priority_order", 100) or 100),
            is_paid_member=await _is_paid_member(db, mgmt.manager_user_id),
            status=mgmt.status,
            created_at=mgmt.created_at,
        ).model_dump())

    max_count = await _get_max_guardians(db, current_user.id)
    return {
        "items": items,
        "total": len(items),
        "max_count": max_count,
        "is_paid_member": await _is_paid_member(db, current_user.id),
    }


@router.get("/api/guardian/i-guard", response_model=dict)
async def list_people_i_guard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 我守护的人列表（含主/普通 + 付费/免费 徽章）"""
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        ).order_by(FamilyManagement.created_at.asc())
    )
    items = []
    for mgmt in res.scalars().all():
        managed_user = (await db.execute(
            select(User).where(User.id == mgmt.managed_user_id)
        )).scalar_one_or_none()
        items.append(GuardianRoleResponse(
            management_id=mgmt.id,
            manager_user_id=mgmt.manager_user_id,
            manager_nickname=current_user.nickname,
            manager_phone=current_user.phone,
            managed_user_id=mgmt.managed_user_id,
            managed_user_nickname=managed_user.nickname if managed_user else None,
            managed_member_id=mgmt.managed_member_id,
            is_primary_guardian=bool(getattr(mgmt, "is_primary_guardian", False)),
            priority_order=int(getattr(mgmt, "priority_order", 100) or 100),
            is_paid_member=await _is_paid_member(db, current_user.id),
            status=mgmt.status,
            created_at=mgmt.created_at,
        ).model_dump())
    return {
        "items": items,
        "total": len(items),
        "max_guarding": MAX_GUARDING,
    }


@router.post("/api/guardian/transfer/initiate", response_model=dict)
async def initiate_primary_transfer(
    payload: GuardianTransferInitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 现任主守护人发起转移请求

    流程：
      1. 校验当前用户是某被守护人的主守护人
      2. 校验目标接任人是该被守护人的现有守护人
      3. 创建 transfer request，发推送/系统消息给被守护人确认
    """
    # 当前用户必须是某个被守护人的主守护人
    target_mgmt = (await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.id == payload.target_management_id,
            FamilyManagement.status == "active",
        )
    )).scalar_one_or_none()
    if not target_mgmt:
        raise HTTPException(status_code=404, detail="目标接任人守护关系不存在或已失效")

    if target_mgmt.manager_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能转移给自己")

    managed_user_id = target_mgmt.managed_user_id

    # 查询当前用户是否是该被守护人的主守护人
    my_mgmt = (await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
        )
    )).scalar_one_or_none()
    if not my_mgmt or not getattr(my_mgmt, "is_primary_guardian", False):
        raise HTTPException(status_code=403, detail="您不是该被守护人的主守护人，无权发起转移")

    # 创建 transfer request（用 ORM 以便兼容 SQLite 测试 / MySQL 生产）
    expires_at = datetime.utcnow() + timedelta(hours=72)
    transfer = GuardianTransferRequest(
        managed_user_id=managed_user_id,
        from_management_id=my_mgmt.id,
        to_management_id=target_mgmt.id,
        status="pending",
        created_at=datetime.utcnow(),
        expires_at=expires_at,
    )
    db.add(transfer)
    await db.flush()
    transfer_id = transfer.id

    # 通知被守护人
    target_user = (await db.execute(
        select(User).where(User.id == target_mgmt.manager_user_id)
    )).scalar_one_or_none()
    target_nick = (target_user.nickname or target_user.phone) if target_user else "新主守护人"
    from_nick = current_user.nickname or current_user.phone or "原主守护人"

    db.add(SystemMessage(
        message_type="guardian_transfer_request",
        recipient_user_id=managed_user_id,
        sender_user_id=current_user.id,
        title="主守护人转移申请",
        content=f"{from_nick} 申请将主守护人身份转移给 {target_nick}，请前往家庭守护页面确认",
        related_business_id=str(transfer_id),
        related_business_type="guardian_transfer",
        click_action="/family-bindlist",
    ))
    db.add(Notification(
        user_id=managed_user_id,
        title="主守护人转移申请",
        content=f"{from_nick} 申请将主守护人身份转移给 {target_nick}",
        type=NotificationType.system,
        extra_data={
            "type": "guardian_transfer_request",
            "transfer_id": transfer_id,
        },
    ))

    await db.flush()
    return {
        "transfer_id": transfer_id,
        "managed_user_id": managed_user_id,
        "status": "pending",
        "message": "转移申请已发起，等待被守护人确认",
    }


@router.post("/api/guardian/transfer/{transfer_id}/approve", response_model=dict)
async def approve_primary_transfer(
    transfer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 被守护人同意主守护人转移"""
    transfer = (await db.execute(
        select(GuardianTransferRequest).where(GuardianTransferRequest.id == transfer_id)
    )).scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=404, detail="转移请求不存在")
    if transfer.managed_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有被守护人本人可以确认")
    if transfer.status != "pending":
        raise HTTPException(status_code=400, detail=f"该请求已 {transfer.status}，无法操作")
    if transfer.expires_at and transfer.expires_at < datetime.utcnow():
        transfer.status = "expired"
        await db.flush()
        raise HTTPException(status_code=400, detail="转移请求已过期")

    from_mgmt = (await db.execute(
        select(FamilyManagement).where(FamilyManagement.id == transfer.from_management_id)
    )).scalar_one_or_none()
    to_mgmt = (await db.execute(
        select(FamilyManagement).where(FamilyManagement.id == transfer.to_management_id)
    )).scalar_one_or_none()
    if not from_mgmt or not to_mgmt:
        raise HTTPException(status_code=404, detail="守护关系已变更，无法完成转移")
    if from_mgmt.status != "active" or to_mgmt.status != "active":
        raise HTTPException(status_code=400, detail="守护关系已失效，无法完成转移")

    # 切换主守护人
    from_mgmt.is_primary_guardian = False
    from_mgmt.priority_order = 1  # 降为第 2 顺位
    to_mgmt.is_primary_guardian = True
    to_mgmt.priority_order = 0

    # 操作日志
    db.add(ManagementOperationLog(
        management_id=to_mgmt.id,
        operator_user_id=current_user.id,
        operation_type="primary_guardian_transferred",
        operation_detail={
            "from_management_id": from_mgmt.id,
            "to_management_id": to_mgmt.id,
            "transfer_id": transfer_id,
        },
    ))

    # 更新 transfer request
    transfer.status = "approved"
    transfer.approved_at = datetime.utcnow()

    # 通知三方
    from_user = (await db.execute(
        select(User).where(User.id == from_mgmt.manager_user_id)
    )).scalar_one_or_none()
    to_user = (await db.execute(
        select(User).where(User.id == to_mgmt.manager_user_id)
    )).scalar_one_or_none()
    from_nick = (from_user.nickname or from_user.phone) if from_user else "原主守护人"
    to_nick = (to_user.nickname or to_user.phone) if to_user else "新主守护人"
    managed_nick = current_user.nickname or current_user.phone or "被守护人"

    for uid, title, content in [
        (from_mgmt.manager_user_id, "主守护人身份已转移",
         f"您已不再是 {managed_nick} 的主守护人，新主守护人为 {to_nick}"),
        (to_mgmt.manager_user_id, "您已成为主守护人",
         f"您已成为 {managed_nick} 的主守护人，将首要接收电话告警"),
        (current_user.id, "主守护人已更新",
         f"您的主守护人已从 {from_nick} 转移给 {to_nick}"),
    ]:
        db.add(SystemMessage(
            message_type="guardian_transfer_done",
            recipient_user_id=uid,
            sender_user_id=current_user.id,
            title=title,
            content=content,
            related_business_id=str(transfer_id),
            related_business_type="guardian_transfer",
            click_action="/family-bindlist",
        ))
        db.add(Notification(
            user_id=uid,
            title=title,
            content=content,
            type=NotificationType.system,
            extra_data={"type": "guardian_transfer_done", "transfer_id": transfer_id},
        ))

    await db.flush()
    return {
        "transfer_id": transfer_id,
        "status": "approved",
        "new_primary_management_id": to_mgmt.id,
        "message": "主守护人转移完成",
    }


@router.post("/api/guardian/transfer/{transfer_id}/cancel", response_model=dict)
async def cancel_primary_transfer(
    transfer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 原主守护人或被守护人取消转移请求"""
    transfer = (await db.execute(
        select(GuardianTransferRequest).where(GuardianTransferRequest.id == transfer_id)
    )).scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=404, detail="转移请求不存在")
    if transfer.status != "pending":
        raise HTTPException(status_code=400, detail=f"该请求已 {transfer.status}")

    # 权限：被守护人 或 原主守护人
    from_mgmt = (await db.execute(
        select(FamilyManagement).where(FamilyManagement.id == transfer.from_management_id)
    )).scalar_one_or_none()
    if not (
        transfer.managed_user_id == current_user.id
        or (from_mgmt and from_mgmt.manager_user_id == current_user.id)
    ):
        raise HTTPException(status_code=403, detail="无权取消该转移请求")

    transfer.status = "cancelled"
    transfer.cancelled_at = datetime.utcnow()
    await db.flush()
    return {"transfer_id": transfer_id, "status": "cancelled"}


@router.get("/api/guardian/transfer/pending", response_model=dict)
async def list_pending_transfers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 查询与当前用户相关的待确认转移请求"""
    # 先取所有 pending 的转移请求
    all_pending = (await db.execute(
        select(GuardianTransferRequest)
        .where(GuardianTransferRequest.status == "pending")
        .order_by(GuardianTransferRequest.created_at.desc())
    )).scalars().all()

    items = []
    for t in all_pending:
        fm = (await db.execute(
            select(FamilyManagement).where(FamilyManagement.id == t.from_management_id)
        )).scalar_one_or_none()
        tm = (await db.execute(
            select(FamilyManagement).where(FamilyManagement.id == t.to_management_id)
        )).scalar_one_or_none()
        from_uid = fm.manager_user_id if fm else None
        to_uid = tm.manager_user_id if tm else None
        # 仅返回当前用户相关的
        if not (
            t.managed_user_id == current_user.id
            or from_uid == current_user.id
            or to_uid == current_user.id
        ):
            continue
        from_user = (await db.execute(select(User).where(User.id == from_uid))).scalar_one_or_none() if from_uid else None
        to_user = (await db.execute(select(User).where(User.id == to_uid))).scalar_one_or_none() if to_uid else None
        items.append({
            "id": t.id,
            "managed_user_id": t.managed_user_id,
            "from_management_id": t.from_management_id,
            "to_management_id": t.to_management_id,
            "from_user_nickname": (from_user.nickname or from_user.phone) if from_user else None,
            "to_user_nickname": (to_user.nickname or to_user.phone) if to_user else None,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
            "can_approve": t.managed_user_id == current_user.id,
        })
    return {"items": items, "total": len(items)}


@router.post("/api/guardian/priority", response_model=dict)
async def update_guardian_priority(
    payload: UpdatePriorityRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 被守护人调整其守护人的串行外呼优先级顺序"""
    if not payload.items:
        return {"message": "无更新项", "updated": 0}

    updated = 0
    for it in payload.items:
        mid = it.get("management_id")
        priority = it.get("priority_order")
        if mid is None or priority is None:
            continue
        res = await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.id == int(mid),
                FamilyManagement.managed_user_id == current_user.id,
                FamilyManagement.status == "active",
            )
        )
        mgmt = res.scalar_one_or_none()
        if not mgmt:
            continue
        # 主守护人保持 priority_order=0
        if not getattr(mgmt, "is_primary_guardian", False):
            mgmt.priority_order = int(priority)
            updated += 1
    await db.flush()
    return {"message": "已更新优先级", "updated": updated}


@router.get("/api/guardian/alert-quota", response_model=AlertQuotaResponse)
async def get_alert_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 查询当前守护人本月异常告警免费电话额度使用情况"""
    is_paid = await _is_paid_member(db, current_user.id)
    monthly_quota = 999 if is_paid else FREE_ALERT_CALL_QUOTA

    # 统计本月已使用
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cnt = (await db.execute(
        select(func.count(GuardianAlertQuotaUsage.id)).where(
            GuardianAlertQuotaUsage.user_id == current_user.id,
            GuardianAlertQuotaUsage.used_at >= month_start,
        )
    )).scalar()
    used = int(cnt or 0)
    remaining = max(0, monthly_quota - used)
    return AlertQuotaResponse(
        user_id=current_user.id,
        is_paid_member=is_paid,
        monthly_free_quota=monthly_quota,
        used_this_month=used,
        remaining=remaining,
        can_receive_call=is_paid or remaining > 0,
    )


class AlertCallSimRequest(BaseModel):
    """模拟触发异常告警（用于自动化测试 / 内部接口）"""
    managed_user_id: int


@router.post("/api/guardian/alert/simulate-serial-call", response_model=dict)
async def simulate_serial_alert_call(
    payload: AlertCallSimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 模拟异常告警串行外呼策略

    - 主守护人优先
    - 第 2 顺位、第 3 顺位按 priority_order 升序、created_at 升序
    - 付费守护人直接收
    - 免费守护人在免费额度内可收，额度用完自动降级（不再扣电话额度，仅 App 推送 + 短信）
    - 异常告警本身完全免费、不扣任何人的额度（PRD §6.1）
    - 但需要记录"已尝试外呼"以供风控统计
    """
    # 校验：被守护人必须存在（不强制权限，方便系统/管理员触发）
    target = (await db.execute(
        select(User).where(User.id == payload.managed_user_id)
    )).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="被守护人不存在")

    # 获取按优先级排列的守护人
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == payload.managed_user_id,
            FamilyManagement.status == "active",
        ).order_by(
            FamilyManagement.is_primary_guardian.desc(),
            FamilyManagement.priority_order.asc().nullslast(),
            FamilyManagement.created_at.asc(),
        )
    )
    guardians = res.scalars().all()

    if not guardians:
        return {"managed_user_id": payload.managed_user_id, "call_plan": [], "message": "无守护人"}

    call_plan = []
    for idx, mgmt in enumerate(guardians):
        manager = (await db.execute(
            select(User).where(User.id == mgmt.manager_user_id)
        )).scalar_one_or_none()
        is_paid = await _is_paid_member(db, mgmt.manager_user_id)

        # 检查该守护人本月剩余额度
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cnt = (await db.execute(
            select(func.count(GuardianAlertQuotaUsage.id)).where(
                GuardianAlertQuotaUsage.user_id == mgmt.manager_user_id,
                GuardianAlertQuotaUsage.used_at >= month_start,
            )
        )).scalar()
        used = int(cnt or 0)
        free_quota = FREE_ALERT_CALL_QUOTA
        can_call = is_paid or (used < free_quota)

        # 记录一次"已尝试外呼"
        if can_call:
            db.add(GuardianAlertQuotaUsage(
                user_id=mgmt.manager_user_id,
                managed_user_id=payload.managed_user_id,
                used_at=datetime.utcnow(),
                call_type="alert",
            ))

        call_plan.append({
            "order": idx + 1,
            "management_id": mgmt.id,
            "manager_user_id": mgmt.manager_user_id,
            "manager_nickname": manager.nickname if manager else None,
            "is_primary": bool(getattr(mgmt, "is_primary_guardian", False)),
            "is_paid_member": is_paid,
            "can_receive_phone_call": can_call,
            "fallback_to_push_sms": not can_call,
            "ring_timeout_seconds": RING_NO_ANSWER_SECONDS,
        })

        # 额度用完即推 App + 短信提示升级（PRD §6.4）
        if not can_call and used == free_quota:
            db.add(Notification(
                user_id=mgmt.manager_user_id,
                title="电话告警额度已用完",
                content=f"您本月的免费电话告警额度已用完，升级会员可恢复电话告警。",
                type=NotificationType.system,
                extra_data={"type": "alert_quota_exhausted"},
            ))
            db.add(Notification(
                user_id=payload.managed_user_id,
                title="您的守护人电话告警额度已用完",
                content=f"守护人 {manager.nickname if manager else ''} 的本月免费电话告警额度已用完，建议升级会员。",
                type=NotificationType.system,
                extra_data={"type": "guardian_alert_quota_exhausted"},
            ))

    await db.flush()
    return {
        "managed_user_id": payload.managed_user_id,
        "call_plan": call_plan,
        "total_guardians": len(guardians),
        "primary_guardian_id": guardians[0].manager_user_id if guardians else None,
    }


@router.get("/api/guardian/invitations/records", response_model=dict)
async def list_invitation_records(
    status: Optional[str] = Query(None, description="过滤状态：pending/accepted/expired/cancelled"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 查询当前用户发出的邀请记录列表（含状态徽章）"""
    q = select(FamilyInvitation).where(FamilyInvitation.inviter_user_id == current_user.id)
    if status:
        q = q.where(FamilyInvitation.status == status)
    q = q.order_by(FamilyInvitation.created_at.desc())

    total = (await db.execute(
        select(func.count(FamilyInvitation.id)).where(FamilyInvitation.inviter_user_id == current_user.id)
    )).scalar() or 0

    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    status_labels = {
        "pending": "待确认",
        "accepted": "已生效",
        "expired": "已过期",
        "cancelled": "已作废",
    }

    items = []
    for inv in rows:
        # 修正过期状态
        actual_status = inv.status
        if actual_status == "pending" and inv.expires_at and inv.expires_at < datetime.utcnow():
            actual_status = "expired"
            inv.status = "expired"

        member = (await db.execute(
            select(FamilyMember).where(FamilyMember.id == inv.member_id)
        )).scalar_one_or_none()
        accepted_user = None
        if inv.accepted_by:
            accepted_user = (await db.execute(
                select(User).where(User.id == inv.accepted_by)
            )).scalar_one_or_none()

        items.append(InvitationRecordResponse(
            invite_code=inv.invite_code,
            inviter_user_id=inv.inviter_user_id,
            member_id=inv.member_id,
            member_nickname=member.nickname if member else None,
            relation_type=inv.relation_type,
            status=actual_status,
            status_label=status_labels.get(actual_status, actual_status),
            expires_at=inv.expires_at,
            accepted_by_nickname=(accepted_user.nickname or accepted_user.phone) if accepted_user else None,
            accepted_at=inv.accepted_at,
            created_at=inv.created_at,
            can_reinvite=actual_status in ("expired", "cancelled"),
        ).model_dump())

    await db.flush()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ─────────── 后台管理接口 ───────────


admin_router = APIRouter(tags=["守护人体系-后台"])


@router.get("/api/admin/guardian/relations", response_model=dict)
async def admin_list_guardian_relations(
    keyword: Optional[str] = Query(None, description="手机号/昵称模糊匹配"),
    is_primary: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1] 后台守护关系查询（运营/客服/风控用）"""
    if str(current_user.role) not in ("admin", "UserRole.admin"):
        # 兼容字符串形式与枚举形式
        if getattr(current_user, "role", None) and getattr(current_user.role, "value", None) != "admin":
            raise HTTPException(status_code=403, detail="仅管理员可访问")

    q = select(FamilyManagement).where(FamilyManagement.status == "active")
    if is_primary is not None:
        q = q.where(FamilyManagement.is_primary_guardian == is_primary)
    q = q.order_by(FamilyManagement.created_at.desc())

    total_q = select(func.count(FamilyManagement.id)).where(FamilyManagement.status == "active")
    if is_primary is not None:
        total_q = total_q.where(FamilyManagement.is_primary_guardian == is_primary)
    total = (await db.execute(total_q)).scalar() or 0

    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = []
    for mgmt in rows:
        manager = (await db.execute(select(User).where(User.id == mgmt.manager_user_id))).scalar_one_or_none()
        managed = (await db.execute(select(User).where(User.id == mgmt.managed_user_id))).scalar_one_or_none()
        if keyword:
            k = keyword.strip()
            if not any(k in (v or "") for v in [
                manager.nickname if manager else "",
                manager.phone if manager else "",
                managed.nickname if managed else "",
                managed.phone if managed else "",
            ]):
                continue
        items.append({
            "id": mgmt.id,
            "manager_user_id": mgmt.manager_user_id,
            "manager_nickname": manager.nickname if manager else None,
            "manager_phone": manager.phone if manager else None,
            "managed_user_id": mgmt.managed_user_id,
            "managed_nickname": managed.nickname if managed else None,
            "managed_phone": managed.phone if managed else None,
            "is_primary_guardian": bool(getattr(mgmt, "is_primary_guardian", False)),
            "priority_order": int(getattr(mgmt, "priority_order", 100) or 100),
            "is_paid_manager": await _is_paid_member(db, mgmt.manager_user_id),
            "created_at": mgmt.created_at.isoformat() if mgmt.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
