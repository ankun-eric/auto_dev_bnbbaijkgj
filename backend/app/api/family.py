import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    DiseasePreset,
    FamilyMember,
    HealthProfile,
    Notification,
    NotificationType,
    RelationType,
    User,
)
# [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 关系徽章字工具
from app.utils.relation_badge import relation_badge_char

logger = logging.getLogger(__name__)
from app.schemas.health_v2 import DiseasePresetResponse, RelationTypeResponse
from app.schemas.user import FamilyMemberCreate, FamilyMemberResponse, FamilyMemberUpdate

router = APIRouter(tags=["家庭成员"])


def _guard_status(member: FamilyMember) -> str:
    """[BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2] 与 health_archive_optim_v2 保持一致的守护状态枚举。"""
    if member.is_self:
        return "self"
    return "guarded" if member.member_user_id else "unguarded"


def _to_member_response(member: FamilyMember) -> FamilyMemberResponse:
    relation_type_name = None
    if member.relation_type is not None:
        relation_type_name = member.relation_type.name
    return FamilyMemberResponse(
        id=member.id,
        user_id=member.user_id,
        member_user_id=member.member_user_id,
        relationship_type=member.relationship_type,
        nickname=member.nickname,
        is_self=member.is_self,
        relation_type_id=member.relation_type_id,
        relation_type_name=relation_type_name,
        birthday=member.birthday,
        gender=member.gender,
        height=member.height,
        weight=member.weight,
        medical_histories=member.medical_histories,
        allergies=member.allergies,
        status=member.status,
        created_at=member.created_at,
    )


def _enrich_member_dict(member: FamilyMember, fallback_color_index: int | None = None) -> dict:
    """[BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 在 FamilyMemberResponse 基础上
    附加 avatar_color_index / relation_badge_char / guard_status 三个字段。

    fallback_color_index：当库内字段为 NULL 时（极少数旧数据），使用该值作为兜底。
    """
    base = _to_member_response(member).model_dump()
    color_index = member.avatar_color_index
    if color_index is None:
        color_index = fallback_color_index if fallback_color_index is not None else 0
    relation_for_badge = "本人" if member.is_self else (
        member.relationship_type or (member.relation_type.name if member.relation_type else "")
    )
    base["avatar_color_index"] = int(color_index) % 5
    base["relation_badge_char"] = relation_badge_char(relation_for_badge, member.nickname)
    base["guard_status"] = _guard_status(member)
    return base


@router.get("/api/family/members")
async def list_family_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status == "active",
        )
    )
    members = list(result.scalars().all())

    # [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 本人永远第一，其余按 created_at 升序
    from datetime import datetime as _dt
    self_members = [m for m in members if m.is_self]
    other_members = sorted(
        [m for m in members if not m.is_self],
        key=lambda x: (x.created_at or _dt.min, x.id),
    )
    ordered = self_members + other_members

    # [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 顺带回填配色（极少数 NULL 数据兜底）
    items = [_enrich_member_dict(m, fallback_color_index=idx % 5) for idx, m in enumerate(ordered)]
    return {"items": items, "total": len(items)}


@router.post("/api/family/members", response_model=FamilyMemberResponse)
async def add_family_member(
    data: FamilyMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.relation_type_id and not data.relationship_type:
        raise HTTPException(status_code=400, detail="成员关系为必填项")

    if data.member_user_id:
        result = await db.execute(select(User).where(User.id == data.member_user_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="关联用户不存在")

    nickname = data.nickname or data.name or ""

    # [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 新成员入档时分配 avatar_color_index：
    # 当前用户已入档成员数（含本人） % 5
    count_res = await db.execute(
        select(func.count(FamilyMember.id)).where(
            FamilyMember.user_id == current_user.id,
            FamilyMember.status == "active",
        )
    )
    existing_count = int(count_res.scalar() or 0)
    next_color_index = existing_count % 5

    member = FamilyMember(
        user_id=current_user.id,
        member_user_id=data.member_user_id,
        relationship_type=data.relationship_type,
        nickname=nickname,
        relation_type_id=data.relation_type_id,
        birthday=data.birthday,
        gender=data.gender,
        height=data.height,
        weight=data.weight,
        medical_histories=data.medical_histories if data.medical_histories else None,
        allergies=data.allergies if data.allergies else None,
        is_self=False,
        avatar_color_index=next_color_index,
    )
    db.add(member)
    await db.flush()

    health_profile = HealthProfile(
        user_id=current_user.id,
        family_member_id=member.id,
        name=nickname,
        gender=data.gender,
        birthday=data.birthday,
        height=data.height,
        weight=data.weight,
        medical_histories=data.medical_histories if data.medical_histories else None,
        allergies=data.allergies if data.allergies else None,
    )
    db.add(health_profile)
    await db.flush()

    result2 = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(FamilyMember.id == member.id)
    )
    member = result2.scalar_one()

    return _enrich_member_dict(member, fallback_color_index=next_color_index)


@router.get("/api/family/members/{member_id}", response_model=FamilyMemberResponse)
async def get_family_member(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(FamilyMember.id == member_id, FamilyMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    return _enrich_member_dict(member)


@router.put("/api/family/members/{member_id}", response_model=FamilyMemberResponse)
async def update_family_member(
    member_id: int,
    data: FamilyMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(FamilyMember.id == member_id, FamilyMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(member, key, value)

    await db.flush()

    result2 = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(FamilyMember.id == member_id)
    )
    member = result2.scalar_one()

    return _enrich_member_dict(member)


@router.delete("/api/family/members/{member_id}")
async def remove_family_member(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember).where(FamilyMember.id == member_id, FamilyMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    if member.is_self:
        raise HTTPException(status_code=400, detail="本人成员不可删除")

    # 软删除该成员的健康档案
    hp_result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == current_user.id,
            HealthProfile.family_member_id == member_id,
        )
    )
    health_profile = hp_result.scalar_one_or_none()
    if health_profile:
        await db.delete(health_profile)

    member.status = "removed"
    await db.flush()
    return {"message": "已移除家庭成员"}


@router.get("/api/relation-types")
async def list_relation_types(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RelationType)
        .where(RelationType.is_active == True)  # noqa: E712
        .order_by(RelationType.sort_order)
    )
    items = [RelationTypeResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items}


@router.get("/api/disease-presets")
async def list_disease_presets(
    category: Optional[str] = Query(None, description="chronic 或 genetic"),
    db: AsyncSession = Depends(get_db),
):
    query = select(DiseasePreset).where(DiseasePreset.is_active == True)  # noqa: E712
    if category:
        query = query.where(DiseasePreset.category == category)
    query = query.order_by(DiseasePreset.sort_order)
    result = await db.execute(query)
    items = [DiseasePresetResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items}


@router.post("/api/family/sos")
async def send_sos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember).where(FamilyMember.user_id == current_user.id, FamilyMember.status == "active")
    )
    members = result.scalars().all()

    notified_count = 0
    for member in members:
        if member.member_user_id:
            notification = Notification(
                user_id=member.member_user_id,
                title="紧急求助",
                content=f"您的家人 {current_user.nickname or current_user.phone} 发来了紧急求助信号，请及时关注！",
                type=NotificationType.health,
                extra_data={"sos_user_id": current_user.id, "sos_type": "emergency"},
            )
            db.add(notification)
            notified_count += 1

    return {"message": "求助信号已发送", "notified_count": notified_count}
