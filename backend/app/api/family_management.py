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
    SystemConfig,
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
    """[BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 创建邀请。

    - 情况 1：传入 member_id，校验后用现有 Tab。重复邀请会自动取消旧 pending。
    - 情况 2：不传 member_id（从"+ 新增"入口"去邀请"），邀请阶段不创建 Tab，
      只保存邀请记录 + relation_type，对方接受时再建 FamilyMember + HealthProfile。
    """
    # [BUGFIX-DELETE-RATELIMIT-V1 2026-06-01] 频次防护：50 次/UID/自然日，仅成功才计数。
    # 此处只「查不记账」，真正记一次推迟到邀请创建成功后（见函数末尾 incr_rate_limit）。
    try:
        from app.api.guardian_bugfix_v1 import check_rate_limit_only as _rate_check
        _rate_check("invite_create", current_user.id)
    except HTTPException:
        raise
    except Exception:
        pass

    member: FamilyMember | None = None
    target_member_id: int | None = None
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
        target_member_id = member.id
    else:
        # [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 情况 2：邀请阶段不创建 Tab；必须提供关系字段，避免空邀请
        if not (data.relation_type_id or data.relation_type or data.relationship_type):
            raise HTTPException(status_code=400, detail="需要提供关系类型")
        # [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] PRD 4.3：nickname 必填
        if not (data.nickname and str(data.nickname).strip()):
            raise HTTPException(status_code=422, detail="姓名不能为空")

    # [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 守护人配额 = 已激活管理关系数 + 当前用户进行中（pending 且未过期）的邀请数
    managed_count_result = await db.execute(
        select(func.count(FamilyManagement.id)).where(
            FamilyManagement.manager_user_id == current_user.id,
            FamilyManagement.status == "active",
        )
    )
    managed_count = int(managed_count_result.scalar() or 0)

    pending_invite_count_result = await db.execute(
        select(func.count(FamilyInvitation.id)).where(
            FamilyInvitation.inviter_user_id == current_user.id,
            FamilyInvitation.status == "pending",
            FamilyInvitation.expires_at > datetime.utcnow(),
        )
    )
    pending_invite_count = int(pending_invite_count_result.scalar() or 0)

    # [PRD-GUARDIAN-V1.3.1] 动态读取 max_guardians（不再写死 10）
    try:
        from app.api.guardian_system_v13 import _get_max_guardians as _v131_max
        dynamic_max = await _v131_max(db, current_user.id)
    except Exception:
        dynamic_max = MAX_MANAGED_COUNT

    if managed_count + pending_invite_count >= dynamic_max:
        # [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 返回结构化错误码 WARD_LIMIT_REACHED
        total_x = managed_count + pending_invite_count
        raise HTTPException(
            status_code=400,
            detail={
                "code": "WARD_LIMIT_REACHED",
                "message": f"我守护的人已达上限（{total_x}/{dynamic_max}），请先升级会员或解绑现有守护对象",
                "x": total_x,
                "y": int(dynamic_max),
            },
        )

    if member is not None:
        # [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 情况 1 兜底：同 Tab 已激活共管，禁止再邀
        active_mgmt_result = await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.managed_member_id == member.id,
                FamilyManagement.status == "active",
            )
        )
        if active_mgmt_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该成员已有激活的共管关系")

        # [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 情况 1：自动取消旧 pending
        pending_result = await db.execute(
            select(FamilyInvitation).where(
                FamilyInvitation.member_id == member.id,
                FamilyInvitation.inviter_user_id == current_user.id,
                FamilyInvitation.status == "pending",
            )
        )
        for old_inv in pending_result.scalars().all():
            old_inv.status = "cancelled"
    # [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 情况 2：允许并存多条 pending，不去重

    invite_code = uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=INVITATION_EXPIRE_HOURS)

    invitation = FamilyInvitation(
        invite_code=invite_code,
        inviter_user_id=current_user.id,
        member_id=target_member_id,  # [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 情况 2 时为 None
        status="pending",
        expires_at=expires_at,
        relation_type=data.relation_type or data.relationship_type,
    )
    # [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 邀请记录附带 nickname（动态属性，模型若无字段则跳过）
    try:
        if hasattr(FamilyInvitation, "nickname") and data.nickname:
            setattr(invitation, "nickname", str(data.nickname).strip())
    except Exception:
        pass
    db.add(invitation)
    await db.flush()

    # [BUGFIX-DELETE-RATELIMIT-V1 2026-06-01] 仅在邀请创建成功后才记一次额度
    try:
        from app.api.guardian_bugfix_v1 import incr_rate_limit as _rate_incr
        _rate_incr("invite_create", current_user.id)
    except Exception:
        pass

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

    # 查询邀请人的主健康档案获取真实姓名
    inviter_hp_result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == invitation.inviter_user_id,
            HealthProfile.family_member_id.is_(None),
        )
    )
    inviter_main_hp = inviter_hp_result.scalar_one_or_none()
    inviter_real_name = inviter_main_hp.name if inviter_main_hp else None

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
        inviter_real_name=inviter_real_name,
        member_id=invitation.member_id,
        member_nickname=member.nickname if member else None,
        relationship_type=member.relationship_type if member else None,
        relation_type=invitation.relation_type,
        invite_type="normal",
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

    # [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 情况 2 邀请阶段没建 Tab，此时才建
    if invitation.member_id is None:
        existing_count_res = await db.execute(
            select(func.count(FamilyMember.id)).where(
                FamilyMember.user_id == invitation.inviter_user_id,
                FamilyMember.status == "active",
            )
        )
        existing_count = int(existing_count_res.scalar() or 0)
        # [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 使用邀请记录里的 nickname 建档
        invite_nickname = getattr(invitation, "nickname", None) or (current_user.nickname or current_user.phone or "")
        member = FamilyMember(
            user_id=invitation.inviter_user_id,
            nickname=invite_nickname,
            relationship_type=invitation.relation_type,
            is_self=False,
            avatar_color_index=existing_count % 5,
            member_user_id=current_user.id,
        )
        db.add(member)
        await db.flush()
        new_hp = HealthProfile(
            user_id=invitation.inviter_user_id,
            family_member_id=member.id,
            name=invite_nickname,
        )
        db.add(new_hp)
        await db.flush()
        invitation.member_id = member.id
    else:
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


@router.put("/api/family/management/{management_id}/share-toggle")
async def toggle_member_benefit_share(
    management_id: int,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[IGUARD-V2 2026-05-28] 切换会员权益共享开关。
    仅守护人本人可操作，关闭后被守护人将无法使用守护人的会员权益。
    """
    enabled = bool(payload.get("enabled", True))
    result = await db.execute(
        select(FamilyManagement).where(FamilyManagement.id == management_id)
    )
    mgmt = result.scalar_one_or_none()
    if not mgmt:
        raise HTTPException(status_code=404, detail="管理关系不存在")
    if mgmt.manager_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此管理关系")
    if mgmt.status != "active":
        raise HTTPException(status_code=400, detail="该管理关系已失效")

    mgmt.member_benefit_shared = enabled
    db.add(ManagementOperationLog(
        management_id=mgmt.id,
        operator_user_id=current_user.id,
        operation_type="share_toggle",
        operation_detail={"enabled": enabled},
    ))
    await db.flush()
    return {
        "management_id": mgmt.id,
        "member_benefit_shared": enabled,
        "message": "已开启会员权益共享" if enabled else "已关闭会员权益共享",
    }


@router.get("/api/family/management/{management_id}/usage-records")
async def list_usage_records(
    management_id: int,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[IGUARD-V2 2026-05-28] 会员权益共享使用明细。
    返回被守护人使用守护人共享额度的最近 N 条记录（基于 operation_logs，类型=share_used 或 proxy_pay_used）。
    """
    result = await db.execute(
        select(FamilyManagement).where(FamilyManagement.id == management_id)
    )
    mgmt = result.scalar_one_or_none()
    if not mgmt:
        raise HTTPException(status_code=404, detail="管理关系不存在")
    if mgmt.manager_user_id != current_user.id and mgmt.managed_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看")

    logs_result = await db.execute(
        select(ManagementOperationLog)
        .where(
            ManagementOperationLog.management_id == management_id,
            ManagementOperationLog.operation_type.in_(["share_used", "proxy_pay_used"]),
        )
        .order_by(ManagementOperationLog.created_at.desc())
        .limit(limit)
    )
    rows = logs_result.scalars().all()
    items = []
    for r in rows:
        detail = r.operation_detail or {}
        items.append({
            "id": r.id,
            "type": r.operation_type,
            "label": detail.get("label") or detail.get("call_type_label") or "权益使用",
            "used_at": r.created_at.isoformat() if r.created_at else None,
        })
    # 额度概览
    total = 5  # 默认 5 次/月（后续可由 system_config 配置）
    used = sum(1 for r in rows if r.created_at and r.created_at.month == datetime.utcnow().month)
    return {
        "management_id": management_id,
        "share_enabled": bool(mgmt.member_benefit_shared),
        "quota": {"total": total, "used": used, "remaining": max(0, total - used)},
        "items": items,
    }


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


# ── 公开协议接口 ──

HEALTH_DATA_AUTH_PROTOCOL_DEFAULT = """《宾尼小康健康数据授权协议》

第一条 协议概述
本协议用于规范"宾尼小康AI健康管家"平台中家庭成员之间的健康数据共享行为。当您接受家庭成员的邀请加入守护关系后，双方将按照本协议约定的范围和方式共享健康数据。

第二条 授权数据范围
接受邀请后，授权共享的数据包括：
- 基础健康档案：姓名、性别、年龄、身高、体重、血型等基本信息
- 体检报告：历次上传的体检报告及AI解读结果
- 用药计划：当前及历史用药方案、服药提醒记录
- 健康指标：血压、血糖、心率等日常监测数据
- 就医资料：就诊记录、诊断报告、医嘱等信息
- AI健康建议：系统为您生成的个性化健康建议和提醒

第三条 数据使用目的
共享的健康数据仅用于以下目的：
- 家庭成员之间的健康关怀与互助管理
- 紧急情况下的健康信息快速获取
- AI健康助手基于家庭整体数据提供更精准的健康建议

第四条 授权可撤回性
- 您可以随时解除守护关系以撤回授权
- 解除关系后，对方将无法继续查看您的健康数据
- 已生成的历史健康建议不受影响，但不再更新

第五条 数据安全保障
- 所有健康数据均经加密传输和存储
- 平台采用严格的访问控制机制，仅授权的家庭成员可查看
- 平台不会将您的健康数据用于商业销售或未授权的第三方共享

第六条 未成年人保护
- 未满14周岁的用户，其健康数据授权须由监护人代为操作
- 14~18周岁的用户，建议在监护人知情同意下进行授权

第七条 协议变更
- 本协议内容如有变更，平台将通过系统通知或页面公告的方式告知
- 变更后继续使用守护功能即视为同意修改后的协议

第八条 争议解决
因本协议引起的争议，双方应友好协商解决。协商不成的，任何一方均可向平台所在地有管辖权的人民法院提起诉讼。"""

public_protocol_router = APIRouter(tags=["公开协议"])


@public_protocol_router.get("/api/public/protocol/{protocol_key}")
async def get_public_protocol(protocol_key: str, db: AsyncSession = Depends(get_db)):
    """获取指定协议的内容（公开接口，不需要登录）"""
    valid_keys = ["userAgreement", "privacyPolicy", "healthDisclaimer", "healthDataAuthorization"]
    if protocol_key not in valid_keys:
        raise HTTPException(status_code=404, detail="协议不存在")
    config_key = f"protocol_{protocol_key}"
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
    config = result.scalar_one_or_none()
    if config:
        content = config.config_value
    elif protocol_key == "healthDataAuthorization":
        content = HEALTH_DATA_AUTH_PROTOCOL_DEFAULT
    else:
        content = ""
    return {"key": protocol_key, "content": content}
