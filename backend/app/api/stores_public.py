"""[核销订单过期+改期规则优化 v1.0] 公开门店联系信息接口

H5/小程序/Flutter 在订单卡片「联系商家」弹窗中调用，仅返回门店基础联系字段
（来源：merchant_stores 表，PRD 强制：电话取门店联系电话，不取商家总部）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import (
    MerchantMemberRole,
    MerchantStore,
    MerchantStoreMembership,
    User,
)


router = APIRouter(prefix="/api/stores", tags=["门店公开信息"])


class StoreContactResponse(BaseModel):
    store_id: int
    store_name: str
    address: Optional[str] = None
    contact_phone: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    business_hours: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.get("/{store_id}/contact", response_model=StoreContactResponse)
async def get_store_contact(store_id: int, db: AsyncSession = Depends(get_db)):
    """获取门店联系信息（用于「联系商家」弹窗）。

    [2026-05-04 订单「联系商家」电话不显示 Bug 修复 v1.0 · 修复点 4]
    PRD 强制：电话取门店「联系电话」（merchant_stores.contact_phone）。
    若门店未填，则降级取门店 owner 角色成员的注册手机号，
    避免历史脏数据 / 商家忘填场景下完全空白的尴尬。
    """
    rs = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
    store = rs.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")

    phone_value = store.contact_phone
    if not phone_value:
        owner_rs = await db.execute(
            select(User.phone)
            .join(
                MerchantStoreMembership,
                MerchantStoreMembership.user_id == User.id,
            )
            .where(
                MerchantStoreMembership.store_id == store.id,
                MerchantStoreMembership.member_role == MerchantMemberRole.owner,
                MerchantStoreMembership.status == "active",
            )
            .limit(1)
        )
        phone_value = owner_rs.scalar_one_or_none()

    return StoreContactResponse(
        store_id=store.id,
        store_name=store.store_name or "",
        address=store.address,
        contact_phone=phone_value,
        province=getattr(store, "province", None),
        city=getattr(store, "city", None),
        district=getattr(store, "district", None),
        lat=float(store.lat) if store.lat is not None else None,
        lng=float(store.lng) if store.lng is not None else None,
        business_hours=getattr(store, "business_hours", None),
    )
