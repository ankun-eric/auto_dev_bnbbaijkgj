"""[守护人体系 PRD v1.2 2026-05-25]

v1.2 关键变更：
- 主守护人转让流程重构：同意方改为接收者（v1.1 是被守护人）
- 新增被守护人上帝视角直改接口
- 新增主守护人代付开关
- AI 外呼提醒扣额度：默认谁设置扣谁；主守护人代付开启后扣主守护人
- 紧急 AI 呼叫扣额度：统一扣主守护人（不管谁接通）
- 套餐字段规范化：emergency_ai_call_count、max_managed、max_guardians
- 紧急呼叫触发源管理（4 种内置 + 后台可扩展）
- AI 外呼提醒列表带权限过滤
- 邀请记录扩展（含我发起的 + 别人邀请我的）
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
from app.core.security import get_current_user, require_role
from app.models.membership_plan import FreeMemberQuota, MembershipPlan, UserMembershipSub
from app.models.models import (
    AiCallReminder,
    EmergencyCallSource,
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    GuardianAlertQuotaUsage,
    GuardianProxyPay,
    GuardianTransferRequest,
    ManagementOperationLog,
    Notification,
    NotificationType,
    ReverseGuardianInvitation,
    SystemMessage,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["守护人体系-v1.2"])
admin_router = APIRouter(prefix="/api/admin", tags=["守护人体系-后台-v1.2"])

admin_dep = require_role("admin")

# 串行外呼无应答超时秒数
RING_NO_ANSWER_SECONDS = 60


# ─────────── Schemas ───────────


class GuardianRoleV12Item(BaseModel):
    """v1.2 守护人列表项（含关系称呼 + 角色徽章）"""
    management_id: int
    manager_user_id: int
    manager_nickname: Optional[str] = None
    managed_user_id: int
    managed_user_nickname: Optional[str] = None
    relation_label: Optional[str] = Field(None, description="关系称呼，如『母亲』")
    role_badge: str = Field("normal", description="primary / normal")
    is_primary_guardian: bool = False
    priority_order: int = 100
    is_paid_member: bool = False
    status: str
    created_at: datetime
    proxy_pay_enabled: bool = Field(False, description="主守护人是否代付该被守护人 AI 外呼额度")

    model_config = ConfigDict(from_attributes=True)


class TransferInitRequest(BaseModel):
    """发起主守护人转让（v1.2: 由接收者同意）"""
    target_management_id: int = Field(..., description="拟接任的目标守护人对应 family_management.id")


class OwnerDirectAdjustRequest(BaseModel):
    """被守护人上帝视角直改"""
    action: str = Field(..., description="set_primary / remove_guardian")
    target_management_id: int


class ProxyPaySwitchRequest(BaseModel):
    enabled: bool


class AiCallReminderCreateRequest(BaseModel):
    target_user_id: int
    title: str
    content: Optional[str] = None
    reminder_type: str = "general"
    schedule_cron: Optional[str] = None
    next_fire_at: Optional[datetime] = None


class EmergencySourceCreateRequest(BaseModel):
    source_code: str
    source_name: str
    description: Optional[str] = None
    is_enabled: bool = True
    trigger_condition: Optional[str] = None
    applicable_device_type: Optional[str] = None
    sort_order: int = 0


class EmergencySourceUpdateRequest(BaseModel):
    source_name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    trigger_condition: Optional[str] = None
    applicable_device_type: Optional[str] = None
    sort_order: Optional[int] = None


# ─────────── 工具函数 ───────────


# v1.2 关系称呼 fallback：在 family_management 没有关系字段时，从 FamilyMember 表取
RELATION_FALLBACKS = {
    "father": "父亲", "mother": "母亲", "spouse": "配偶",
    "son": "儿子", "daughter": "女儿", "brother": "兄弟", "sister": "姐妹",
    "grandfather": "祖父", "grandmother": "祖母", "other": "亲友",
}


async def _is_paid_member(db: AsyncSession, user_id: int) -> bool:
    """判断用户是否为付费会员（v1.2 同 v1.1）"""
    now = datetime.utcnow()
    res = await db.execute(
        select(UserMembershipSub).where(
            UserMembershipSub.user_id == user_id,
            UserMembershipSub.status == "active",
            UserMembershipSub.expire_at > now,
        )
    )
    return res.scalars().first() is not None


async def _get_user_plan(db: AsyncSession, user_id: int) -> Optional[MembershipPlan]:
    now = datetime.utcnow()
    res = await db.execute(
        select(UserMembershipSub).where(
            UserMembershipSub.user_id == user_id,
            UserMembershipSub.status == "active",
            UserMembershipSub.expire_at > now,
        ).order_by(UserMembershipSub.expire_at.desc())
    )
    sub = res.scalars().first()
    if not sub:
        return None
    return await db.get(MembershipPlan, sub.plan_id)


async def _get_user_quotas(db: AsyncSession, user_id: int) -> dict:
    """[v1.2] 获取用户的额度配置：
    - 付费用户：套餐配置
    - 免费用户：免费额度配置
    """
    plan = await _get_user_plan(db, user_id)
    if plan:
        return {
            "is_paid_member": True,
            "plan_id": plan.id,
            "plan_name": plan.name,
            "ai_remind_quota": int(plan.ai_remind_quota or 0),
            "emergency_ai_call_count": int(getattr(plan, "emergency_ai_call_count", 0) or 0),
            "max_managed": int(getattr(plan, "max_managed", 10) or 10),
            "max_guardians": int(plan.max_guardians or 1),
            "point_multiplier": float(getattr(plan, "point_multiplier", 1.0) or 1.0),
            "discount_rate": float(plan.discount_rate or 1.0),
        }
    quota = await db.get(FreeMemberQuota, 1)
    return {
        "is_paid_member": False,
        "plan_id": None,
        "plan_name": "普通会员",
        "ai_remind_quota": int(quota.ai_remind_quota) if quota else 0,
        "emergency_ai_call_count": int(getattr(quota, "emergency_ai_call_count", 3)) if quota else 3,
        "max_managed": int(getattr(quota, "max_managed", 3)) if quota else 3,
        "max_guardians": int(quota.max_guardians) if quota else 1,
        "point_multiplier": 1.0,
        "discount_rate": 1.0,
    }


async def _get_used_count(db: AsyncSession, user_id: int, call_type: str) -> int:
    """统计某用户本月某类额度已使用次数"""
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cnt = (await db.execute(
        select(func.count(GuardianAlertQuotaUsage.id)).where(
            GuardianAlertQuotaUsage.user_id == user_id,
            GuardianAlertQuotaUsage.used_at >= month_start,
            GuardianAlertQuotaUsage.call_type == call_type,
        )
    )).scalar()
    return int(cnt or 0)


async def _get_primary_guardian_mgmt(db: AsyncSession, managed_user_id: int) -> Optional[FamilyManagement]:
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
            FamilyManagement.is_primary_guardian == True,
        )
    )
    return res.scalars().first()


async def _resolve_relation_label(db: AsyncSession, mgmt: FamilyManagement) -> Optional[str]:
    """优先取 family_management.relation_type，回退到 FamilyMember"""
    rel = getattr(mgmt, "relation_type", None)
    if rel:
        return RELATION_FALLBACKS.get(rel, rel)
    if mgmt.managed_member_id:
        m = await db.get(FamilyMember, mgmt.managed_member_id)
        if m:
            return getattr(m, "relation_type_name", None) or getattr(m, "relationship_type", None)
    return None


async def _is_proxy_pay_enabled(db: AsyncSession, primary_uid: int, managed_uid: int) -> bool:
    res = await db.execute(
        select(GuardianProxyPay).where(
            GuardianProxyPay.primary_guardian_user_id == primary_uid,
            GuardianProxyPay.managed_user_id == managed_uid,
        )
    )
    rec = res.scalars().first()
    return bool(rec and rec.enabled)


# ─────────── 接口 ───────────


@router.get("/api/guardian/v12/i-guard")
async def list_people_i_guard_v12(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §11.2] 我守护的人列表（直筒列表，含关系称呼 + 角色徽章 + 代付状态）"""
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        ).order_by(FamilyManagement.created_at.asc())
    )
    items = []
    for mgmt in res.scalars().all():
        managed_user = await db.get(User, mgmt.managed_user_id)
        relation_label = await _resolve_relation_label(db, mgmt)
        is_primary = bool(getattr(mgmt, "is_primary_guardian", False))
        proxy_pay = False
        if is_primary:
            proxy_pay = await _is_proxy_pay_enabled(db, current_user.id, mgmt.managed_user_id)
        items.append(GuardianRoleV12Item(
            management_id=mgmt.id,
            manager_user_id=mgmt.manager_user_id,
            manager_nickname=current_user.nickname,
            managed_user_id=mgmt.managed_user_id,
            managed_user_nickname=managed_user.nickname if managed_user else None,
            relation_label=relation_label,
            role_badge="primary" if is_primary else "normal",
            is_primary_guardian=is_primary,
            priority_order=int(getattr(mgmt, "priority_order", 100) or 100),
            is_paid_member=await _is_paid_member(db, current_user.id),
            status=mgmt.status,
            created_at=mgmt.created_at,
            proxy_pay_enabled=proxy_pay,
        ).model_dump())

    quotas = await _get_user_quotas(db, current_user.id)
    return {
        "items": items,
        "total": len(items),
        "max_managed": quotas["max_managed"],
        "is_paid_member": quotas["is_paid_member"],
    }


@router.get("/api/guardian/v12/managed/{managed_user_id}/all-guardians")
async def list_all_guardians_of_managed(
    managed_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §11.3] 守护管理抽屉 - 列出某被守护人的全部守护人列表

    权限：调用者必须是该被守护人本身、或该被守护人的某个守护人
    """
    # 权限校验
    if current_user.id != managed_user_id:
        res = await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == current_user.id,
                FamilyManagement.managed_user_id == managed_user_id,
                FamilyManagement.status == "active",
            )
        )
        if not res.scalars().first():
            raise HTTPException(status_code=403, detail="您不是该被守护人的守护人")

    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
        ).order_by(
            FamilyManagement.is_primary_guardian.desc(),
            FamilyManagement.priority_order.asc().nullslast(),
            FamilyManagement.created_at.asc(),
        )
    )
    items = []
    for mgmt in res.scalars().all():
        manager = await db.get(User, mgmt.manager_user_id)
        relation_label = await _resolve_relation_label(db, mgmt)
        is_primary = bool(getattr(mgmt, "is_primary_guardian", False))
        items.append({
            "management_id": mgmt.id,
            "manager_user_id": mgmt.manager_user_id,
            "manager_nickname": manager.nickname if manager else None,
            "manager_phone": manager.phone if manager else None,
            "relation_label": relation_label,
            "role_badge": "primary" if is_primary else "normal",
            "is_primary_guardian": is_primary,
            "priority_order": int(getattr(mgmt, "priority_order", 100) or 100),
            "is_paid_member": await _is_paid_member(db, mgmt.manager_user_id),
            "is_self": mgmt.manager_user_id == current_user.id,
            "created_at": mgmt.created_at.isoformat() if mgmt.created_at else None,
        })

    # 判断当前用户角色
    caller_role = "owner" if current_user.id == managed_user_id else "guardian"
    caller_is_primary = False
    if caller_role == "guardian":
        for it in items:
            if it["is_self"]:
                caller_is_primary = it["is_primary_guardian"]
                break

    return {
        "items": items,
        "total": len(items),
        "caller_role": caller_role,
        "caller_is_primary": caller_is_primary,
    }


@router.post("/api/guardian/v12/transfer/initiate")
async def transfer_initiate_v12(
    payload: TransferInitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §7.2 通道 A] 主守护人发起转让 → 通知接收者"""
    target_mgmt = await db.get(FamilyManagement, payload.target_management_id)
    if not target_mgmt or target_mgmt.status != "active":
        raise HTTPException(status_code=404, detail="目标守护关系不存在或已失效")

    if target_mgmt.manager_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能转让给自己")

    managed_user_id = target_mgmt.managed_user_id

    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
            FamilyManagement.is_primary_guardian == True,
        )
    )
    my_mgmt = res.scalars().first()
    if not my_mgmt:
        raise HTTPException(status_code=403, detail="您不是该被守护人的主守护人")

    # 24h 内同一对 from/to 不可重复发起
    one_day_ago = datetime.utcnow() - timedelta(hours=24)
    existing = (await db.execute(
        select(GuardianTransferRequest).where(
            GuardianTransferRequest.from_management_id == my_mgmt.id,
            GuardianTransferRequest.to_management_id == target_mgmt.id,
            GuardianTransferRequest.status == "pending",
            GuardianTransferRequest.created_at >= one_day_ago,
        )
    )).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="已存在 24 小时内的待确认转让，请等接收者确认或取消")

    transfer = GuardianTransferRequest(
        managed_user_id=managed_user_id,
        from_management_id=my_mgmt.id,
        to_management_id=target_mgmt.id,
        status="pending",
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(transfer)
    await db.flush()
    transfer_id = transfer.id

    # 通知接收者 + 被守护人（接收者主操作，被守护人知晓）
    target_user = await db.get(User, target_mgmt.manager_user_id)
    target_nick = (target_user.nickname or target_user.phone) if target_user else "新主守护人"
    from_nick = current_user.nickname or current_user.phone or "原主守护人"

    db.add(SystemMessage(
        message_type="guardian_transfer_request_v12",
        recipient_user_id=target_mgmt.manager_user_id,
        sender_user_id=current_user.id,
        title="您被指定为新主守护人",
        content=f"{from_nick} 申请将主守护人身份转让给您，请前往「我守护的人 → 守护管理」确认",
        related_business_id=str(transfer_id),
        related_business_type="guardian_transfer_v12",
        click_action="/health-profile",
    ))
    db.add(Notification(
        user_id=target_mgmt.manager_user_id,
        title="您被指定为新主守护人",
        content=f"{from_nick} 申请将主守护人身份转让给您",
        type=NotificationType.system,
        extra_data={"type": "guardian_transfer_request_v12", "transfer_id": transfer_id},
    ))
    # 通知被守护人
    db.add(Notification(
        user_id=managed_user_id,
        title="主守护人转让申请",
        content=f"{from_nick} 申请将主守护人身份转让给 {target_nick}",
        type=NotificationType.system,
        extra_data={"type": "guardian_transfer_request_v12", "transfer_id": transfer_id},
    ))

    await db.flush()
    return {
        "transfer_id": transfer_id,
        "managed_user_id": managed_user_id,
        "status": "pending",
        "expires_at": transfer.expires_at.isoformat(),
        "message": "转让申请已发起，等待接收者确认（v1.2 新流程）",
    }


@router.post("/api/guardian/v12/transfer/{transfer_id}/approve")
async def transfer_approve_v12(
    transfer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §7.2 通道 A] 接收者同意主守护人转让（v1.2 同意方变为接收者）"""
    transfer = await db.get(GuardianTransferRequest, transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="转让请求不存在")

    to_mgmt = await db.get(FamilyManagement, transfer.to_management_id)
    from_mgmt = await db.get(FamilyManagement, transfer.from_management_id)
    if not to_mgmt or not from_mgmt:
        raise HTTPException(status_code=404, detail="守护关系已失效")
    # 权限：当前用户必须是接收者
    if to_mgmt.manager_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有接收者本人可以确认")
    if transfer.status != "pending":
        raise HTTPException(status_code=400, detail=f"该请求已 {transfer.status}")
    if transfer.expires_at and transfer.expires_at < datetime.utcnow():
        transfer.status = "expired"
        await db.flush()
        raise HTTPException(status_code=400, detail="转让请求已过期")
    if from_mgmt.status != "active" or to_mgmt.status != "active":
        raise HTTPException(status_code=400, detail="守护关系已失效，无法完成转让")

    # 切换主守护人
    from_mgmt.is_primary_guardian = False
    from_mgmt.priority_order = 1
    to_mgmt.is_primary_guardian = True
    to_mgmt.priority_order = 0

    db.add(ManagementOperationLog(
        management_id=to_mgmt.id,
        operator_user_id=current_user.id,
        operation_type="primary_guardian_transferred_v12",
        operation_detail={
            "from_management_id": from_mgmt.id,
            "to_management_id": to_mgmt.id,
            "transfer_id": transfer_id,
        },
    ))

    transfer.status = "approved"
    transfer.approved_at = datetime.utcnow()

    # 通知三方
    managed_user = await db.get(User, transfer.managed_user_id)
    from_user = await db.get(User, from_mgmt.manager_user_id)
    managed_nick = managed_user.nickname if managed_user else "被守护人"
    from_nick = from_user.nickname if from_user else "原主守护人"
    to_nick = current_user.nickname or "新主守护人"

    msgs = [
        (from_mgmt.manager_user_id, "主守护人身份已转让", f"您已不再是 {managed_nick} 的主守护人，新主守护人为 {to_nick}"),
        (to_mgmt.manager_user_id, "您已成为主守护人", f"您已成为 {managed_nick} 的主守护人"),
        (transfer.managed_user_id, "主守护人已更新", f"您的主守护人已从 {from_nick} 转让给 {to_nick}"),
    ]
    for uid, title, content in msgs:
        db.add(Notification(
            user_id=uid, title=title, content=content,
            type=NotificationType.system,
            extra_data={"type": "guardian_transfer_done_v12", "transfer_id": transfer_id},
        ))

    await db.flush()
    return {
        "transfer_id": transfer_id,
        "status": "approved",
        "new_primary_management_id": to_mgmt.id,
        "message": "转让完成",
    }


@router.post("/api/guardian/v12/owner/direct-adjust")
async def owner_direct_adjust(
    payload: OwnerDirectAdjustRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §7.2 通道 B] 被守护人上帝视角直接调整守护关系"""
    target_mgmt = await db.get(FamilyManagement, payload.target_management_id)
    if not target_mgmt or target_mgmt.status != "active":
        raise HTTPException(status_code=404, detail="守护关系不存在或已失效")
    if target_mgmt.managed_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有被守护人本人可以使用上帝视角")

    if payload.action == "set_primary":
        # 把所有该被守护人的关系 is_primary 置 false，再把 target 置 true
        all_mgmts = (await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.managed_user_id == current_user.id,
                FamilyManagement.status == "active",
            )
        )).scalars().all()
        for m in all_mgmts:
            if m.id == target_mgmt.id:
                m.is_primary_guardian = True
                m.priority_order = 0
            else:
                if getattr(m, "is_primary_guardian", False):
                    m.is_primary_guardian = False
                    m.priority_order = 1
        db.add(ManagementOperationLog(
            management_id=target_mgmt.id,
            operator_user_id=current_user.id,
            operation_type="owner_set_primary_v12",
            operation_detail={"new_primary_management_id": target_mgmt.id},
        ))
        # 通知新主守护人
        db.add(Notification(
            user_id=target_mgmt.manager_user_id,
            title="您已成为主守护人",
            content=f"{current_user.nickname or '被守护人'} 直接指定您为主守护人",
            type=NotificationType.system,
            extra_data={"type": "owner_set_primary_v12"},
        ))
        await db.flush()
        return {"status": "ok", "action": "set_primary", "management_id": target_mgmt.id}

    elif payload.action == "remove_guardian":
        was_primary = bool(getattr(target_mgmt, "is_primary_guardian", False))
        target_mgmt.status = "inactive"
        if was_primary:
            target_mgmt.is_primary_guardian = False
            # 提升最早的另一个为主守护人
            others = (await db.execute(
                select(FamilyManagement).where(
                    FamilyManagement.managed_user_id == current_user.id,
                    FamilyManagement.status == "active",
                    FamilyManagement.id != target_mgmt.id,
                ).order_by(FamilyManagement.created_at.asc())
            )).scalars().all()
            if others:
                others[0].is_primary_guardian = True
                others[0].priority_order = 0
        db.add(ManagementOperationLog(
            management_id=target_mgmt.id,
            operator_user_id=current_user.id,
            operation_type="owner_remove_guardian_v12",
            operation_detail={"removed_management_id": target_mgmt.id},
        ))
        db.add(Notification(
            user_id=target_mgmt.manager_user_id,
            title="守护关系已解除",
            content=f"{current_user.nickname or '被守护人'} 解除了您的守护关系",
            type=NotificationType.system,
            extra_data={"type": "owner_remove_guardian_v12"},
        ))
        await db.flush()
        return {"status": "ok", "action": "remove_guardian", "management_id": target_mgmt.id}

    raise HTTPException(status_code=400, detail=f"未知 action: {payload.action}")


@router.post("/api/guardian/v12/managed/{managed_user_id}/proxy-pay")
async def set_proxy_pay(
    managed_user_id: int,
    payload: ProxyPaySwitchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §5.2] 主守护人开启/关闭"代付被守护人 AI 外呼额度"开关"""
    # 校验：当前用户必须是该被守护人的主守护人
    my_mgmt = (await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
            FamilyManagement.is_primary_guardian == True,
        )
    )).scalars().first()
    if not my_mgmt:
        raise HTTPException(status_code=403, detail="只有主守护人可设置代付开关")

    # upsert
    res = await db.execute(
        select(GuardianProxyPay).where(
            GuardianProxyPay.primary_guardian_user_id == current_user.id,
            GuardianProxyPay.managed_user_id == managed_user_id,
        )
    )
    rec = res.scalars().first()
    if not rec:
        rec = GuardianProxyPay(
            primary_guardian_user_id=current_user.id,
            managed_user_id=managed_user_id,
            enabled=bool(payload.enabled),
        )
        db.add(rec)
    else:
        rec.enabled = bool(payload.enabled)

    await db.flush()

    # 通知被守护人
    if payload.enabled:
        db.add(Notification(
            user_id=managed_user_id,
            title="AI 外呼额度代付已开启",
            content=f"您的 AI 外呼额度由主守护人 {current_user.nickname or ''} 代付中",
            type=NotificationType.system,
            extra_data={"type": "proxy_pay_enabled_v12"},
        ))
        await db.flush()

    return {"managed_user_id": managed_user_id, "enabled": bool(payload.enabled)}


@router.get("/api/guardian/v12/ai-call-quota")
async def get_ai_call_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §13.4] 查询本月 AI 外呼额度"""
    quotas = await _get_user_quotas(db, current_user.id)
    used = await _get_used_count(db, current_user.id, "ai_remind")
    total = quotas["ai_remind_quota"]
    if total < 0:
        remaining = -1
    else:
        remaining = max(0, total - used)
    return {
        "user_id": current_user.id,
        "is_paid_member": quotas["is_paid_member"],
        "plan_name": quotas["plan_name"],
        "total": total,
        "used": used,
        "remaining": remaining,
        "unlimited": total < 0,
    }


@router.get("/api/guardian/v12/emergency-quota")
async def get_emergency_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §6] 查询本月紧急 AI 呼叫额度（统一扣主守护人）"""
    quotas = await _get_user_quotas(db, current_user.id)
    used = await _get_used_count(db, current_user.id, "emergency_call")
    total = quotas["emergency_ai_call_count"]
    if total < 0:
        remaining = -1
    else:
        remaining = max(0, total - used)
    return {
        "user_id": current_user.id,
        "is_paid_member": quotas["is_paid_member"],
        "plan_name": quotas["plan_name"],
        "total": total,
        "used": used,
        "remaining": remaining,
        "low_quota_warning": (total > 0 and remaining <= 2 and remaining >= 0),
        "exhausted": (total >= 0 and remaining == 0),
        "unlimited": total < 0,
    }


@router.get("/api/guardian/v12/managed-quota-summary")
async def managed_quota_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §13] 会员中心本月配额概览（AI 外呼 / 紧急呼叫 / 守护他人）"""
    quotas = await _get_user_quotas(db, current_user.id)
    ai_used = await _get_used_count(db, current_user.id, "ai_remind")
    em_used = await _get_used_count(db, current_user.id, "emergency_call")
    managed_count = (await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )).scalar() or 0

    def _quota_item(total: int, used: int):
        if total < 0:
            return {"total": -1, "used": used, "remaining": -1, "unlimited": True, "ratio": 0}
        remaining = max(0, total - used)
        ratio = round((used / total) if total > 0 else 0, 2)
        return {"total": total, "used": used, "remaining": remaining, "unlimited": False, "ratio": ratio}

    return {
        "plan_name": quotas["plan_name"],
        "is_paid_member": quotas["is_paid_member"],
        "ai_remind": _quota_item(quotas["ai_remind_quota"], ai_used),
        "emergency_ai_call": _quota_item(quotas["emergency_ai_call_count"], em_used),
        "max_managed": _quota_item(quotas["max_managed"], int(managed_count)),
        "max_guardians": quotas["max_guardians"],
    }


@router.get("/api/guardian/v12/reminders/{managed_user_id}")
async def list_reminders_of_managed(
    managed_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §11.4] 提醒设置抽屉 - 列出该被守护人的全部 AI 外呼提醒（带权限过滤）

    权限矩阵：
    - 主守护人：可查看/编辑/删除"所有人为该被守护人设置的提醒"
    - 普通守护人：仅查看/编辑/删除"自己设置的"，对其他人设置的只读
    - 被守护人本人：可查看/编辑/删除所有人为自己设置的提醒
    """
    # 权限校验
    is_owner = current_user.id == managed_user_id
    is_primary = False
    is_guardian = False
    if not is_owner:
        my_mgmt = (await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == current_user.id,
                FamilyManagement.managed_user_id == managed_user_id,
                FamilyManagement.status == "active",
            )
        )).scalars().first()
        if not my_mgmt:
            raise HTTPException(status_code=403, detail="您不是该被守护人的守护人")
        is_guardian = True
        is_primary = bool(getattr(my_mgmt, "is_primary_guardian", False))

    res = await db.execute(
        select(AiCallReminder).where(
            AiCallReminder.target_user_id == managed_user_id
        ).order_by(AiCallReminder.created_at.desc())
    )
    items = []
    for r in res.scalars().all():
        setter = await db.get(User, r.setter_user_id)
        # 权限：can_edit
        if is_owner or is_primary:
            can_edit = True
        elif is_guardian:
            can_edit = (r.setter_user_id == current_user.id)
        else:
            can_edit = False
        items.append({
            "id": r.id,
            "setter_user_id": r.setter_user_id,
            "setter_nickname": setter.nickname if setter else None,
            "setter_is_me": r.setter_user_id == current_user.id,
            "target_user_id": r.target_user_id,
            "reminder_type": r.reminder_type,
            "title": r.title,
            "content": r.content,
            "schedule_cron": r.schedule_cron,
            "next_fire_at": r.next_fire_at.isoformat() if r.next_fire_at else None,
            "is_enabled": bool(r.is_enabled),
            "is_paused_by_quota": bool(r.is_paused_by_quota),
            "can_edit": can_edit,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    # 当前用户本月剩余 AI 外呼额度
    quotas = await _get_user_quotas(db, current_user.id)
    ai_used = await _get_used_count(db, current_user.id, "ai_remind")
    ai_total = quotas["ai_remind_quota"]
    remaining = -1 if ai_total < 0 else max(0, ai_total - ai_used)

    # 检查是否有代付："如果我是被守护人本人，看主守护人是否开启了代付"
    proxy_pay_payer = None
    if is_owner:
        primary = await _get_primary_guardian_mgmt(db, managed_user_id)
        if primary and await _is_proxy_pay_enabled(db, primary.manager_user_id, managed_user_id):
            payer_user = await db.get(User, primary.manager_user_id)
            proxy_pay_payer = payer_user.nickname if payer_user else "主守护人"

    return {
        "items": items,
        "total": len(items),
        "caller_is_owner": is_owner,
        "caller_is_primary_guardian": is_primary,
        "caller_is_guardian": is_guardian,
        "my_remaining_quota": remaining,
        "my_total_quota": ai_total,
        "proxy_pay_payer_nickname": proxy_pay_payer,
    }


@router.post("/api/guardian/v12/reminders")
async def create_reminder(
    payload: AiCallReminderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §5] 创建 AI 外呼提醒"""
    # 权限：current_user 是 target_user_id 本人 或 该被守护人的守护人
    if current_user.id != payload.target_user_id:
        my_mgmt = (await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == current_user.id,
                FamilyManagement.managed_user_id == payload.target_user_id,
                FamilyManagement.status == "active",
            )
        )).scalars().first()
        if not my_mgmt:
            raise HTTPException(status_code=403, detail="无权为该用户设置提醒")

    r = AiCallReminder(
        setter_user_id=current_user.id,
        target_user_id=payload.target_user_id,
        reminder_type=payload.reminder_type,
        title=payload.title,
        content=payload.content,
        schedule_cron=payload.schedule_cron,
        next_fire_at=payload.next_fire_at,
        is_enabled=True,
        is_paused_by_quota=False,
    )
    db.add(r)
    await db.flush()
    return {"id": r.id, "message": "已创建提醒"}


@router.delete("/api/guardian/v12/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除 AI 外呼提醒（权限：设置者、被守护人本人、主守护人）"""
    r = await db.get(AiCallReminder, reminder_id)
    if not r:
        raise HTTPException(status_code=404, detail="提醒不存在")
    # 权限
    if r.setter_user_id == current_user.id or r.target_user_id == current_user.id:
        pass
    else:
        my_mgmt = (await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == current_user.id,
                FamilyManagement.managed_user_id == r.target_user_id,
                FamilyManagement.status == "active",
                FamilyManagement.is_primary_guardian == True,
            )
        )).scalars().first()
        if not my_mgmt:
            raise HTTPException(status_code=403, detail="无权删除该提醒")
    await db.delete(r)
    await db.flush()
    return {"message": "已删除"}


@router.post("/api/guardian/v12/emergency/simulate-serial-call")
async def simulate_emergency_serial_call(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §6] 模拟紧急 AI 呼叫串行外呼（v1.2 统一扣主守护人）

    入参：{ managed_user_id, source_code? }
    """
    managed_user_id = payload.get("managed_user_id")
    source_code = payload.get("source_code", "health_data_abnormal")
    if not managed_user_id:
        raise HTTPException(status_code=400, detail="缺少 managed_user_id")

    # 触发源校验
    src = (await db.execute(
        select(EmergencyCallSource).where(
            EmergencyCallSource.source_code == source_code,
            EmergencyCallSource.is_enabled == True,
        )
    )).scalars().first()
    if not src:
        raise HTTPException(status_code=400, detail=f"触发源 {source_code} 不存在或已禁用")

    # 找主守护人
    primary = await _get_primary_guardian_mgmt(db, managed_user_id)
    if not primary:
        return {
            "managed_user_id": managed_user_id,
            "source_code": source_code,
            "call_plan": [],
            "fallback_to_push_sms": True,
            "reason": "无主守护人，降级推送+短信",
        }

    # 主守护人额度
    primary_quotas = await _get_user_quotas(db, primary.manager_user_id)
    em_total = primary_quotas["emergency_ai_call_count"]
    em_used = await _get_used_count(db, primary.manager_user_id, "emergency_call")
    em_remaining = -1 if em_total < 0 else max(0, em_total - em_used)

    if em_total >= 0 and em_remaining == 0:
        # 主守护人额度耗尽 → 全部降级推送+短信
        return {
            "managed_user_id": managed_user_id,
            "source_code": source_code,
            "primary_guardian_user_id": primary.manager_user_id,
            "call_plan": [],
            "fallback_to_push_sms": True,
            "reason": "主守护人本月额度已耗尽，降级推送+短信",
        }

    # 串行外呼计划
    res = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == managed_user_id,
            FamilyManagement.status == "active",
        ).order_by(
            FamilyManagement.is_primary_guardian.desc(),
            FamilyManagement.priority_order.asc().nullslast(),
            FamilyManagement.created_at.asc(),
        )
    )
    guardians = res.scalars().all()
    call_plan = []
    for idx, mgmt in enumerate(guardians):
        manager = await db.get(User, mgmt.manager_user_id)
        call_plan.append({
            "order": idx + 1,
            "management_id": mgmt.id,
            "manager_user_id": mgmt.manager_user_id,
            "manager_nickname": manager.nickname if manager else None,
            "is_primary": bool(getattr(mgmt, "is_primary_guardian", False)),
            "ring_timeout_seconds": RING_NO_ANSWER_SECONDS,
        })

    # 模拟：第一顺位接通 → 扣主守护人 1 次（v1.2 统一规则）
    if call_plan:
        if em_total >= 0:  # 非不限
            db.add(GuardianAlertQuotaUsage(
                user_id=primary.manager_user_id,
                managed_user_id=managed_user_id,
                used_at=datetime.utcnow(),
                call_type="emergency_call",
            ))
        await db.flush()

    return {
        "managed_user_id": managed_user_id,
        "source_code": source_code,
        "source_name": src.source_name,
        "primary_guardian_user_id": primary.manager_user_id,
        "call_plan": call_plan,
        "charged_user_id": primary.manager_user_id,
        "charged_count": 1 if call_plan else 0,
        "primary_quota_remaining": em_remaining - 1 if em_remaining > 0 else em_remaining,
        "low_quota_warning": (em_remaining > 0 and em_remaining - 1 <= 2),
        "fallback_to_push_sms": False,
        "message": "紧急 AI 呼叫已扣主守护人 1 次额度（v1.2 统一规则）",
    }


@router.get("/api/guardian/v12/invitations/records")
async def list_invitation_records_v12(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §11.5] 邀请记录列表（我发起的 + 别人邀请我的）"""
    # 我发起的（FamilyInvitation: inviter_user_id = me）
    my_sent = (await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.inviter_user_id == current_user.id
        ).order_by(FamilyInvitation.created_at.desc())
    )).scalars().all()

    # 别人邀请我的（反向：FamilyInvitation.accepted_by 可能是 me；或 ReverseGuardianInvitation 中 invitee_phone 是 my phone）
    others_invite = []
    if current_user.phone:
        try:
            r1 = (await db.execute(
                select(ReverseGuardianInvitation).where(
                    or_(
                        ReverseGuardianInvitation.invitee_phone == current_user.phone,
                        ReverseGuardianInvitation.accepted_by == current_user.id,
                    )
                ).order_by(ReverseGuardianInvitation.created_at.desc())
            )).scalars().all()
            others_invite = list(r1)
        except Exception:
            others_invite = []

    status_labels = {
        "pending": ("待确认", "info"),
        "accepted": ("已生效", "success"),
        "expired": ("已过期", "warning"),
        "cancelled": ("已作废", "gray"),
    }
    now = datetime.utcnow()

    sent_items = []
    for inv in my_sent:
        actual_status = inv.status
        if actual_status == "pending" and inv.expires_at and inv.expires_at < now:
            actual_status = "expired"
        label, color = status_labels.get(actual_status, (actual_status, "gray"))
        sent_items.append({
            "id": inv.id,
            "direction": "sent",
            "invite_code": inv.invite_code,
            "member_id": inv.member_id,
            "relation_type": getattr(inv, "relation_type", None),
            "status": actual_status,
            "status_label": label,
            "status_color": color,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "can_reinvite": actual_status in ("expired", "cancelled"),
        })

    received_items = []
    for inv in others_invite:
        actual_status = inv.status
        if actual_status == "pending" and getattr(inv, "expires_at", None) and inv.expires_at < now:
            actual_status = "expired"
        label, color = status_labels.get(actual_status, (actual_status, "gray"))
        received_items.append({
            "id": inv.id,
            "direction": "received",
            "invite_code": getattr(inv, "invite_code", None),
            "inviter_user_id": getattr(inv, "inviter_user_id", None),
            "relation_type": getattr(inv, "relation_type", None),
            "status": actual_status,
            "status_label": label,
            "status_color": color,
            "expires_at": inv.expires_at.isoformat() if getattr(inv, "expires_at", None) else None,
            "created_at": inv.created_at.isoformat() if getattr(inv, "created_at", None) else None,
            "can_reinvite": False,
        })

    all_items = sent_items + received_items
    all_items.sort(key=lambda x: x["created_at"] or "", reverse=True)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": all_items[start:end],
        "total": len(all_items),
        "page": page,
        "page_size": page_size,
        "sent_count": len(sent_items),
        "received_count": len(received_items),
    }


# ─────────── 后台管理接口 ───────────


@admin_router.get("/emergency-sources")
async def admin_list_emergency_sources(
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2 §12.3] 紧急呼叫触发源列表"""
    res = await db.execute(
        select(EmergencyCallSource).order_by(
            EmergencyCallSource.sort_order.asc(),
            EmergencyCallSource.id.asc(),
        )
    )
    items = []
    for s in res.scalars().all():
        items.append({
            "id": s.id,
            "source_code": s.source_code,
            "source_name": s.source_name,
            "description": s.description,
            "is_enabled": bool(s.is_enabled),
            "is_builtin": bool(s.is_builtin),
            "trigger_condition": s.trigger_condition,
            "applicable_device_type": s.applicable_device_type,
            "sort_order": s.sort_order,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return {"items": items, "total": len(items)}


@admin_router.post("/emergency-sources")
async def admin_create_emergency_source(
    payload: EmergencySourceCreateRequest,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2] 新增紧急呼叫触发源"""
    exists = (await db.execute(
        select(EmergencyCallSource).where(EmergencyCallSource.source_code == payload.source_code)
    )).scalars().first()
    if exists:
        raise HTTPException(status_code=400, detail=f"触发源编码已存在：{payload.source_code}")
    s = EmergencyCallSource(
        source_code=payload.source_code,
        source_name=payload.source_name,
        description=payload.description,
        is_enabled=payload.is_enabled,
        is_builtin=False,
        trigger_condition=payload.trigger_condition,
        applicable_device_type=payload.applicable_device_type,
        sort_order=payload.sort_order,
    )
    db.add(s)
    await db.flush()
    await db.refresh(s)
    return {"id": s.id, "source_code": s.source_code}


@admin_router.put("/emergency-sources/{source_id}")
async def admin_update_emergency_source(
    source_id: int,
    payload: EmergencySourceUpdateRequest,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2] 编辑紧急呼叫触发源（内置只允许改启停）"""
    s = await db.get(EmergencyCallSource, source_id)
    if not s:
        raise HTTPException(status_code=404, detail="触发源不存在")
    data = payload.model_dump(exclude_unset=True)
    if s.is_builtin:
        # 内置仅允许改 is_enabled
        allowed = {"is_enabled", "sort_order"}
        data = {k: v for k, v in data.items() if k in allowed}
    for k, v in data.items():
        setattr(s, k, v)
    await db.flush()
    return {"id": s.id, "message": "已更新"}


@admin_router.delete("/emergency-sources/{source_id}")
async def admin_delete_emergency_source(
    source_id: int,
    _=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1.2] 删除非内置触发源"""
    s = await db.get(EmergencyCallSource, source_id)
    if not s:
        raise HTTPException(status_code=404, detail="触发源不存在")
    if s.is_builtin:
        raise HTTPException(status_code=400, detail="内置触发源不可删除，仅可禁用")
    await db.delete(s)
    await db.flush()
    return {"message": "已删除"}
