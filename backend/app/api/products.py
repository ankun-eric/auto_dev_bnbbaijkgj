from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, func, select, String
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
