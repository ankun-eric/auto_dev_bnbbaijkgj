"""反向守护邀请接口。

被守护人主动生成邀请链接，邀请他人成为自己的守护者。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    FamilyManagement,
    FamilyMember,
    HealthProfile,
    ManagementOperationLog,
    Notification,
    NotificationType,
    ReverseGuardianInvitation,
    SystemMessage,
    User,
)
from app.services.family_bind_dedup_service import is_duplicate_bind
from app.schemas.reverse_guardian import (
    AcceptReverseInviteResponse,
    CancelReverseInviteRequest,
    CancelReverseInviteResponse,
    GuardianCountResponse,
    GuardianItem,
    MyGuardiansResponse,
    RemoveGuardianRequest,
    RemoveGuardianResponse,
    ReverseInviteCreateResponse,
    ReverseInviteDetailResponse,
)
from app.models.membership_plan import FreeMemberQuota, MembershipPlan, UserMembershipSub

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reverse-guardian", tags=["反向守护"])

INVITE_EXPIRE_HOURS = 24
MAX_INVITE_USES = 3
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

# [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 错误码常量
ERR_GUARDIAN_LIMIT_REACHED = "GUARDIAN_LIMIT_REACHED"
ERR_WARD_LIMIT_REACHED = "WARD_LIMIT_REACHED"


# ─────────── 会员配置 helpers（守护我的人卡片专用） ───────────


async def _get_user_membership_config(db: AsyncSession, user_id: int) -> dict:
    """[PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 获取当前用户的会员配置信息。

    返回字段：
    - max_managed: 管理上限（我守护的人 Y）
    - max_managed_by: 被管理上限（守护我的人 Y）
    - is_top_level: 是否顶级会员（按 max_managed_by 是否为该字段在所有 active 套餐中最大值，
      或者 max_managed_by >= 9999 视为无上限即顶级）
    - is_unlimited: 是否无上限（max_managed_by >= 9999 或 -1）
    - member_level: 会员等级名称
    """
    now = datetime.utcnow()
    sub_res = await db.execute(
        select(UserMembershipSub).where(
            UserMembershipSub.user_id == user_id,
            UserMembershipSub.status == "active",
            UserMembershipSub.expire_at > now,
        ).order_by(UserMembershipSub.expire_at.desc())
    )
    sub = sub_res.scalars().first()

    if sub:
        plan = await db.get(MembershipPlan, sub.plan_id)
        if plan:
            mm_by = int(plan.max_managed_by or 0)
            mm = int(plan.max_managed or 0)
            # 顶级判断：max_managed_by 为所有 active 套餐中最大值，或 unlimited
            is_unlimited = mm_by >= 9999 or mm_by < 0
            # 查询所有 active 套餐中最大的 max_managed_by
            max_res = await db.execute(
                select(func.max(MembershipPlan.max_managed_by)).where(
                    MembershipPlan.is_active == True  # noqa: E712
                )
            )
            top_mm_by = int(max_res.scalar() or 0)
            is_top_level = is_unlimited or (mm_by >= top_mm_by and top_mm_by > 0)
            return {
                "max_managed": mm if mm > 0 else 3,
                "max_managed_by": mm_by if mm_by > 0 else 3,
                "is_top_level": bool(is_top_level),
                "is_unlimited": bool(is_unlimited),
                "member_level": plan.name or "paid",
            }

    # 免费会员
    quota_res = await db.execute(
        select(FreeMemberQuota).order_by(FreeMemberQuota.id.asc())
    )
    quota = quota_res.scalars().first()
    if quota:
        return {
            "max_managed": int(quota.max_managed or 3),
            "max_managed_by": int(quota.max_managed_by or 3),
            "is_top_level": False,
            "is_unlimited": False,
            "member_level": "free",
        }
    return {
        "max_managed": 3,
        "max_managed_by": 3,
        "is_top_level": False,
        "is_unlimited": False,
        "member_level": "free",
    }


async def _count_my_guardians_x(db: AsyncSession, user_id: int) -> tuple[int, int, int]:
    """[PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 计算「守护我的人」X 值。

    X = active_count + pending_count（已绑定 + 邀请中）
    返回 (active_count, pending_count, total_x)
    """
    active_res = await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.managed_user_id == user_id,
            FamilyManagement.status == "active",
        )
    )
    active_count = int(active_res.scalar() or 0)

    now = datetime.utcnow()
    pending_res = await db.execute(
        select(func.count(ReverseGuardianInvitation.id)).where(
            ReverseGuardianInvitation.invitee_user_id == user_id,
            ReverseGuardianInvitation.status == "pending",
            ReverseGuardianInvitation.used_count < ReverseGuardianInvitation.max_uses,
            ReverseGuardianInvitation.expires_at > now,
        )
    )
    pending_count = int(pending_res.scalar() or 0)
    return active_count, pending_count, active_count + pending_count


async def _count_bound_others(db: AsyncSession, user_id: int) -> int:
    """[PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 计算「我守护的人」X 口径（不含本人，仅已绑定）。"""
    res = await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.manager_user_id == user_id,
            FamilyManagement.status == "active",
        )
    )
    return int(res.scalar() or 0)


@router.get("/my-guardians", response_model=MyGuardiansResponse)
async def list_my_guardians(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 获取「守护我的人」列表。

    包含两部分：
    - active 项：已生效的守护关系（FamilyManagement.status=active）
    - pending 项：当前用户发出的待确认反向邀请（pending 且未过期未用满）
    """
    items: list[GuardianItem] = []
    # active 项
    result = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == current_user.id,
            FamilyManagement.status == "active",
        ).order_by(FamilyManagement.created_at.desc())
    )
    managements = list(result.scalars().all())
    active_count = 0
    for mgmt in managements:
        guardian_result = await db.execute(
            select(User).where(User.id == mgmt.manager_user_id)
        )
        guardian = guardian_result.scalar_one_or_none()
        items.append(GuardianItem(
            item_type="active",
            management_id=mgmt.id,
            user_id=mgmt.manager_user_id,
            nickname=guardian.nickname if guardian else None,
            avatar=guardian.avatar if guardian else None,
            guardian_since=mgmt.created_at,
            permission_scope="全部健康信息",
            last_viewed_at=None,
        ))
        active_count += 1

    # pending 项
    now = datetime.utcnow()
    pending_res = await db.execute(
        select(ReverseGuardianInvitation).where(
            ReverseGuardianInvitation.invitee_user_id == current_user.id,
            ReverseGuardianInvitation.status == "pending",
            ReverseGuardianInvitation.used_count < ReverseGuardianInvitation.max_uses,
            ReverseGuardianInvitation.expires_at > now,
        ).order_by(ReverseGuardianInvitation.created_at.desc())
    )
    pending_count = 0
    for inv in pending_res.scalars().all():
        items.append(GuardianItem(
            item_type="pending",
            invitation_id=inv.id,
            invite_code=inv.invite_code,
            nickname=inv.guardian_name or "待确认",
            permission_scope=inv.relation_type or "待确认",
            invite_expires_at=inv.expires_at,
            invite_status="pending",
            guardian_since=inv.created_at,
            guardian_name=inv.guardian_name,
        ))
        pending_count += 1

    return MyGuardiansResponse(
        items=items, total=len(items),
        active_count=active_count, pending_count=pending_count,
    )


@router.get("/guardian-count", response_model=GuardianCountResponse)
async def get_guardian_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527] 获取守护我的人数量。

    返回结构升级为：
    - count: 兼容旧前端，等于 active_count
    - active_count: 已生效的守护关系数
    - pending_count: 当前用户发出的未过期且未用完的反向邀请数（待确认）
    - total_count: active_count + pending_count
    """
    # [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 守护我的人 X 与上限
    active_count, pending_count, _ = await _count_my_guardians_x(db, current_user.id)
    cfg = await _get_user_membership_config(db, current_user.id)
    bound_others = await _count_bound_others(db, current_user.id)

    return GuardianCountResponse(
        count=active_count,
        active_count=active_count,
        pending_count=pending_count,
        total_count=active_count + pending_count,
        max_guardians_for_me=int(cfg["max_managed_by"]),
        max_guardians_by_me=int(cfg["max_managed"]),
        bound_others_count=bound_others,
        is_top_level=bool(cfg["is_top_level"]),
        is_unlimited=bool(cfg["is_unlimited"]),
        member_level=str(cfg["member_level"]),
    )


@router.post("/remove", response_model=RemoveGuardianResponse)
async def remove_guardian(
    body: RemoveGuardianRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """被守护人单方面解除守护关系。"""
    result = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.id == body.management_id,
            FamilyManagement.managed_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    mgmt = result.scalar_one_or_none()
    if not mgmt:
        raise HTTPException(status_code=404, detail="守护关系不存在或无权操作")

    mgmt.status = "cancelled"
    mgmt.cancelled_at = datetime.utcnow()
    mgmt.cancelled_by = current_user.id

    fm_result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == mgmt.manager_user_id,
            FamilyMember.member_user_id == current_user.id,
            FamilyMember.status == "bound",
        )
    )
    for fm in fm_result.scalars().all():
        fm.status = "deleted"
        fm.sub_status = "self_deleted"
        fm.status_changed_at = datetime.utcnow()
        fm.status_changed_by = current_user.id
        fm.status_reason = "reverse_guardian_unbind"

    log = ManagementOperationLog(
        management_id=mgmt.id,
        operator_user_id=current_user.id,
        operation_type="reverse_remove_guardian",
        operation_detail={"removed_guardian_user_id": mgmt.manager_user_id},
    )
    db.add(log)

    guardian_result = await db.execute(
        select(User).where(User.id == mgmt.manager_user_id)
    )
    guardian = guardian_result.scalar_one_or_none()
    managed_name = current_user.nickname or current_user.phone or "对方"

    db.add(Notification(
        user_id=mgmt.manager_user_id,
        title="守护关系已解除",
        content=f"{managed_name} 已解除与您的守护关系",
        type=NotificationType.system,
        extra_data={
            "type": "family_management",
            "action": "reverse_guardian_removed",
            "management_id": mgmt.id,
        },
    ))
    db.add(Notification(
        user_id=current_user.id,
        title="已解除守护关系",
        content=f"您已成功解除与 {guardian.nickname or guardian.phone or '对方'} 的守护关系" if guardian else "您已成功解除守护关系",
        type=NotificationType.system,
        extra_data={
            "type": "family_management",
            "action": "reverse_guardian_removed_self",
            "management_id": mgmt.id,
        },
    ))

    await db.flush()
    logger.info("[reverse-guardian/remove] user=%s removed guardian=%s mgmt=%s",
                current_user.id, mgmt.manager_user_id, mgmt.id)
    return RemoveGuardianResponse(message="已解除守护关系")


@router.post("/invite", response_model=ReverseInviteCreateResponse)
async def create_reverse_invite(
    relation_type: Optional[str] = Body(None, embed=True),
    guardian_name: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """被守护人生成反向邀请链接。

    [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 校验 X<Y（守护者总数<被管理上限），
    超额时返回 GUARDIAN_LIMIT_REACHED 错误码（HTTP 400）。

    [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 新增「名字」参数（去首尾空格后非空即可，
    与家庭成员邀请规则一致），存入 ReverseGuardianInvitation.guardian_name。
    """
    # [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 名字归一化：去首尾空格
    normalized_name = (guardian_name or "").strip() or None
    # 先把过期的 pending 清掉，再取消旧 pending（让出名额）
    pending_result = await db.execute(
        select(ReverseGuardianInvitation).where(
            ReverseGuardianInvitation.invitee_user_id == current_user.id,
            ReverseGuardianInvitation.status == "pending",
        )
    )
    for old_inv in pending_result.scalars().all():
        if old_inv.expires_at < datetime.utcnow():
            old_inv.status = "expired"
        else:
            old_inv.status = "cancelled"
    await db.flush()

    # X<Y 校验：active + 剩余 pending（已全部取消，故为 0）
    active_count, pending_count, total_x = await _count_my_guardians_x(db, current_user.id)
    cfg = await _get_user_membership_config(db, current_user.id)
    y_limit = int(cfg["max_managed_by"])
    is_unlimited = bool(cfg["is_unlimited"])
    if not is_unlimited and total_x >= y_limit:
        raise HTTPException(
            status_code=400,
            detail={
                "code": ERR_GUARDIAN_LIMIT_REACHED,
                "message": f"守护者已达上限（{total_x}/{y_limit}），请先升级会员或解绑现有守护者",
                "x": total_x,
                "y": y_limit,
            },
        )

    invite_code = uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=INVITE_EXPIRE_HOURS)

    invitation = ReverseGuardianInvitation(
        invite_code=invite_code,
        invitee_user_id=current_user.id,
        status="pending",
        max_uses=MAX_INVITE_USES,
        used_count=0,
        expires_at=expires_at,
        relation_type=relation_type,
        guardian_name=normalized_name,
    )
    db.add(invitation)
    await db.flush()

    qr_url = f"{BASE_URL}/family-invite?code={invite_code}&type=reverse"
    logger.info("[reverse-guardian/invite] user=%s code=%s name=%s",
                current_user.id, invite_code, normalized_name)
    return ReverseInviteCreateResponse(
        invite_code=invite_code,
        qr_url=qr_url,
        expires_at=expires_at,
        guardian_name=normalized_name,
    )


@router.get("/invite/{invite_code}", response_model=ReverseInviteDetailResponse)
async def get_reverse_invite_detail(
    invite_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看反向邀请详情。"""
    result = await db.execute(
        select(ReverseGuardianInvitation).where(
            ReverseGuardianInvitation.invite_code == invite_code
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在")

    if invitation.status == "pending" and invitation.expires_at < datetime.utcnow():
        invitation.status = "expired"
        await db.flush()

    invitee_result = await db.execute(
        select(User).where(User.id == invitation.invitee_user_id)
    )
    invitee = invitee_result.scalar_one_or_none()

    # 查询邀请人(invitee_user_id)的主健康档案获取真实姓名
    invitee_hp_result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == invitation.invitee_user_id,
            HealthProfile.family_member_id.is_(None),
        )
    )
    invitee_main_hp = invitee_hp_result.scalar_one_or_none()
    inviter_real_name = invitee_main_hp.name if invitee_main_hp else None

    check_result: str | None = None
    if invitation.status == "expired" or (invitation.status == "pending" and invitation.expires_at < datetime.utcnow()):
        check_result = "expired"
    elif invitation.status != "pending":
        check_result = invitation.status
    elif invitation.used_count >= invitation.max_uses:
        check_result = "full"
    elif invitation.invitee_user_id == current_user.id:
        check_result = "self_invite"
    else:
        existing = await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == current_user.id,
                FamilyManagement.managed_user_id == invitation.invitee_user_id,
                FamilyManagement.status == "active",
            )
        )
        if existing.scalar_one_or_none():
            check_result = "already_guardian"

    return ReverseInviteDetailResponse(
        invite_code=invitation.invite_code,
        status=invitation.status,
        invitee_user_id=invitation.invitee_user_id,
        invitee_nickname=invitee.nickname if invitee else None,
        invitee_avatar=invitee.avatar if invitee else None,
        inviter_real_name=inviter_real_name,
        relation_type=invitation.relation_type,
        guardian_name=invitation.guardian_name,
        max_uses=invitation.max_uses,
        used_count=invitation.used_count,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        check_result=check_result,
    )


@router.post("/invite/{invite_code}/accept", response_model=AcceptReverseInviteResponse)
async def accept_reverse_invite(
    invite_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """接受反向邀请，成为守护者。"""
    result = await db.execute(
        select(ReverseGuardianInvitation).where(
            ReverseGuardianInvitation.invite_code == invite_code
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在")

    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="该邀请已失效")
    if invitation.expires_at < datetime.utcnow():
        invitation.status = "expired"
        await db.flush()
        raise HTTPException(status_code=400, detail="邀请已过期")
    if invitation.used_count >= invitation.max_uses:
        raise HTTPException(status_code=400, detail="该邀请已达使用上限")
    if invitation.invitee_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能接受自己发出的邀请")

    # [BUGFIX-FAMILY-DUPLICATE-BIND-V1 2026-06-02] 复用统一判重逻辑，
    # 同管理者名下不能重复绑定同一被守护人（用户 ID 或手机号任一命中即拦截）。
    invitee_phone_res = await db.execute(
        select(User.phone).where(User.id == invitation.invitee_user_id)
    )
    invitee_phone = invitee_phone_res.scalar_one_or_none()
    if await is_duplicate_bind(
        db,
        manager_user_id=current_user.id,
        managed_user_id=invitation.invitee_user_id,
        managed_phone=invitee_phone,
    ):
        raise HTTPException(status_code=400, detail="您已是对方的守护者")

    # 查找或创建被守护人在守护者名下的 FamilyMember 档案
    fm_result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.member_user_id == invitation.invitee_user_id,
            FamilyMember.status == "bound",
        )
    )
    family_member = fm_result.scalar_one_or_none()

    invitee_result = await db.execute(
        select(User).where(User.id == invitation.invitee_user_id)
    )
    invitee = invitee_result.scalar_one_or_none()

    if not family_member:
        family_member = FamilyMember(
            user_id=current_user.id,
            member_user_id=invitation.invitee_user_id,
            relationship_type="other",
            nickname=invitee.nickname if invitee else None,
            status="bound",
            sub_status="bound",
            is_self=False,
        )
        db.add(family_member)
        await db.flush()

    # [BUGFIX-FAMILY-DUPLICATE-BIND-V1 2026-06-02] 写库前兜底再判一次重，防并发。
    if await is_duplicate_bind(
        db,
        manager_user_id=current_user.id,
        managed_user_id=invitation.invitee_user_id,
        managed_phone=invitee_phone,
    ):
        raise HTTPException(status_code=400, detail="您已是对方的守护者")

    management = FamilyManagement(
        manager_user_id=current_user.id,
        managed_user_id=invitation.invitee_user_id,
        managed_member_id=family_member.id,
        status="active",
    )
    db.add(management)
    await db.flush()

    invitation.used_count += 1
    if invitation.used_count >= invitation.max_uses:
        invitation.status = "fulfilled"

    log = ManagementOperationLog(
        management_id=management.id,
        operator_user_id=current_user.id,
        operation_type="accept_reverse_invitation",
        operation_detail={"invite_code": invite_code},
    )
    db.add(log)

    acceptor_name = current_user.nickname or current_user.phone or "对方"
    invitee_name = invitee.nickname or invitee.phone or "对方" if invitee else "对方"

    db.add(Notification(
        user_id=invitation.invitee_user_id,
        title="有人成为了您的守护者",
        content=f"{acceptor_name} 已接受您的邀请，成为您的守护者",
        type=NotificationType.system,
        extra_data={
            "type": "family_management",
            "action": "reverse_invitation_accepted",
            "management_id": management.id,
        },
    ))
    db.add(SystemMessage(
        message_type="reverse_invite_accepted",
        recipient_user_id=invitation.invitee_user_id,
        sender_user_id=current_user.id,
        title="新守护者加入",
        content=f"{acceptor_name} 已成为您的守护者，可在第一时间收到您的健康提醒",
        related_business_id=str(management.id),
        related_business_type="family_management",
        click_action="/my-guardians",
    ))
    db.add(SystemMessage(
        message_type="reverse_invite_accepted",
        recipient_user_id=current_user.id,
        sender_user_id=invitation.invitee_user_id,
        title="已成功守护家人",
        content=f"您已成功守护 {invitee_name}，可在第一时间收到对方的健康提醒",
        related_business_id=str(management.id),
        related_business_type="family_management",
        click_action="/family-bindlist",
    ))

    await db.flush()
    logger.info("[reverse-guardian/accept] guardian=%s managed=%s mgmt=%s code=%s",
                current_user.id, invitation.invitee_user_id, management.id, invite_code)
    return AcceptReverseInviteResponse(message="已成为守护者", management_id=management.id)


@router.post("/invite/cancel", response_model=CancelReverseInviteResponse)
async def cancel_reverse_invite(
    payload: CancelReverseInviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 取消反向邀请，释放名额。

    要求：
    - invitation_id 或 invite_code 至少传一个
    - 邀请必须属于当前用户（invitee_user_id == current_user.id）
    - 仅 status=pending 可取消
    """
    if not payload.invitation_id and not payload.invite_code:
        raise HTTPException(status_code=400, detail="invitation_id 或 invite_code 至少传一个")

    inv: ReverseGuardianInvitation | None = None
    if payload.invitation_id:
        inv = await db.get(ReverseGuardianInvitation, payload.invitation_id)
    elif payload.invite_code:
        res = await db.execute(
            select(ReverseGuardianInvitation).where(
                ReverseGuardianInvitation.invite_code == payload.invite_code
            )
        )
        inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=404, detail="邀请记录不存在")
    if inv.invitee_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能取消自己发起的邀请")
    if inv.status != "pending":
        raise HTTPException(status_code=400, detail=f"当前状态 {inv.status} 不可取消")
    inv.status = "cancelled"
    await db.flush()
    logger.info("[reverse-guardian/invite/cancel] user=%s invitation=%s",
                current_user.id, inv.id)
    return CancelReverseInviteResponse(
        invitation_id=inv.id,
        status="cancelled",
        message="邀请已取消",
    )
