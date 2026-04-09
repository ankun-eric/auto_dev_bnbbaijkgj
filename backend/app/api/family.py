from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import FamilyMember, Notification, NotificationType, User
from app.schemas.user import FamilyMemberCreate, FamilyMemberResponse, FamilyMemberUpdate

router = APIRouter(prefix="/api/family", tags=["家庭成员"])


@router.post("/members", response_model=FamilyMemberResponse)
async def add_family_member(
    data: FamilyMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.member_user_id:
        result = await db.execute(select(User).where(User.id == data.member_user_id))
        member_user = result.scalar_one_or_none()
        if not member_user:
            raise HTTPException(status_code=404, detail="关联用户不存在")

    member = FamilyMember(
        user_id=current_user.id,
        member_user_id=data.member_user_id,
        relationship_type=data.relationship_type,
        nickname=data.nickname,
        birthday=data.birthday,
        gender=data.gender,
        height=data.height,
        weight=data.weight,
        medical_histories=data.medical_histories if data.medical_histories else None,
        allergies=data.allergies if data.allergies else None,
    )
    db.add(member)
    await db.flush()
    await db.refresh(member)
    return FamilyMemberResponse.model_validate(member)


@router.get("/members", response_model=dict)
async def list_family_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(
        select(func.count(FamilyMember.id)).where(FamilyMember.user_id == current_user.id, FamilyMember.status == "active")
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(FamilyMember)
        .where(FamilyMember.user_id == current_user.id, FamilyMember.status == "active")
        .order_by(FamilyMember.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [FamilyMemberResponse.model_validate(m) for m in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/members/{member_id}", response_model=FamilyMemberResponse)
async def get_family_member(
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
    return FamilyMemberResponse.model_validate(member)


@router.put("/members/{member_id}", response_model=FamilyMemberResponse)
async def update_family_member(
    member_id: int,
    data: FamilyMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FamilyMember).where(FamilyMember.id == member_id, FamilyMember.user_id == current_user.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(member, key, value)

    await db.flush()
    await db.refresh(member)
    return FamilyMemberResponse.model_validate(member)


@router.delete("/members/{member_id}")
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

    member.status = "removed"
    return {"message": "已移除家庭成员"}


@router.post("/sos")
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
