from datetime import date, datetime
from math import asin, cos, radians, sin, sqrt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, func, select, String, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.models import (
    OrderItem,
    OrderReview,
    Product,
    ProductCategory,
    ProductSku,
    ProductStore,
    MerchantStore,
    UnifiedOrder,
    UnifiedOrderStatus,
)
from app.schemas.products import (
    ProductCategoryTreeResponse,
    ProductDetailResponse,
    ProductResponse,
)

router = APIRouter(prefix="/api/products", tags=["商品"])


async def _has_recommend_products(db: AsyncSession) -> bool:
    """Check if there are active products with 'recommend' in marketing_badges."""
    result = await db.execute(
        select(func.count(Product.id))
        .where(Product.status == "active")
        .where(cast(Product.marketing_badges, String).like('%recommend%'))
    )
    count = result.scalar() or 0
    return count > 0


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProductCategory)
        .where(ProductCategory.status == "active")
        .order_by(ProductCategory.sort_order.asc())
    )
    all_cats = result.scalars().all()

    def to_dict(cat: ProductCategory) -> dict:
        return {
            "id": cat.id,
            "name": cat.name,
            "parent_id": cat.parent_id,
            "icon": cat.icon,
            "description": cat.description,
            "sort_order": cat.sort_order,
            "status": cat.status,
            "level": cat.level,
            "created_at": cat.created_at,
            "children": [],
        }

    top_level: list[dict] = []
    children_map: dict[int, list] = {}
    items_by_id: dict[int, dict] = {}
    for cat in all_cats:
        d = to_dict(cat)
        items_by_id[cat.id] = d
        if cat.parent_id is None:
            top_level.append(d)
        else:
            children_map.setdefault(cat.parent_id, []).append(d)

    for cid, children in children_map.items():
        if cid in items_by_id:
            items_by_id[cid]["children"] = children

    has_recommend = await _has_recommend_products(db)
    if has_recommend:
        recommend_virtual = {
            "id": "recommend",
            "name": "推荐",
            "parent_id": None,
            "icon": "🔥",
            "description": "平台精选推荐商品",
            "sort_order": -1,
            "status": "active",
            "level": 1,
            "created_at": None,
            "children": [],
            "is_virtual": True,
        }
        top_level.insert(0, recommend_virtual)

    flat = [to_dict(c) for c in all_cats]
    if has_recommend:
        flat.insert(0, {
            "id": "recommend",
            "name": "推荐",
            "parent_id": None,
            "icon": "🔥",
            "description": "平台精选推荐商品",
            "sort_order": -1,
            "status": "active",
            "level": 1,
            "created_at": None,
            "children": [],
            "is_virtual": True,
        })

    return {"items": top_level, "flat": flat}


@router.get("")
async def list_products(
    category_id: Optional[str] = None,
    parent_category_id: Optional[int] = None,
    fulfillment_type: Optional[str] = None,
    points_exchangeable: Optional[bool] = None,
    keyword: Optional[str] = None,
    q: Optional[str] = None,
    constitution_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """服务列表接口
    - `category_id=recommend`：返回营销角标含 recommend 的推荐商品
    - `parent_category_id`：按一级分类（左侧大类）筛选，自动包含其全部子类
    - `q`：与 `keyword` 等价的关键词参数（前端搜索框使用）
    """
    is_recommend = category_id == "recommend"

    query = (
        select(Product)
        .options(selectinload(Product.skus))
        .where(Product.status == "active")
    )
    count_query = select(func.count(Product.id)).where(Product.status == "active")

    if is_recommend:
        recommend_filter = cast(Product.marketing_badges, String).like('%recommend%')
        query = query.where(recommend_filter)
        count_query = count_query.where(recommend_filter)
    elif category_id and category_id.isdigit():
        cat_id_int = int(category_id)
        query = query.where(Product.category_id == cat_id_int)
        count_query = count_query.where(Product.category_id == cat_id_int)
    elif parent_category_id:
        # 改造④：左侧大类（一级分类）→ 取该大类下所有子类 ID 一起查询
        sub_ids_result = await db.execute(
            select(ProductCategory.id).where(ProductCategory.parent_id == parent_category_id)
        )
        sub_ids = [r for r in sub_ids_result.scalars().all()]
        # 兼容大类本身也挂着商品的场景
        sub_ids.append(parent_category_id)
        query = query.where(Product.category_id.in_(sub_ids))
        count_query = count_query.where(Product.category_id.in_(sub_ids))
    if fulfillment_type:
        query = query.where(Product.fulfillment_type == fulfillment_type)
        count_query = count_query.where(Product.fulfillment_type == fulfillment_type)
    if points_exchangeable is not None:
        query = query.where(Product.points_exchangeable == points_exchangeable)
        count_query = count_query.where(Product.points_exchangeable == points_exchangeable)

    final_kw = (q or keyword or "").strip()
    if final_kw:
        kw = f"%{final_kw}%"
        # 改造④：name 或 symptom_tags（tags JSON 字符串化模糊匹配）任一命中
        cond = Product.name.like(kw) | cast(Product.symptom_tags, String).like(kw)
        query = query.where(cond)
        count_query = count_query.where(cond)
    if constitution_type:
        ct_pattern = f"%{constitution_type}%"
        filter_cond = cast(Product.symptom_tags, String).like(ct_pattern)
        query = query.where(filter_cond)
        count_query = count_query.where(filter_cond)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    if is_recommend:
        order_clause = query.order_by(
            Product.recommend_weight.desc(),
            Product.sort_order.asc(),
            Product.created_at.desc(),
        )
    else:
        order_clause = query.order_by(
            Product.recommend_weight.desc(),
            Product.sort_order.asc(),
            Product.sales_count.desc(),
        )

    result = await db.execute(
        order_clause.offset((page - 1) * page_size).limit(page_size)
    )
    items = [ProductResponse.model_validate(p) for p in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/hot-recommendations")
async def hot_recommendations(
    limit: int = Query(6, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """改造④：服务列表搜索无结果时的「热门推荐」接口

    取近 30 天销量 Top N（用 `sales_count` 作为代理指标，避免重型 join）。
    若库存空可放宽到 active 全集按 sales_count desc。
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=30)

    base_q = (
        select(Product)
        .options(selectinload(Product.skus))
        .where(Product.status == "active")
        .order_by(Product.sales_count.desc(), Product.recommend_weight.desc())
        .limit(limit)
    )
    # 优先取近 30 天有更新的商品（认为是"近期热销"）
    recent_q = base_q.where(Product.updated_at >= cutoff)
    items_recent = (await db.execute(recent_q)).scalars().all()
    if len(items_recent) < limit:
        # 不足则用全集补齐
        items_full = (await db.execute(base_q)).scalars().all()
        seen = {p.id for p in items_recent}
        for p in items_full:
            if p.id not in seen:
                items_recent = list(items_recent) + [p]
                seen.add(p.id)
                if len(items_recent) >= limit:
                    break
    items = [ProductResponse.model_validate(p) for p in items_recent[:limit]]
    return {"items": items}


@router.get("/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.stores).selectinload(ProductStore.store),
            selectinload(Product.skus),
        )
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    cat_result = await db.execute(
        select(ProductCategory.name).where(ProductCategory.id == product.category_id)
    )
    category_name = cat_result.scalar_one_or_none()

    stores = []
    for ps in product.stores:
        stores.append({
            "id": ps.id,
            "store_id": ps.store_id,
            "store_name": ps.store.store_name if ps.store else None,
        })

    review_count_result = await db.execute(
        select(func.count(OrderReview.id))
        .join(OrderItem, OrderItem.order_id == OrderReview.order_id)
        .where(OrderItem.product_id == product_id)
    )
    review_count = review_count_result.scalar() or 0

    avg_rating_result = await db.execute(
        select(func.avg(OrderReview.rating))
        .join(OrderItem, OrderItem.order_id == OrderReview.order_id)
        .where(OrderItem.product_id == product_id)
    )
    avg_rating = avg_rating_result.scalar()

    data = ProductDetailResponse.model_validate(product)
    data.stores = stores
    data.review_count = review_count
    data.avg_rating = float(avg_rating) if avg_rating else None
    data.category_name = category_name
    return data


@router.get("/{product_id}/time-slots/availability")
async def get_time_slots_availability(
    product_id: int,
    date_str: str = Query(..., alias="date", description="查询日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """查询指定商品在某日各时段的可用名额"""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    try:
        query_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    time_slots = product.time_slots or []
    if not time_slots:
        return {"code": 0, "data": {"date": date_str, "slots": []}}

    excluded_statuses = [UnifiedOrderStatus.cancelled.value]

    booked_result = await db.execute(
        select(OrderItem.appointment_data, func.count(OrderItem.id))
        .join(UnifiedOrder, UnifiedOrder.id == OrderItem.order_id)
        .where(
            OrderItem.product_id == product_id,
            func.date(OrderItem.appointment_time) == query_date,
            UnifiedOrder.status.notin_(excluded_statuses),
        )
        .group_by(OrderItem.appointment_data)
    )

    booked_map = {}
    for row in booked_result.all():
        appt_data = row[0]
        count = row[1]
        if appt_data and isinstance(appt_data, dict):
            slot_key = appt_data.get("time_slot", "")
            if slot_key:
                booked_map[slot_key] = booked_map.get(slot_key, 0) + count

    slots_info = []
    for slot in time_slots:
        start = slot.get("start", "")
        end = slot.get("end", "")
        capacity = slot.get("capacity", 1)
        slot_key = f"{start}-{end}"
        booked = booked_map.get(slot_key, 0)
        available = max(0, capacity - booked)
        slots_info.append({
            "start_time": start,
            "end_time": end,
            "capacity": capacity,
            "booked": booked,
            "available": available,
        })

    return {"code": 0, "data": {"date": date_str, "slots": slots_info}}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两点间球面距离 (km)，Haversine 公式。"""
    R = 6371.0
    lat1r, lng1r, lat2r, lng2r = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2r - lat1r
    dlng = lng2r - lng1r
    a = sin(dlat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(dlng / 2) ** 2
    return 2 * R * asin(sqrt(a))


@router.get("/{product_id}/available-stores")
async def get_available_stores(
    product_id: int,
    lat: Optional[float] = Query(None, description="用户当前纬度"),
    lng: Optional[float] = Query(None, description="用户当前经度"),
    db: AsyncSession = Depends(get_db),
):
    """获取商品/卡项的可用门店列表，按距离或字母排序。

    - 当 lat 与 lng 同时传入时按 Haversine 距离升序排序
    - 任一为空时按门店名升序排序
    - 仅返回该商品绑定且 status=active 的门店
    """
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.stores).selectinload(ProductStore.store))
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    raw_stores = []
    for ps in (product.stores or []):
        ms: MerchantStore = ps.store
        if ms is None or (ms.status or "active") != "active":
            continue
        raw_stores.append(ms)

    has_user_loc = lat is not None and lng is not None

    def _build_static_map_url(_lat: Optional[float], _lng: Optional[float]) -> Optional[str]:
        """[2026-05-01 门店地图能力 PRD v1.0] 静态地图缩略图 URL（带大头针）。"""
        if _lat is None or _lng is None:
            return None
        import os as _os
        from urllib.parse import quote as _quote
        amap_key = _os.getenv("AMAP_SERVER_KEY", "").strip()
        if amap_key:
            return (
                "https://restapi.amap.com/v3/staticmap"
                f"?location={_lng:.6f},{_lat:.6f}&zoom=16&size=200*150"
                f"&markers=mid,,A:{_lng:.6f},{_lat:.6f}&key={_quote(amap_key)}"
            )
        # 兜底：OSM 静态地图（无 Key）
        return (
            f"https://staticmap.openstreetmap.de/staticmap.php"
            f"?center={_lat:.6f},{_lng:.6f}&zoom=16&size=200x150"
            f"&markers={_lat:.6f},{_lng:.6f},red-pushpin"
        )

    def _store_extra(ms: MerchantStore) -> dict:
        """[2026-05-02 H5 下单流程优化 PRD v1.0] 扩展字段统一拼装。"""
        return {
            "slot_capacity": getattr(ms, "slot_capacity", 10) or 10,
            "business_start": getattr(ms, "business_start", None),
            "business_end": getattr(ms, "business_end", None),
        }

    items = []
    if has_user_loc:
        for ms in raw_stores:
            store_lat = float(ms.lat) if ms.lat is not None else None
            store_lng = float(ms.lng) if ms.lng is not None else None
            dist = None
            if store_lat is not None and store_lng is not None:
                dist = round(_haversine_km(float(lat), float(lng), store_lat, store_lng), 2)
            items.append({
                "store_id": ms.id,
                "store_code": ms.store_code,
                "name": ms.store_name,
                "address": ms.address,
                "province": getattr(ms, "province", None),
                "city": getattr(ms, "city", None),
                "district": getattr(ms, "district", None),
                "lat": store_lat,
                "lng": store_lng,
                "longitude": store_lng,
                "latitude": store_lat,
                "distance_km": dist,
                "is_nearest": False,
                "static_map_url": _build_static_map_url(store_lat, store_lng),
                **_store_extra(ms),
            })
        items.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] if x["distance_km"] is not None else 0))
        if items and items[0]["distance_km"] is not None:
            items[0]["is_nearest"] = True
        sort_by = "distance"
        user_location = {"lat": float(lat), "lng": float(lng), "source": "gps"}
    else:
        for ms in raw_stores:
            store_lat = float(ms.lat) if ms.lat is not None else None
            store_lng = float(ms.lng) if ms.lng is not None else None
            items.append({
                "store_id": ms.id,
                "store_code": ms.store_code,
                "name": ms.store_name,
                "address": ms.address,
                "province": getattr(ms, "province", None),
                "city": getattr(ms, "city", None),
                "district": getattr(ms, "district", None),
                "lat": store_lat,
                "lng": store_lng,
                "longitude": store_lng,
                "latitude": store_lat,
                "distance_km": None,
                "is_nearest": False,
                "static_map_url": _build_static_map_url(store_lat, store_lng),
                **_store_extra(ms),
            })
        items.sort(key=lambda x: (x["name"] or ""))
        sort_by = "name"
        user_location = None

    return {
        "code": 0,
        "data": {
            "user_location": user_location,
            "stores": items,
            "sort_by": sort_by,
        },
    }
