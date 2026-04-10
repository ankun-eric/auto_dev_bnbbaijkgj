import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
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

logger = logging.getLogger(__name__)
from app.schemas.health_v2 import DiseasePresetResponse, RelationTypeResponse
from app.schemas.user import FamilyMemberCreate, FamilyMemberResponse, FamilyMemberUpdate

router = APIRouter(tags=["家庭成员"])


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

    if not any(m.is_self for m in members):
        try:
            relation_type_id = None
            rt_result = await db.execute(
                select(RelationType).where(RelationType.name == "本人")
            )
            rt = rt_result.scalar_one_or_none()
            if rt:
                relation_type_id = rt.id

            self_member = FamilyMember(
                user_id=current_user.id,
                relationship_type="本人",
                nickname="本人",
                is_self=True,
                status="active",
                relation_type_id=relation_type_id,
            )
            db.add(self_member)
            await db.flush()
            await db.refresh(self_member, attribute_names=["id", "created_at"])
            if rt:
                self_member.relation_type = rt
            members.append(self_member)

            hp_result = await db.execute(
                select(HealthProfile).where(
                    HealthProfile.user_id == current_user.id,
                    HealthProfile.family_member_id == self_member.id,
                )
            )
            if not hp_result.scalar_one_or_none():
                hp_unlinked = await db.execute(
                    select(HealthProfile).where(
                        HealthProfile.user_id == current_user.id,
                        HealthProfile.family_member_id.is_(None),
                    )
                )
                unlinked_hp = hp_unlinked.scalar_one_or_none()
                if unlinked_hp:
                    unlinked_hp.family_member_id = self_member.id
                else:
                    db.add(HealthProfile(
                        user_id=current_user.id,
                        family_member_id=self_member.id,
                    ))
                await db.flush()
        except Exception:
            logger.exception("Failed to auto-create self member for user %s", current_user.id)

    self_members = [m for m in members if m.is_self]
    other_members = sorted([m for m in members if not m.is_self], key=lambda x: x.created_at)
    ordered = self_members + other_members

    return {"items": [_to_member_response(m) for m in ordered], "total": len(ordered)}


@router.post("/api/family/members", response_model=FamilyMemberResponse)
async def add_family_member(
    data: FamilyMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="姓名为必填项")
    if not data.gender or not data.gender.strip():
        raise HTTPException(status_code=400, detail="性别为必填项")
    if not data.birthday:
        raise HTTPException(status_code=400, detail="出生日期为必填项")
    if not data.relation_type_id and not data.relationship_type:
        raise HTTPException(status_code=400, detail="成员关系为必填项")

    if data.member_user_id:
        result = await db.execute(select(User).where(User.id == data.member_user_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="关联用户不存在")

    nickname = data.nickname or data.name
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
    )
    db.add(member)
    await db.flush()

    result2 = await db.execute(
        select(FamilyMember)
        .options(selectinload(FamilyMember.relation_type))
        .where(FamilyMember.id == member.id)
    )
    member = result2.scalar_one()

    return _to_member_response(member)


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

    return _to_member_response(member)


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

    return _to_member_response(member)


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
