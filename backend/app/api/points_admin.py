"""管理后台 - 积分商城商品 & 兑换记录 v3.

前端路径：
- GET/POST/PUT/DELETE /api/admin/points/mall
- PUT /api/admin/points/mall/batch-status
- GET /api/admin/points/exchange-records
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    PointExchangeRecord,
    PointsMallItem,
    PointsMallItemType,
    User,
)

admin_dep = require_role("admin")

router = APIRouter(prefix="/api/admin/points", tags=["管理后台-积分商城"])


class MallItemPayload(BaseModel):
    name: str
    type: str  # coupon/service/virtual/physical/third_party
    price_points: int
    stock: int = 0
    description: Optional[str] = ""
    status: Optional[str] = "active"
    images: Optional[List[str]] = None


def _coerce_type(value: str) -> PointsMallItemType:
    try:
        return PointsMallItemType(value)
    except Exception:
        # coupon 等新值可能不在枚举里；若枚举严格限制则退化到 virtual
        for v in PointsMallItemType:
            if v.value == value:
                return v
        raise HTTPException(status_code=400, detail=f"未知商品类型: {value}")


def _item_to_dict(i: PointsMallItem) -> dict:
    t = i.type
    type_str = t.value if hasattr(t, "value") else str(t)
    return {
        "id": i.id,
        "name": i.name,
        "description": i.description,
        "images": i.images,
        "type": type_str,
        "price_points": i.price_points,
        "stock": i.stock,
        "status": i.status,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


# ───────── 商品 CRUD ─────────
@router.get("/mall")
async def admin_list_mall(
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    base = select(PointsMallItem)
    cnt = select(func.count(PointsMallItem.id))
    if keyword:
        like = f"%{keyword}%"
        base = base.where(PointsMallItem.name.like(like))
        cnt = cnt.where(PointsMallItem.name.like(like))
    total = (await db.execute(cnt)).scalar() or 0
    res = await db.execute(
        base.order_by(PointsMallItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_item_to_dict(i) for i in res.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/mall")
async def admin_create_mall(
    payload: MallItemPayload,
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if payload.type in ("virtual", "third_party"):
        raise HTTPException(status_code=400, detail="该类型正在开发中，暂不支持创建")

    item = PointsMallItem(
        name=payload.name,
        description=payload.description or "",
        images=payload.images or [],
        type=_coerce_type(payload.type),
        price_points=int(payload.price_points),
        stock=int(payload.stock or 0),
        status=payload.status or "active",
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return _item_to_dict(item)


@router.put("/mall/batch-status")
async def admin_batch_status(
    payload: dict = Body(...),
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    ids = payload.get("item_ids") or []
    status = payload.get("status") or "active"
    if not ids:
        raise HTTPException(status_code=400, detail="请选择商品")
    res = await db.execute(select(PointsMallItem).where(PointsMallItem.id.in_(ids)))
    for it in res.scalars().all():
        it.status = status
    await db.flush()
    return {"ok": True, "count": len(ids)}


@router.put("/mall/{item_id}")
async def admin_update_mall(
    item_id: int,
    payload: dict = Body(...),
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(PointsMallItem).where(PointsMallItem.id == item_id))
    it = res.scalar_one_or_none()
    if not it:
        raise HTTPException(status_code=404, detail="商品不存在")
    if "name" in payload:
        it.name = payload["name"]
    if "type" in payload:
        if payload["type"] in ("virtual", "third_party"):
            raise HTTPException(status_code=400, detail="该类型正在开发中")
        it.type = _coerce_type(payload["type"])
    if "price_points" in payload:
        it.price_points = int(payload["price_points"])
    if "stock" in payload:
        it.stock = int(payload["stock"])
    if "description" in payload:
        it.description = payload["description"] or ""
    if "images" in payload:
        it.images = payload["images"] or []
    if "status" in payload:
        it.status = str(payload["status"])
    await db.flush()
    await db.refresh(it)
    return _item_to_dict(it)


@router.delete("/mall/{item_id}")
async def admin_delete_mall(
    item_id: int,
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(PointsMallItem).where(PointsMallItem.id == item_id))
    it = res.scalar_one_or_none()
    if not it:
        raise HTTPException(status_code=404, detail="商品不存在")
    await db.delete(it)
    await db.flush()
    return {"ok": True}


# ───────── 兑换记录（管理侧）─────────
@router.get("/exchange-records")
async def admin_list_exchange_records(
    keyword: Optional[str] = None,
    goods_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    base = select(PointExchangeRecord)
    cnt = select(func.count(PointExchangeRecord.id))
    if goods_type:
        base = base.where(PointExchangeRecord.goods_type == goods_type)
        cnt = cnt.where(PointExchangeRecord.goods_type == goods_type)
    if status:
        base = base.where(PointExchangeRecord.status == status)
        cnt = cnt.where(PointExchangeRecord.status == status)
    if keyword:
        like = f"%{keyword}%"
        base = base.where(PointExchangeRecord.goods_name.like(like))
        cnt = cnt.where(PointExchangeRecord.goods_name.like(like))
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date)
            base = base.where(PointExchangeRecord.exchange_time >= dt)
            cnt = cnt.where(PointExchangeRecord.exchange_time >= dt)
        except Exception:
            pass
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date + "T23:59:59")
            base = base.where(PointExchangeRecord.exchange_time <= dt)
            cnt = cnt.where(PointExchangeRecord.exchange_time <= dt)
        except Exception:
            pass

    total = (await db.execute(cnt)).scalar() or 0
    res = await db.execute(
        base.order_by(PointExchangeRecord.exchange_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = res.scalars().all()
    items = [
        {
            "id": r.id,
            "order_no": r.order_no,
            "user_id": r.user_id,
            "goods_id": r.goods_id,
            "goods_type": r.goods_type,
            "goods_name": r.goods_name,
            "points": r.points_cost,
            "points_cost": r.points_cost,
            "quantity": r.quantity,
            "status": r.status,
            "created_at": r.exchange_time.isoformat() if r.exchange_time else None,
            "exchange_time": r.exchange_time.isoformat() if r.exchange_time else None,
            "expire_at": r.expire_at.isoformat() if r.expire_at else None,
            "ref_order_no": r.ref_order_no,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
