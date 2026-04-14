import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    FamilyInvitation,
    FamilyManagement,
    FamilyMember,
    HealthProfile,
    ManagementOperationLog,
    Notification,
    NotificationType,
    SystemMessage,
    User,
)
from app.schemas.family_management import (
    FamilyManagementResponse,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationCreateResponse,
    InvitationDetailResponse,
    ManagedByResponse,
    OperationLogResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["家庭健康档案共管"])

INVITATION_EXPIRE_HOURS = 24
MAX_MANAGED_COUNT = 10
MAX_MANAGED_BY_COUNT = 3


@router.post("/api/family/invitation", response_model=InvitationCreateResponse)
async def create_invitation(
    data: InvitationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member_result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == data.member_id,
            FamilyMember.user_id == current_user.id,
            FamilyMember.status == "active",
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在或不属于当前用户")

    managed_count_result = await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    managed_count = managed_count_result.scalar() or 0
    if managed_count >= MAX_MANAGED_COUNT:
        raise HTTPException(status_code=400, detail=f"管理人数已达上限（{MAX_MANAGED_COUNT}人）")

    active_mgmt_result = await db.execute(
        select(FamilyManagement).where(
            FamilyManagement.managed_member_id == data.member_id,
            FamilyManagement.status == "active",
        )
    )
    if active_mgmt_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该成员已有激活的共管关系")

    pending_result = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.member_id == data.member_id,
            FamilyInvitation.inviter_user_id == current_user.id,
            FamilyInvitation.status == "pending",
        )
    )
    for old_inv in pending_result.scalars().all():
        old_inv.status = "cancelled"

    invite_code = uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=INVITATION_EXPIRE_HOURS)

    invitation = FamilyInvitation(
        invite_code=invite_code,
        inviter_user_id=current_user.id,
        member_id=data.member_id,
        status="pending",
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()

    qr_url = f"/api/family/invitation/{invite_code}"
    qr_content_url = f"https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-auth?code={invite_code}"

    return InvitationCreateResponse(
        invite_code=invite_code,
        qr_url=qr_url,
        qr_content_url=qr_content_url,
        expires_at=expires_at,
    )


@router.get("/api/family/invitation/{code}", response_model=InvitationDetailResponse)
async def get_invitation_detail(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyInvitation).where(FamilyInvitation.invite_code == code)
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="邀请不存在")

    inviter_result = await db.execute(
        select(User).where(User.id == invitation.inviter_user_id)
    )
    inviter = inviter_result.scalar_one_or_none()

    member_result = await db.execute(
        select(FamilyMember).where(FamilyMember.id == invitation.member_id)
    )
    member = member_result.scalar_one_or_none()

    status = invitation.status
    if status == "pending" and invitation.expires_at < datetime.utcnow():
        status = "expired"
        invitation.status = "expired"
        await db.flush()

    return InvitationDetailResponse(
        invite_code=invitation.invite_code,
        status=status,
        inviter_nickname=inviter.nickname if inviter else None,
        member_nickname=member.nickname if member else None,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.post("/api/family/invitation/{code}/accept")
async def accept_invitation(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyInvitation).where(FamilyInvitation.invite_code == code)
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

    if invitation.inviter_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能接受自己发出的邀请")

    managed_by_count_result = await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.managed_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    managed_by_count = managed_by_count_result.scalar() or 0
    if managed_by_count >= MAX_MANAGED_BY_COUNT:
        raise HTTPException(status_code=400, detail=f"被管理人数已达上限（{MAX_MANAGED_BY_COUNT}人）")

    member_result = await db.execute(
        select(FamilyMember).where(FamilyMember.id == invitation.member_id)
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="关联的家庭成员不存在")

    # --- 档案合并逻辑 ---
    member.member_user_id = current_user.id

    inviter_hp_result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == invitation.inviter_user_id,
            HealthProfile.family_member_id == invitation.member_id,
        )
    )
    inviter_hp = inviter_hp_result.scalar_one_or_none()

    acceptor_hp_result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == current_user.id,
            HealthProfile.family_member_id.is_(None),
        )
    )
    acceptor_hp = acceptor_hp_result.scalar_one_or_none()

    if acceptor_hp and inviter_hp:
        mergeable_fields = [
            "name", "height", "weight", "blood_type", "gender", "birthday",
            "smoking", "drinking", "exercise_habit", "sleep_habit", "diet_habit",
            "chronic_diseases", "medical_histories", "allergies",
            "drug_allergies", "food_allergies", "other_allergies", "genetic_diseases",
        ]
        for field in mergeable_fields:
            acceptor_val = getattr(acceptor_hp, field, None)
            if acceptor_val is None:
                inviter_val = getattr(inviter_hp, field, None)
                if inviter_val is not None:
                    setattr(acceptor_hp, field, inviter_val)
        acceptor_hp.updated_at = datetime.utcnow()
    elif not acceptor_hp and inviter_hp:
        acceptor_hp = HealthProfile(
            user_id=current_user.id,
            family_member_id=None,
            name=inviter_hp.name,
            height=inviter_hp.height,
            weight=inviter_hp.weight,
            blood_type=inviter_hp.blood_type,
            gender=inviter_hp.gender,
            birthday=inviter_hp.birthday,
            smoking=inviter_hp.smoking,
            drinking=inviter_hp.drinking,
            exercise_habit=inviter_hp.exercise_habit,
            sleep_habit=inviter_hp.sleep_habit,
            diet_habit=inviter_hp.diet_habit,
            chronic_diseases=inviter_hp.chronic_diseases,
            medical_histories=inviter_hp.medical_histories,
            allergies=inviter_hp.allergies,
            drug_allergies=inviter_hp.drug_allergies,
            food_allergies=inviter_hp.food_allergies,
            other_allergies=inviter_hp.other_allergies,
            genetic_diseases=inviter_hp.genetic_diseases,
        )
        db.add(acceptor_hp)

    management = FamilyManagement(
        manager_user_id=invitation.inviter_user_id,
        managed_user_id=current_user.id,
        managed_member_id=invitation.member_id,
        status="active",
    )
    db.add(management)
    await db.flush()

    log = ManagementOperationLog(
        management_id=management.id,
        operator_user_id=current_user.id,
        operation_type="accept_invitation",
        operation_detail={"invite_code": code},
    )
    db.add(log)

    invitation.status = "accepted"
    invitation.accepted_by = current_user.id
    invitation.accepted_at = datetime.utcnow()

    notification = Notification(
        user_id=invitation.inviter_user_id,
        title="共管邀请已接受",
        content=f"{current_user.nickname or current_user.phone} 已接受您的家庭健康档案共管邀请",
        type=NotificationType.system,
        extra_data={
            "type": "family_management",
            "action": "invitation_accepted",
            "management_id": management.id,
        },
    )
    db.add(notification)

    inviter_result = await db.execute(
        select(User).where(User.id == invitation.inviter_user_id)
    )
    inviter = inviter_result.scalar_one_or_none()
    inviter_name = inviter.nickname or inviter.phone if inviter else "对方"
    acceptor_name = current_user.nickname or current_user.phone

    msg_to_inviter = SystemMessage(
        message_type="family_invite_accepted",
        recipient_user_id=invitation.inviter_user_id,
        sender_user_id=current_user.id,
        title="共管邀请已同意",
        content=f"{acceptor_name}已同意您的健康档案共管邀请，您现在可以查看对方的健康数据了",
        related_business_id=str(management.id),
        related_business_type="family_management",
        click_action="/family-bindlist",
    )
    db.add(msg_to_inviter)

    msg_to_acceptor = SystemMessage(
        message_type="family_invite_accepted",
        recipient_user_id=current_user.id,
        sender_user_id=invitation.inviter_user_id,
        title="共管邀请已同意",
        content=f"您已同意{inviter_name}的健康档案共管邀请，对方现在可以查看您的健康数据",
        related_business_id=str(management.id),
        related_business_type="family_management",
        click_action="/family-bindlist",
    )
    db.add(msg_to_acceptor)

    await db.flush()

    return {"message": "已接受邀请", "management_id": management.id}


@router.post("/api/family/invitation/{code}/reject")
async def reject_invitation(
    code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyInvitation).where(FamilyInvitation.invite_code == code)
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

    invitation.status = "cancelled"

    inviter_result = await db.execute(
        select(User).where(User.id == invitation.inviter_user_id)
    )
    inviter = inviter_result.scalar_one_or_none()
    inviter_name = inviter.nickname or inviter.phone if inviter else "对方"
    rejector_name = current_user.nickname or current_user.phone

    msg_to_inviter = SystemMessage(
        message_type="family_invite_rejected",
        recipient_user_id=invitation.inviter_user_id,
        sender_user_id=current_user.id,
        title="共管邀请已被拒绝",
        content=f"{rejector_name}已拒绝您的健康档案共管邀请",
        related_business_id=str(invitation.id),
        related_business_type="family_invitation",
        click_action="/family-invite",
        click_action_params={"can_reinvite": True},
    )
    db.add(msg_to_inviter)

    msg_to_rejector = SystemMessage(
        message_type="family_invite_rejected",
        recipient_user_id=current_user.id,
        sender_user_id=invitation.inviter_user_id,
        title="已拒绝共管邀请",
        content=f"您已拒绝{inviter_name}的健康档案共管邀请",
        related_business_id=str(invitation.id),
        related_business_type="family_invitation",
        click_action="/family-bindlist",
    )
    db.add(msg_to_rejector)

    await db.flush()

    return {"message": "已拒绝邀请"}


@router.get("/api/family/management")
async def list_managed_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(FamilyManagement)
        .where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
        .order_by(FamilyManagement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    managements = result.scalars().all()

    items = []
    for mgmt in managements:
        managed_user_result = await db.execute(
            select(User).where(User.id == mgmt.managed_user_id)
        )
        managed_user = managed_user_result.scalar_one_or_none()

        items.append(FamilyManagementResponse(
            id=mgmt.id,
            manager_user_id=mgmt.manager_user_id,
            manager_nickname=current_user.nickname,
            managed_user_id=mgmt.managed_user_id,
            managed_user_nickname=managed_user.nickname if managed_user else None,
            managed_member_id=mgmt.managed_member_id,
            status=mgmt.status,
            created_at=mgmt.created_at,
        ))

    return {"items": [item.model_dump() for item in items], "total": total, "page": page, "page_size": page_size}


@router.get("/api/family/managed-by")
async def list_managed_by(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.managed_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(FamilyManagement)
        .where(
            FamilyManagement.managed_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
        .order_by(FamilyManagement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    managements = result.scalars().all()

    items = []
    for mgmt in managements:
        manager_result = await db.execute(
            select(User).where(User.id == mgmt.manager_user_id)
        )
        manager = manager_result.scalar_one_or_none()

        items.append(ManagedByResponse(
            id=mgmt.id,
            manager_user_id=mgmt.manager_user_id,
            manager_nickname=manager.nickname if manager else None,
            status=mgmt.status,
            created_at=mgmt.created_at,
        ))

    return {"items": [item.model_dump() for item in items], "total": total, "page": page, "page_size": page_size}


@router.delete("/api/family/management/{management_id}")
async def cancel_management(
    management_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyManagement).where(FamilyManagement.id == management_id)
    )
    mgmt = result.scalar_one_or_none()
    if not mgmt:
        raise HTTPException(status_code=404, detail="管理关系不存在")

    if mgmt.manager_user_id != current_user.id and mgmt.managed_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此管理关系")

    if mgmt.status != "active":
        raise HTTPException(status_code=400, detail="该管理关系已失效")

    mgmt.status = "cancelled"
    mgmt.cancelled_at = datetime.utcnow()
    mgmt.cancelled_by = current_user.id

    log = ManagementOperationLog(
        management_id=mgmt.id,
        operator_user_id=current_user.id,
        operation_type="cancel_management",
        operation_detail={"cancelled_by_role": "manager" if mgmt.manager_user_id == current_user.id else "managed"},
    )
    db.add(log)

    notify_user_id = mgmt.managed_user_id if mgmt.manager_user_id == current_user.id else mgmt.manager_user_id
    notification = Notification(
        user_id=notify_user_id,
        title="共管关系已解除",
        content=f"{current_user.nickname or current_user.phone} 已解除家庭健康档案共管关系",
        type=NotificationType.system,
        extra_data={
            "type": "family_management",
            "action": "management_cancelled",
            "management_id": mgmt.id,
        },
    )
    db.add(notification)
    await db.flush()

    return {"message": "已解除管理关系"}


@router.get("/api/family/management/{management_id}/logs")
async def list_management_logs(
    management_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mgmt_result = await db.execute(
        select(FamilyManagement).where(FamilyManagement.id == management_id)
    )
    mgmt = mgmt_result.scalar_one_or_none()
    if not mgmt:
        raise HTTPException(status_code=404, detail="管理关系不存在")

    if mgmt.manager_user_id != current_user.id and mgmt.managed_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此管理关系的操作记录")

    total_result = await db.execute(
        select(func.count(ManagementOperationLog.id)).where(
            ManagementOperationLog.management_id == management_id,
        )
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(ManagementOperationLog)
        .where(ManagementOperationLog.management_id == management_id)
        .order_by(ManagementOperationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    items = []
    for log_entry in logs:
        operator_result = await db.execute(
            select(User).where(User.id == log_entry.operator_user_id)
        )
        operator = operator_result.scalar_one_or_none()

        items.append(OperationLogResponse(
            id=log_entry.id,
            operator_nickname=operator.nickname if operator else None,
            operation_type=log_entry.operation_type,
            operation_detail=log_entry.operation_detail,
            created_at=log_entry.created_at,
        ))

    return {"items": [item.model_dump() for item in items], "total": total, "page": page, "page_size": page_size}
