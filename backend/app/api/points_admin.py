"""管理后台 - 积分商城商品 & 兑换记录 v3.1（PRD 积分商城商品管理优化 v1.1）.

前端路径：
- GET/POST/PUT/DELETE /api/admin/points/mall
- PUT /api/admin/points/mall/batch-status
- GET /api/admin/points/exchange-records
- GET /api/admin/products/services
- POST /api/admin/points/mall/{id}/publish      — 草稿→在售
- POST /api/admin/points/mall/{id}/offline      — 在售→已下架
- POST /api/admin/points/mall/{id}/duplicate    — 复制新建
- GET  /api/admin/points/mall/{id}/change-logs  — 修改历史
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
    Coupon,
    FulfillmentType,
    PointExchangeRecord,
    PointsMallGoodsChangeLog,
    PointsMallItem,
    PointsMallItemType,
    Product,
    ProductCategory,
    User,
)

admin_dep = require_role("admin")

router = APIRouter(prefix="/api/admin", tags=["管理后台-积分商城"])


_ALLOWED_TYPES = {"coupon", "service", "physical", "virtual", "third_party"}

# 在售状态下被锁定的字段（键 = payload key）
LOCKED_FIELDS_ON_SALE = {
    "type": "商品类型",
    "ref_coupon_id": "关联优惠券",
    "ref_service_id": "关联服务商品",
    "price_points": "积分价格",
}

# 可改但留痕的字段
TRACKED_FIELDS = {
    "name": "商品标题",
    "images": "主图/轮播图",
}


class MallItemPayload(BaseModel):
    name: str
    type: str
    price_points: int
    stock: int = 0
    description: Optional[str] = ""
    status: Optional[str] = "active"
    images: Optional[List[str]] = None
    detail_html: Optional[str] = None
    ref_coupon_id: Optional[int] = None
    ref_service_id: Optional[int] = None
    limit_per_user: Optional[int] = 0
    goods_status: Optional[str] = None  # draft/on_sale/off_sale
    sort_weight: Optional[int] = 0


def _coerce_type(value: str) -> str:
    if not value:
        raise HTTPException(status_code=400, detail="商品类型不能为空")
    v = str(value).strip()
    if v not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"未知商品类型: {value}")
    return v


def _get_goods_status(i: PointsMallItem) -> str:
    gs = getattr(i, "goods_status", None)
    if gs:
        return str(gs)
    # 兜底：从 status 推导
    return "on_sale" if (i.status or "") == "active" else "off_sale"


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
        "detail_html": getattr(i, "detail_html", None),
        "ref_coupon_id": getattr(i, "ref_coupon_id", None),
        "ref_service_id": getattr(i, "ref_service_id", None),
        "limit_per_user": getattr(i, "limit_per_user", 0) or 0,
        "goods_status": _get_goods_status(i),
        "replaced_by_goods_id": getattr(i, "replaced_by_goods_id", None),
        "copied_from_goods_id": getattr(i, "copied_from_goods_id", None),
        "sort_weight": getattr(i, "sort_weight", 0) or 0,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


async def _count_exchanged(db: AsyncSession, goods_id: int) -> int:
    cnt = await db.execute(
        select(func.count(PointExchangeRecord.id)).where(
            PointExchangeRecord.goods_id == goods_id,
            PointExchangeRecord.status.in_(["success", "used"]),
        )
    )
    return int(cnt.scalar() or 0)


async def _log_change(
    db: AsyncSession,
    goods_id: int,
    field_key: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    operator: Optional[User],
) -> None:
    try:
        ov = "" if old_value is None else str(old_value) if not isinstance(old_value, (list, dict)) else __import__("json").dumps(old_value, ensure_ascii=False)
        nv = "" if new_value is None else str(new_value) if not isinstance(new_value, (list, dict)) else __import__("json").dumps(new_value, ensure_ascii=False)
        if ov == nv:
            return
        db.add(
            PointsMallGoodsChangeLog(
                goods_id=goods_id,
                field_key=field_key,
                field_name=field_name,
                old_value=ov,
                new_value=nv,
                operator_id=operator.id if operator else None,
                operator_name=(operator.nickname or operator.phone or f"user#{operator.id}") if operator else None,
            )
        )
    except Exception:
        pass


# ───────── 商品 CRUD ─────────
@router.get("/points/mall")
async def admin_list_mall(
    keyword: Optional[str] = None,
    goods_status: Optional[str] = Query(None, description="draft/on_sale/off_sale；默认隐藏 off_sale"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    base = select(PointsMallItem)
    cnt = select(func.count(PointsMallItem.id))
    # 默认隐藏已下架（off_sale）
    if goods_status:
        if goods_status not in ("draft", "on_sale", "off_sale", "all"):
            raise HTTPException(status_code=400, detail="goods_status 参数无效")
        if goods_status != "all":
            base = base.where(PointsMallItem.goods_status == goods_status)
            cnt = cnt.where(PointsMallItem.goods_status == goods_status)
    else:
        base = base.where(PointsMallItem.goods_status != "off_sale")
        cnt = cnt.where(PointsMallItem.goods_status != "off_sale")

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

    if t == "coupon" and not payload.ref_coupon_id:
        raise HTTPException(status_code=400, detail="优惠券类商品必须选择「关联优惠券」")
    if t == "service" and not payload.ref_service_id:
        raise HTTPException(status_code=400, detail="体验服务类商品必须选择「关联服务商品」")

    # 新商品默认为 draft 状态
    goods_status = (payload.goods_status or "draft").strip()
    if goods_status not in ("draft", "on_sale", "off_sale"):
        goods_status = "draft"
    status_compat = "active" if goods_status == "on_sale" else "inactive"
    # 保留 payload.status 兼容
    if payload.status:
        status_compat = payload.status

    item = PointsMallItem(
        name=payload.name,
        description=payload.description or "",
        images=payload.images or [],
        type=t,
        price_points=int(payload.price_points),
        stock=int(payload.stock or 0),
        status=status_compat,
        detail_html=payload.detail_html,
        ref_coupon_id=payload.ref_coupon_id,
        ref_service_id=payload.ref_service_id,
        limit_per_user=int(payload.limit_per_user or 0),
        goods_status=goods_status,
        sort_weight=int(payload.sort_weight or 0),
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
        # 同步 goods_status
        if status == "active":
            it.goods_status = "on_sale"
        else:
            it.goods_status = "off_sale"
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

    current_status = _get_goods_status(it)

    # 字段锁定校验（仅当商品处于 on_sale 状态时生效）
    if current_status == "on_sale":
        for k, label in LOCKED_FIELDS_ON_SALE.items():
            if k in payload:
                old_v = getattr(it, k, None)
                new_v = payload[k]
                if str(old_v or "") != str(new_v or ""):
                    raise HTTPException(
                        status_code=400,
                        detail=f"商品在售中，「{label}」字段不可修改。如需修改，请先下架商品或使用复制新建。",
                    )

    # 记录可留痕字段变更
    if "name" in payload and payload["name"] != it.name:
        await _log_change(db, it.id, "name", "商品标题", it.name, payload["name"], admin)
        it.name = payload["name"]
    if "images" in payload:
        new_images = payload["images"] or []
        if new_images != (it.images or []):
            await _log_change(db, it.id, "images", "主图/轮播图", it.images, new_images, admin)
            it.images = new_images

    if "type" in payload and current_status != "on_sale":
        t = _coerce_type(payload["type"])
        if t in ("virtual", "third_party"):
            raise HTTPException(status_code=400, detail="该类型正在开发中")
        it.type = t
    if "price_points" in payload and current_status != "on_sale":
        it.price_points = int(payload["price_points"])

    if "stock" in payload:
        new_stock = int(payload["stock"])
        # 库存只能增加或不能降到已兑换数以下
        exchanged = await _count_exchanged(db, it.id)
        if new_stock < exchanged:
            raise HTTPException(
                status_code=400,
                detail=f"库存不能低于已兑换数 {exchanged}",
            )
        it.stock = new_stock
    if "description" in payload:
        it.description = payload["description"] or ""
    if "status" in payload:
        it.status = str(payload["status"])
        # 保持 goods_status 对齐
        if it.status == "active" and current_status == "draft":
            it.goods_status = "on_sale"
        elif it.status != "active" and current_status == "on_sale":
            it.goods_status = "off_sale"
    if "goods_status" in payload:
        gs = str(payload["goods_status"])
        if gs not in ("draft", "on_sale", "off_sale"):
            raise HTTPException(status_code=400, detail="goods_status 参数无效")
        it.goods_status = gs
        it.status = "active" if gs == "on_sale" else "inactive"
    if "detail_html" in payload:
        it.detail_html = payload["detail_html"]
    if "ref_coupon_id" in payload and current_status != "on_sale":
        v = payload["ref_coupon_id"]
        it.ref_coupon_id = int(v) if v else None
    if "ref_service_id" in payload and current_status != "on_sale":
        v = payload["ref_service_id"]
        it.ref_service_id = int(v) if v else None
    if "limit_per_user" in payload:
        it.limit_per_user = int(payload["limit_per_user"] or 0)
    if "sort_weight" in payload:
        it.sort_weight = int(payload["sort_weight"] or 0)

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


# ───────── 三态流转接口 ─────────
@router.post("/points/mall/{item_id}/publish")
async def admin_publish_item(
    item_id: int,
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """草稿→在售；若该商品是复制新建的（copied_from_goods_id 非空），自动把源商品下架并打替代标签。"""
    res = await db.execute(select(PointsMallItem).where(PointsMallItem.id == item_id))
    it = res.scalar_one_or_none()
    if not it:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 关联必填校验
    t_str = it.type.value if hasattr(it.type, "value") else str(it.type or "")
    if t_str == "coupon" and not it.ref_coupon_id:
        raise HTTPException(status_code=400, detail="优惠券类商品必须选择「关联优惠券」")
    if t_str == "service" and not it.ref_service_id:
        raise HTTPException(status_code=400, detail="体验服务类商品必须选择「关联服务商品」")

    it.goods_status = "on_sale"
    it.status = "active"

    # 无缝替换：源商品自动下架
    src_id = getattr(it, "copied_from_goods_id", None)
    if src_id:
        src_res = await db.execute(select(PointsMallItem).where(PointsMallItem.id == src_id))
        src = src_res.scalar_one_or_none()
        if src and _get_goods_status(src) == "on_sale":
            src.goods_status = "off_sale"
            src.status = "inactive"
            src.replaced_by_goods_id = it.id
            await _log_change(db, src.id, "replaced_by", "被替代",
                              None, f"被商品《{it.name}》替代", admin)
    await db.flush()
    await db.refresh(it)
    return _item_to_dict(it)


@router.post("/points/mall/{item_id}/offline")
async def admin_offline_item(
    item_id: int,
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """在售→已下架。"""
    res = await db.execute(select(PointsMallItem).where(PointsMallItem.id == item_id))
    it = res.scalar_one_or_none()
    if not it:
        raise HTTPException(status_code=404, detail="商品不存在")
    it.goods_status = "off_sale"
    it.status = "inactive"
    await db.flush()
    await db.refresh(it)
    return _item_to_dict(it)


@router.post("/points/mall/{item_id}/duplicate")
async def admin_duplicate_item(
    item_id: int,
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """复制新建：生成该商品的草稿副本（copied_from_goods_id 指向源商品）。"""
    res = await db.execute(select(PointsMallItem).where(PointsMallItem.id == item_id))
    src = res.scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="源商品不存在")

    t_str = src.type.value if hasattr(src.type, "value") else str(src.type or "")
    copy = PointsMallItem(
        name=f"{src.name} (副本)",
        description=src.description,
        images=list(src.images) if isinstance(src.images, list) else src.images,
        type=t_str,
        price_points=src.price_points,
        stock=src.stock,
        status="inactive",
        detail_html=src.detail_html,
        ref_coupon_id=src.ref_coupon_id,
        ref_service_id=src.ref_service_id,
        limit_per_user=src.limit_per_user or 0,
        goods_status="draft",
        copied_from_goods_id=src.id,
        sort_weight=getattr(src, "sort_weight", 0) or 0,
    )
    db.add(copy)
    await db.flush()
    await db.refresh(copy)
    return _item_to_dict(copy)


@router.get("/points/mall/{item_id}/change-logs")
async def admin_change_logs(
    item_id: int,
    field_key: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    base = select(PointsMallGoodsChangeLog).where(
        PointsMallGoodsChangeLog.goods_id == item_id
    )
    cnt = select(func.count(PointsMallGoodsChangeLog.id)).where(
        PointsMallGoodsChangeLog.goods_id == item_id
    )
    if field_key:
        base = base.where(PointsMallGoodsChangeLog.field_key == field_key)
        cnt = cnt.where(PointsMallGoodsChangeLog.field_key == field_key)
    total = (await db.execute(cnt)).scalar() or 0
    res = await db.execute(
        base.order_by(PointsMallGoodsChangeLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for r in res.scalars().all():
        items.append({
            "id": r.id,
            "goods_id": r.goods_id,
            "field_key": r.field_key,
            "field_name": r.field_name,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "operator_id": r.operator_id,
            "operator_name": r.operator_name,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ───────── 优惠券库存辅助信息（用于前端实时防呆提示） ─────────
@router.get("/points/coupons/{coupon_id}/stock-info")
async def admin_coupon_stock_info(
    coupon_id: int,
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    total_count = int(c.total_count or 0)
    claimed = int(c.claimed_count or 0)
    available = max(total_count - claimed, 0)
    return {
        "coupon_id": c.id,
        "name": c.name,
        "total_count": total_count,
        "claimed_count": claimed,
        "available": available,
    }


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


# ───────── v3.1 服务商品下拉 ─────────
@router.get("/products/services")
async def admin_list_service_products(
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    base = select(Product, ProductCategory.name).join(
        ProductCategory, Product.category_id == ProductCategory.id, isouter=True
    ).where(
        Product.fulfillment_type == FulfillmentType.in_store,
    )
    cnt = select(func.count(Product.id)).where(
        Product.fulfillment_type == FulfillmentType.in_store,
    )
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
