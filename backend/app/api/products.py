from datetime import date, datetime
from math import asin, cos, radians, sin, sqrt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, func, select, String, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.models import (
    GoodsTag,
    OrderItem,
    OrderReview,
    Product,
    ProductCategory,
    ProductSku,
    ProductStore,
    MerchantStore,
    Tag,
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


async def _load_products_tags(db: AsyncSession, goods_ids: list[int]) -> dict[int, dict]:
    """[商品标签体系重构 v1.0] 批量加载多个商品的标签关联，返回 {goods_id: {tag_ids, tags}}

    tags 按 6 大分类分组，便于 C 端按分类展示。
    """
    if not goods_ids:
        return {}
    rows = (
        await db.execute(
            select(GoodsTag.goods_id, Tag)
            .join(Tag, Tag.id == GoodsTag.tag_id)
            .where(GoodsTag.goods_id.in_(goods_ids), Tag.status == 1)
        )
    ).all()
    result: dict[int, dict] = {gid: {"tag_ids": [], "tags": {}} for gid in goods_ids}
    for gid, t in rows:
        bucket = result[gid]
        bucket["tag_ids"].append(t.id)
        bucket["tags"].setdefault(t.category, []).append({
            "id": t.id,
            "name": t.name,
            "category": t.category,
        })
    return result


def _attach_tags(item_dict: dict, tag_bucket: dict | None) -> dict:
    if tag_bucket:
        item_dict["tag_ids"] = tag_bucket.get("tag_ids", [])
        item_dict["tags"] = tag_bucket.get("tags", {})
    else:
        item_dict.setdefault("tag_ids", [])
        item_dict.setdefault("tags", {})
    return item_dict


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
    # [实物商品与积分商城彻底解耦 v1.0 2026-05-25]
    # 兼容老版本 H5/小程序/App 仍可能传 points_exchangeable 查询参数：
    # 接收但完全忽略（不再用于筛选），保证老客户端不会因未知参数报错。
    points_exchangeable: Optional[bool] = None,  # noqa: ARG001  # 仅用于兼容，逻辑已忽略
    keyword: Optional[str] = None,
    q: Optional[str] = None,
    constitution_type: Optional[str] = None,
    tag_ids: Optional[str] = None,
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
    # [实物商品与积分商城彻底解耦 v1.0 2026-05-25]
    # points_exchangeable 参数已废弃：实物商品不再具备"是否进入积分商城"概念，
    # 即便老客户端传入该参数也直接忽略，不做任何 SQL 过滤。

    final_kw = (q or keyword or "").strip()
    if final_kw:
        kw = f"%{final_kw}%"
        # [商品标签体系重构 v1.0] 关键词搜索：name 或 命中任一启用标签的 name
        tag_match_subq = (
            select(GoodsTag.goods_id)
            .join(Tag, Tag.id == GoodsTag.tag_id)
            .where(Tag.name.like(kw), Tag.status == 1)
        )
        cond = Product.name.like(kw) | Product.id.in_(tag_match_subq)
        query = query.where(cond)
        count_query = count_query.where(cond)
    if constitution_type:
        # [商品标签体系重构 v1.0] 体质筛选：找到 constitution 类下名称匹配的 tag.id，
        # 再用 goods_tags 关联筛出商品；体质名兼容带"质"或不带"质"两种写法
        ct = (constitution_type or "").strip()
        ct_variants = {ct, ct + "质", ct.replace("质", "")}
        const_subq = (
            select(GoodsTag.goods_id)
            .join(Tag, Tag.id == GoodsTag.tag_id)
            .where(
                Tag.category == "constitution",
                Tag.status == 1,
                Tag.name.in_(list(ct_variants)),
            )
        )
        query = query.where(Product.id.in_(const_subq))
        count_query = count_query.where(Product.id.in_(const_subq))
    if tag_ids:
        # [商品标签体系重构 v1.0] 多 tag 命中：逗号分隔
        try:
            tid_list = [int(x) for x in str(tag_ids).split(",") if x.strip().isdigit()]
        except Exception:
            tid_list = []
        if tid_list:
            multi_subq = (
                select(GoodsTag.goods_id).where(GoodsTag.tag_id.in_(tid_list))
            )
            query = query.where(Product.id.in_(multi_subq))
            count_query = count_query.where(Product.id.in_(multi_subq))

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
    prods = result.scalars().all()
    # [商品标签体系重构 v1.0] 批量加载并注入 tags / tag_ids
    tag_map = await _load_products_tags(db, [p.id for p in prods])
    items = []
    for p in prods:
        m = ProductResponse.model_validate(p)
        bucket = tag_map.get(p.id) or {}
        m.tag_ids = bucket.get("tag_ids", [])
        m.tags = bucket.get("tags", {})
        items.append(m)
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
    cutoff = datetime.now() - timedelta(days=30)

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
    prods = items_recent[:limit]
    tag_map = await _load_products_tags(db, [p.id for p in prods])
    items = []
    for p in prods:
        m = ProductResponse.model_validate(p)
        bucket = tag_map.get(p.id) or {}
        m.tag_ids = bucket.get("tag_ids", [])
        m.tags = bucket.get("tags", {})
        items.append(m)
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
    # [商品标签体系重构 v1.0] 注入新标签字段
    tag_map = await _load_products_tags(db, [product.id])
    bucket = tag_map.get(product.id) or {}
    data.tag_ids = bucket.get("tag_ids", [])
    data.tags = bucket.get("tags", {})
    return data


@router.get("/{product_id}/related")
async def get_related_products(
    product_id: int,
    limit: int = Query(6, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """[商品标签体系重构 v1.0 2026-05-20] 相关商品推荐

    算法：基于「标签命中数」加权
    1. 取当前商品挂载的所有启用标签 tag_ids
    2. 找出其它启用商品中也命中这些标签的商品，按命中数倒序排序
    3. 命中数相同的按销量、上架时间补充排序
    4. 若该商品无任何标签，回退按同分类销量 Top
    """
    base = await db.get(Product, product_id)
    if not base:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 当前商品的启用标签
    cur_tag_ids = (
        await db.execute(
            select(GoodsTag.tag_id)
            .join(Tag, Tag.id == GoodsTag.tag_id)
            .where(GoodsTag.goods_id == product_id, Tag.status == 1)
        )
    ).scalars().all()

    rows: list[tuple[int, int]] = []
    if cur_tag_ids:
        rows = list(
            (
                await db.execute(
                    select(GoodsTag.goods_id, func.count(GoodsTag.tag_id))
                    .where(
                        GoodsTag.tag_id.in_(list(cur_tag_ids)),
                        GoodsTag.goods_id != product_id,
                    )
                    .group_by(GoodsTag.goods_id)
                    .order_by(func.count(GoodsTag.tag_id).desc())
                    .limit(limit * 3)
                )
            ).all()
        )

    candidate_ids = [int(gid) for gid, _ in rows]
    hit_map = {int(gid): int(cnt) for gid, cnt in rows}

    if not candidate_ids:
        fallback_q = (
            select(Product)
            .options(selectinload(Product.skus))
            .where(
                Product.status == "active",
                Product.id != product_id,
                Product.category_id == base.category_id,
            )
            .order_by(Product.sales_count.desc(), Product.created_at.desc())
            .limit(limit)
        )
        prods = (await db.execute(fallback_q)).scalars().all()
    else:
        q = (
            select(Product)
            .options(selectinload(Product.skus))
            .where(Product.id.in_(candidate_ids), Product.status == "active")
        )
        prods = list((await db.execute(q)).scalars().all())
        prods.sort(
            key=lambda p: (
                -hit_map.get(p.id, 0),
                -(p.sales_count or 0),
                -int((p.created_at or datetime.min).timestamp() if p.created_at else 0),
            )
        )
        prods = prods[:limit]

    tag_map = await _load_products_tags(db, [p.id for p in prods])
    items = []
    for p in prods:
        m = ProductResponse.model_validate(p)
        bucket = tag_map.get(p.id) or {}
        m.tag_ids = bucket.get("tag_ids", [])
        m.tags = bucket.get("tags", {})
        items.append(m)
    return {"items": items, "hit_map": hit_map}


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
