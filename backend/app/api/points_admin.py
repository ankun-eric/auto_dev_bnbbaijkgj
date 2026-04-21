"""管理后台 - 积分商城商品 & 兑换记录 v3.1（PRD v2 合并发版）.

前端路径：
- GET/POST/PUT/DELETE /api/admin/points/mall
- PUT /api/admin/points/mall/batch-status
- GET /api/admin/points/exchange-records
- GET /api/admin/products/services — v3.1 新增：供"关联服务商品"下拉拉取
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
    FulfillmentType,
    PointExchangeRecord,
    PointsMallItem,
    PointsMallItemType,
    Product,
    ProductCategory,
    User,
)

admin_dep = require_role("admin")

router = APIRouter(prefix="/api/admin", tags=["管理后台-积分商城"])


# 允许的商品类型（白名单）— Bug1 修复：coupon 必须放行
_ALLOWED_TYPES = {"coupon", "service", "physical", "virtual", "third_party"}


class MallItemPayload(BaseModel):
    name: str
    type: str  # coupon/service/virtual/physical/third_party
    price_points: int
    stock: int = 0
    description: Optional[str] = ""
    status: Optional[str] = "active"
    images: Optional[List[str]] = None
    # v3.1 新增
    detail_html: Optional[str] = None
    ref_coupon_id: Optional[int] = None
    ref_service_id: Optional[int] = None
    limit_per_user: Optional[int] = 0


def _coerce_type(value: str) -> str:
    """v3.1：改为返回 VARCHAR 字符串，不再转枚举。放行白名单内所有值。"""
    if not value:
        raise HTTPException(status_code=400, detail="商品类型不能为空")
    v = str(value).strip()
    if v not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"未知商品类型: {value}")
    return v


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
        # v3.1 新增字段
        "detail_html": getattr(i, "detail_html", None),
        "ref_coupon_id": getattr(i, "ref_coupon_id", None),
        "ref_service_id": getattr(i, "ref_service_id", None),
        "limit_per_user": getattr(i, "limit_per_user", 0) or 0,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


# ───────── 商品 CRUD ─────────
@router.get("/points/mall")
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


@router.post("/points/mall")
async def admin_create_mall(
    payload: MallItemPayload,
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    t = _coerce_type(payload.type)
    if t in ("virtual", "third_party"):
        raise HTTPException(status_code=400, detail="该类型正在开发中，暂不支持创建")

    # 关联必填校验（用户 Q-Bug1：给出明确 detail）
    if t == "coupon" and not payload.ref_coupon_id:
        raise HTTPException(status_code=400, detail="优惠券类商品必须选择「关联优惠券」")
    if t == "service" and not payload.ref_service_id:
        raise HTTPException(status_code=400, detail="体验服务类商品必须选择「关联服务商品」")

    item = PointsMallItem(
        name=payload.name,
        description=payload.description or "",
        images=payload.images or [],
        type=t,
        price_points=int(payload.price_points),
        stock=int(payload.stock or 0),
        status=payload.status or "active",
        detail_html=payload.detail_html,
        ref_coupon_id=payload.ref_coupon_id,
        ref_service_id=payload.ref_service_id,
        limit_per_user=int(payload.limit_per_user or 0),
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return _item_to_dict(item)


@router.put("/points/mall/batch-status")
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


@router.put("/points/mall/{item_id}")
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
        t = _coerce_type(payload["type"])
        if t in ("virtual", "third_party"):
            raise HTTPException(status_code=400, detail="该类型正在开发中")
        it.type = t
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
    if "detail_html" in payload:
        it.detail_html = payload["detail_html"]
    if "ref_coupon_id" in payload:
        v = payload["ref_coupon_id"]
        it.ref_coupon_id = int(v) if v else None
    if "ref_service_id" in payload:
        v = payload["ref_service_id"]
        it.ref_service_id = int(v) if v else None
    if "limit_per_user" in payload:
        it.limit_per_user = int(payload["limit_per_user"] or 0)

    # 保存后对关联必填再做一次校验（若运营误清空字段，抛友好 detail）
    t_str = it.type.value if hasattr(it.type, "value") else str(it.type or "")
    if t_str == "coupon" and not it.ref_coupon_id:
        raise HTTPException(status_code=400, detail="优惠券类商品必须选择「关联优惠券」")
    if t_str == "service" and not it.ref_service_id:
        raise HTTPException(status_code=400, detail="体验服务类商品必须选择「关联服务商品」")

    await db.flush()
    await db.refresh(it)
    return _item_to_dict(it)


@router.delete("/points/mall/{item_id}")
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
@router.get("/points/exchange-records")
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


# ───────── v3.1 新增：服务商品下拉（修 Bug2）─────────
@router.get("/products/services")
async def admin_list_service_products(
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """供 Admin 积分商品表单"关联服务商品"下拉使用。

    返回 products 表中 fulfillment_type=in_store 且 status=active 的商品清单。
    - PRD Bug-Q6: 把"服务类商品"数据源彻底改成 products 表（Q6-a.D 已确认）
    """
    base = select(Product, ProductCategory.name).join(
        ProductCategory, Product.category_id == ProductCategory.id, isouter=True
    ).where(
        Product.fulfillment_type == FulfillmentType.in_store,
    )
    cnt = select(func.count(Product.id)).where(
        Product.fulfillment_type == FulfillmentType.in_store,
    )
    # 可选：只返回上架状态。但 Product 模型状态字段可能为 is_active / is_on_sale 等，
    # 为避免字段缺失的硬依赖，这里不强制过滤 status，交给运营在下拉中自行筛选。
    if keyword:
        like = f"%{keyword}%"
        base = base.where(Product.name.like(like))
        cnt = cnt.where(Product.name.like(like))

    total = (await db.execute(cnt)).scalar() or 0
    res = await db.execute(
        base.order_by(Product.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for row in res.all():
        p: Product = row[0]
        cat_name = row[1]
        images = p.images if isinstance(p.images, list) else []
        image = images[0] if images else None
        items.append(
            {
                "id": p.id,
                "name": p.name,
                "category_id": p.category_id,
                "category_name": cat_name,
                "image": image,
                "sale_price": float(p.sale_price) if p.sale_price is not None else None,
                "original_price": float(p.original_price) if p.original_price is not None else None,
                "fulfillment_type": "in_store",
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}
