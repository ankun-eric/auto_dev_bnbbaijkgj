from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, UserAddress
from app.schemas.addresses import AddressCreate, AddressResponse, AddressUpdate

router = APIRouter(prefix="/api/addresses", tags=["收货地址"])


@router.get("")
async def list_addresses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAddress)
        .where(UserAddress.user_id == current_user.id)
        .order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc())
    )
    items = [AddressResponse.model_validate(a) for a in result.scalars().all()]
    return {"items": items}


@router.post("")
async def create_address(
    data: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(
        select(func.count(UserAddress.id)).where(UserAddress.user_id == current_user.id)
    )
    count = count_result.scalar() or 0
    if count >= 10:
        raise HTTPException(status_code=400, detail="最多只能添加10个收货地址")

    if data.is_default:
        await db.execute(
            select(UserAddress).where(
                UserAddress.user_id == current_user.id, UserAddress.is_default == True
            )
        )
        existing_defaults = await db.execute(
            select(UserAddress).where(
                UserAddress.user_id == current_user.id, UserAddress.is_default == True
            )
        )
        for addr in existing_defaults.scalars().all():
            addr.is_default = False

    address = UserAddress(
        user_id=current_user.id,
        name=data.name,
        phone=data.phone,
        province=data.province,
        city=data.city,
        district=data.district,
        street=data.street,
        is_default=data.is_default,
    )
    db.add(address)
    await db.flush()
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.put("/{address_id}")
async def update_address(
    address_id: int,
    data: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAddress).where(
            UserAddress.id == address_id, UserAddress.user_id == current_user.id
        )
    )
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(status_code=404, detail="地址不存在")

    if data.is_default:
        existing_defaults = await db.execute(
            select(UserAddress).where(
                UserAddress.user_id == current_user.id,
                UserAddress.is_default == True,
                UserAddress.id != address_id,
            )
        )
        for addr in existing_defaults.scalars().all():
            addr.is_default = False

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(address, key, value)

    await db.flush()
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.delete("/{address_id}")
async def delete_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAddress).where(
            UserAddress.id == address_id, UserAddress.user_id == current_user.id
        )
    )
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(status_code=404, detail="地址不存在")

    await db.delete(address)
    return {"message": "地址已删除"}
