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
    ProductStore,
    MerchantStore,
)
from app.schemas.products import (
    ProductCategoryTreeResponse,
    ProductDetailResponse,
    ProductResponse,
)

router = APIRouter(prefix="/api/products", tags=["商品"])


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProductCategory)
        .where(ProductCategory.status == "active")
        .order_by(ProductCategory.sort_order.asc())
    )
    all_cats = result.scalars().all()

    top_level = []
    children_map: dict[int, list] = {}
    for cat in all_cats:
        cat_data = ProductCategoryTreeResponse.model_validate(cat)
        if cat.parent_id is None:
            top_level.append(cat_data)
        else:
            children_map.setdefault(cat.parent_id, []).append(cat_data)

    for cat in top_level:
        cat.children = children_map.get(cat.id, [])

    return {"items": top_level}


@router.get("")
async def list_products(
    category_id: Optional[int] = None,
    fulfillment_type: Optional[str] = None,
    points_exchangeable: Optional[bool] = None,
    keyword: Optional[str] = None,
    constitution_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Product).where(Product.status == "active")
    count_query = select(func.count(Product.id)).where(Product.status == "active")

    if category_id:
        query = query.where(Product.category_id == category_id)
        count_query = count_query.where(Product.category_id == category_id)
    if fulfillment_type:
        query = query.where(Product.fulfillment_type == fulfillment_type)
        count_query = count_query.where(Product.fulfillment_type == fulfillment_type)
    if points_exchangeable is not None:
        query = query.where(Product.points_exchangeable == points_exchangeable)
        count_query = count_query.where(Product.points_exchangeable == points_exchangeable)
    if keyword:
        kw = f"%{keyword}%"
        query = query.where(Product.name.like(kw))
        count_query = count_query.where(Product.name.like(kw))
    if constitution_type:
        ct_pattern = f"%{constitution_type}%"
        filter_cond = cast(Product.symptom_tags, String).like(ct_pattern)
        query = query.where(filter_cond)
        count_query = count_query.where(filter_cond)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Product.recommend_weight.desc(), Product.sort_order.asc(), Product.sales_count.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ProductResponse.model_validate(p) for p in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.stores).selectinload(ProductStore.store))
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
