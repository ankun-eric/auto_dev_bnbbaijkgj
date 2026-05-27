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
from app.schemas.reverse_guardian import (
    AcceptReverseInviteResponse,
    GuardianCountResponse,
    GuardianItem,
    MyGuardiansResponse,
    RemoveGuardianRequest,
    RemoveGuardianResponse,
    ReverseInviteCreateResponse,
    ReverseInviteDetailResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reverse-guardian", tags=["反向守护"])

INVITE_EXPIRE_HOURS = 24
MAX_INVITE_USES = 3
BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


@router.get("/my-guardians", response_model=MyGuardiansResponse)
async def list_my_guardians(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取「守护我的人」列表。"""
    result = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_user_id == current_user.id,
            FamilyManagement.status == "active",
        ).order_by(FamilyManagement.created_at.desc())
    )
    managements = list(result.scalars().all())

    items: list[GuardianItem] = []
    for mgmt in managements:
        guardian_result = await db.execute(
            select(User).where(User.id == mgmt.manager_user_id)
        )
        guardian = guardian_result.scalar_one_or_none()
        items.append(GuardianItem(
            management_id=mgmt.id,
            user_id=mgmt.manager_user_id,
            nickname=guardian.nickname if guardian else None,
            avatar=guardian.avatar if guardian else None,
            guardian_since=mgmt.created_at,
            permission_scope="全部健康信息",
            last_viewed_at=None,
        ))

    return MyGuardiansResponse(items=items, total=len(items))


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
    active_result = await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.managed_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    active_count = active_result.scalar() or 0

    now = datetime.utcnow()
    pending_result = await db.execute(
        select(func.count(ReverseGuardianInvitation.id)).where(
            ReverseGuardianInvitation.invitee_user_id == current_user.id,
            ReverseGuardianInvitation.status == "pending",
            ReverseGuardianInvitation.used_count < ReverseGuardianInvitation.max_uses,
            ReverseGuardianInvitation.expires_at > now,
        )
    )
    pending_count = pending_result.scalar() or 0

    return GuardianCountResponse(
        count=active_count,
        active_count=active_count,
        pending_count=pending_count,
        total_count=active_count + pending_count,
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
            FamilyMember.status == "active",
        )
    )
    for fm in fm_result.scalars().all():
        fm.status = "removed"

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """被守护人生成反向邀请链接。"""
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
    )
    db.add(invitation)
    await db.flush()

    qr_url = f"{BASE_URL}/family-invite?code={invite_code}&type=reverse"
    logger.info("[reverse-guardian/invite] user=%s code=%s", current_user.id, invite_code)
    return ReverseInviteCreateResponse(
        invite_code=invite_code,
        qr_url=qr_url,
        expires_at=expires_at,
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

    existing = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.managed_user_id == invitation.invitee_user_id,
            FamilyManagement.status == "active",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已是对方的守护者")

    # 查找或创建被守护人在守护者名下的 FamilyMember 档案
    fm_result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.member_user_id == invitation.invitee_user_id,
            FamilyMember.status == "active",
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
            status="active",
            is_self=False,
        )
        db.add(family_member)
        await db.flush()

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
