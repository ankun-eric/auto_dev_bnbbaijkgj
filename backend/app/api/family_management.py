import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    MergePreviewField,
    OperationLogResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["家庭健康档案共管"])

INVITATION_EXPIRE_HOURS = 24
MAX_MANAGED_COUNT = 10
MAX_MANAGED_BY_COUNT = 3

# [PRD-FAMILY-AUTH-MP-V1] 健康档案可合并字段元数据：(key, label)
# key 与 HealthProfile 列名一一对应，label 用于前端展示
MERGEABLE_HEALTH_FIELDS = [
    ("name", "昵称"),
    ("gender", "性别"),
    ("birthday", "生日"),
    ("height", "身高"),
    ("weight", "体重"),
    ("blood_type", "血型"),
    ("smoking", "吸烟史"),
    ("drinking", "饮酒史"),
    ("exercise_habit", "运动习惯"),
    ("sleep_habit", "睡眠习惯"),
    ("diet_habit", "饮食习惯"),
    ("chronic_diseases", "慢性病"),
    ("medical_histories", "既往病史"),
    ("allergies", "过敏史"),
    ("drug_allergies", "药物过敏"),
    ("food_allergies", "食物过敏"),
    ("other_allergies", "其他过敏"),
    ("genetic_diseases", "遗传病"),
]
MERGEABLE_FIELD_KEYS = {k for k, _ in MERGEABLE_HEALTH_FIELDS}


def _normalize_invalid_reason(status: str) -> str | None:
    """[PRD-FAMILY-AUTH-MP-V1] 将邀请 status 归一化为失效原因码。"""
    if status == "expired":
        return "expired"
    if status == "accepted":
        return "used"
    if status == "cancelled":
        return "cancelled"
    return None


@router.post("/api/family/invitation", response_model=InvitationCreateResponse)
async def create_invitation(
    data: InvitationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member: FamilyMember | None = None
    if data.member_id:
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
    else:
        # [F8] 无 member_id 时自动新建一个 Tab（家庭成员记录）
        if not data.nickname and not data.relationship_type and not data.relation_type_id:
            raise HTTPException(status_code=400, detail="需要提供 member_id 或 nickname/relationship_type 以创建新成员")
        count_res = await db.execute(
            select(func.count(FamilyMember.id)).where(
                FamilyMember.user_id == current_user.id,
                FamilyMember.status == "active",
            )
        )
        existing_count = int(count_res.scalar() or 0)
        member = FamilyMember(
            user_id=current_user.id,
            nickname=data.nickname or "",
            relationship_type=data.relationship_type,
            relation_type_id=data.relation_type_id,
            is_self=False,
            avatar_color_index=existing_count % 5,
        )
        db.add(member)
        await db.flush()
        hp = HealthProfile(
            user_id=current_user.id,
            family_member_id=member.id,
            name=data.nickname or "",
        )
        db.add(hp)
        await db.flush()

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
            FamilyManagement.managed_member_id == member.id,
            FamilyManagement.status == "active",
        )
    )
    if active_mgmt_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该成员已有激活的共管关系")

    pending_result = await db.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.member_id == member.id,
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
        member_id=member.id,
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


async def _try_get_optional_user(request_headers: dict, db: AsyncSession) -> Optional[User]:
    """[PRD-FAMILY-AUTH-MP-V1] 解析 Authorization 头，可选返回当前用户；无 token 时返回 None。

    避免直接依赖 get_current_user（强制鉴权），让邀请详情接口同时兼容未登录态预览
    与登录态富信息两种调用方式。
    """
    auth = request_headers.get("authorization") or request_headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(None, 1)[1].strip()
    if not token:
        return None
    try:
        from jose import jwt as _jwt  # 局部 import
        from app.core.config import settings as _settings

        payload = _jwt.decode(token, _settings.SECRET_KEY, algorithms=[_settings.ALGORITHM])
        raw_sub = payload.get("sub") if payload else None
        if raw_sub is None:
            return None
        user_id = int(str(raw_sub))
        u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        return u
    except Exception:
        return None


@router.get("/api/family/invitation/{code}", response_model=InvitationDetailResponse)
async def get_invitation_detail(
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """[PRD-FAMILY-AUTH-MP-V1] 邀请详情。

    - 不强制登录：未登录时返回基本信息 + invalid_reason
    - 已登录时额外返回：is_self_invite、当前用户已被守护数量、合并预览
    """
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

    invalid_reason = _normalize_invalid_reason(status)

    # 当前用户视角字段
    current_user: Optional[User] = None
    if request is not None:
        try:
            current_user = await _try_get_optional_user(dict(request.headers), db)
        except Exception:
            current_user = None

    is_self_invite = bool(
        current_user and invitation.inviter_user_id == current_user.id
    )
    if is_self_invite and invalid_reason is None and status == "pending":
        invalid_reason = "self"

    managed_by_count = 0
    if current_user is not None:
        cnt_res = await db.execute(
            select(func.count(FamilyManagement.id)).where(
                FamilyManagement.managed_user_id == current_user.id,
                FamilyManagement.status == "active",
            )
        )
        managed_by_count = int(cnt_res.scalar() or 0)
    reached_limit = managed_by_count >= MAX_MANAGED_BY_COUNT
    if (
        invalid_reason is None
        and status == "pending"
        and current_user is not None
        and reached_limit
    ):
        invalid_reason = "limit"

    # 合并预览
    merge_preview: list[MergePreviewField] = []
    if current_user is not None and status == "pending" and not is_self_invite:
        inviter_hp = (
            await db.execute(
                select(HealthProfile).where(
                    HealthProfile.user_id == invitation.inviter_user_id,
                    HealthProfile.family_member_id == invitation.member_id,
                )
            )
        ).scalar_one_or_none()
        acceptor_hp = (
            await db.execute(
                select(HealthProfile).where(
                    HealthProfile.user_id == current_user.id,
                    HealthProfile.family_member_id.is_(None),
                )
            )
        ).scalar_one_or_none()
        for key, label in MERGEABLE_HEALTH_FIELDS:
            inviter_val = getattr(inviter_hp, key, None) if inviter_hp else None
            acceptor_val = getattr(acceptor_hp, key, None) if acceptor_hp else None
            if inviter_val is None and acceptor_val is None:
                continue
            will_merge = bool(acceptor_val in (None, "") and inviter_val not in (None, ""))
            merge_preview.append(
                MergePreviewField(
                    key=key,
                    label=label,
                    acceptor_value=acceptor_val,
                    inviter_value=inviter_val,
                    will_merge=will_merge,
                )
            )

    return InvitationDetailResponse(
        invite_code=invitation.invite_code,
        status=status,
        inviter_user_id=invitation.inviter_user_id,
        inviter_nickname=inviter.nickname if inviter else None,
        inviter_avatar=inviter.avatar if inviter else None,
        inviter_phone=inviter.phone if inviter else None,
        member_id=invitation.member_id,
        member_nickname=member.nickname if member else None,
        relationship_type=member.relationship_type if member else None,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        is_self_invite=is_self_invite,
        current_managed_by_count=managed_by_count,
        max_managed_by_count=MAX_MANAGED_BY_COUNT,
        reached_managed_by_limit=reached_limit,
        invalid_reason=invalid_reason,
        merge_preview=merge_preview,
    )


@router.post("/api/family/invitation/{code}/accept")
async def accept_invitation(
    code: str,
    payload: Optional[InvitationAcceptRequest] = None,
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

    # [PRD-FAMILY-AUTH-MP-V1] 根据 payload.merge_fields 控制合并范围
    # - None  → 兼容旧行为，合并所有可合并字段
    # - []    → 不合并任何字段（用户全部选择"保留原值"）
    # - 子集  → 仅合并指定 key
    requested_keys: Optional[set[str]] = None
    if payload is not None and payload.merge_fields is not None:
        requested_keys = {k for k in payload.merge_fields if k in MERGEABLE_FIELD_KEYS}

    if acceptor_hp and inviter_hp:
        mergeable_fields = [
            "name", "height", "weight", "blood_type", "gender", "birthday",
            "smoking", "drinking", "exercise_habit", "sleep_habit", "diet_habit",
            "chronic_diseases", "medical_histories", "allergies",
            "drug_allergies", "food_allergies", "other_allergies", "genetic_diseases",
        ]
        for field in mergeable_fields:
            if requested_keys is not None and field not in requested_keys:
                continue
            acceptor_val = getattr(acceptor_hp, field, None)
            if acceptor_val is None:
                inviter_val = getattr(inviter_hp, field, None)
                if inviter_val is not None:
                    setattr(acceptor_hp, field, inviter_val)
        acceptor_hp.updated_at = datetime.utcnow()
    elif not acceptor_hp and inviter_hp:
        # 仅当用户没有现成档案时，从邀请人档案派生
        def _maybe(field_name: str):
            if requested_keys is not None and field_name not in requested_keys:
                return None
            return getattr(inviter_hp, field_name, None)

        acceptor_hp = HealthProfile(
            user_id=current_user.id,
            family_member_id=None,
            name=_maybe("name"),
            height=_maybe("height"),
            weight=_maybe("weight"),
            blood_type=_maybe("blood_type"),
            gender=_maybe("gender"),
            birthday=_maybe("birthday"),
            smoking=_maybe("smoking"),
            drinking=_maybe("drinking"),
            exercise_habit=_maybe("exercise_habit"),
            sleep_habit=_maybe("sleep_habit"),
            diet_habit=_maybe("diet_habit"),
            chronic_diseases=_maybe("chronic_diseases"),
            medical_histories=_maybe("medical_histories"),
            allergies=_maybe("allergies"),
            drug_allergies=_maybe("drug_allergies"),
            food_allergies=_maybe("food_allergies"),
            other_allergies=_maybe("other_allergies"),
            genetic_diseases=_maybe("genetic_diseases"),
        )
        db.add(acceptor_hp)

    # [F9] 数据合并：将 inviter 在 member 下录入的数据合并到 acceptor
    try:
        from app.services.data_merge_service import merge_health_data_on_accept
        merge_stats = await merge_health_data_on_accept(
            db,
            inviter_user_id=invitation.inviter_user_id,
            acceptor_user_id=current_user.id,
            member_id=invitation.member_id,
        )
        logger.info("[F9] data merge stats: %s", merge_stats)
    except Exception as e:
        logger.error("[F9] data merge failed (non-blocking): %s", e)

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
        title="守护邀请已接受",
        content=f"{current_user.nickname or current_user.phone} 已成为您的守护者",
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
        title="守护邀请已同意",
        content=f"{acceptor_name} 已成为您的守护者，可在第一时间收到您的健康提醒",
        related_business_id=str(management.id),
        related_business_type="family_management",
        click_action="/family-bindlist",
    )
    db.add(msg_to_inviter)

    msg_to_acceptor = SystemMessage(
        message_type="family_invite_accepted",
        recipient_user_id=current_user.id,
        sender_user_id=invitation.inviter_user_id,
        title="已成功守护家人",
        content=f"您已成功守护 {inviter_name}，可在第一时间收到对方的健康提醒",
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

    # [PRD-FAMILY-GUARDIAN-V1] 解绑双向通知：守护者退出/被守护者踢人都互相通知
    other_user_id = (
        mgmt.managed_user_id if mgmt.manager_user_id == current_user.id else mgmt.manager_user_id
    )
    operator_role = "guardian" if mgmt.managed_user_id == current_user.id else "managed"
    op_name = current_user.nickname or current_user.phone or "对方"

    # 给对方的通知
    db.add(Notification(
        user_id=other_user_id,
        title="守护关系已解除",
        content=f"{op_name} 已解除与您的家庭健康档案守护关系",
        type=NotificationType.system,
        extra_data={
            "type": "family_management",
            "action": "management_cancelled",
            "management_id": mgmt.id,
            "operator_role": operator_role,
        },
    ))
    # 给操作者本人的回执通知
    db.add(Notification(
        user_id=current_user.id,
        title="已解除守护关系",
        content="您已成功解除家庭健康档案守护关系",
        type=NotificationType.system,
        extra_data={
            "type": "family_management",
            "action": "management_cancelled_self",
            "management_id": mgmt.id,
        },
    ))
    await db.flush()

    return {"message": "已解除守护关系"}


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
