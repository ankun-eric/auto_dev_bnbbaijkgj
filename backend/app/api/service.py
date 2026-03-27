from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import ServiceCategory, ServiceItem
from app.schemas.service import ServiceCategoryResponse, ServiceItemResponse

router = APIRouter(prefix="/api/services", tags=["服务"])


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceCategory)
        .where(ServiceCategory.status == "active")
        .order_by(ServiceCategory.sort_order.asc())
    )
    items = [ServiceCategoryResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items}


@router.get("/items")
async def list_items(
    category_id: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(ServiceItem).where(ServiceItem.status == "active")
    count_query = select(func.count(ServiceItem.id)).where(ServiceItem.status == "active")

    if category_id:
        query = query.where(ServiceItem.category_id == category_id)
        count_query = count_query.where(ServiceItem.category_id == category_id)
    if keyword:
        query = query.where(ServiceItem.name.contains(keyword))
        count_query = count_query.where(ServiceItem.name.contains(keyword))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(ServiceItem.sales_count.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ServiceItemResponse.model_validate(i) for i in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/items/{item_id}", response_model=ServiceItemResponse)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ServiceItem).where(ServiceItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="服务项目不存在")
    return ServiceItemResponse.model_validate(item)
