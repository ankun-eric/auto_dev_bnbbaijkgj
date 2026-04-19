from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Favorite, Product, Article, User

router = APIRouter(prefix="/api/favorites", tags=["收藏"])


@router.post("")
async def toggle_favorite(
    content_type: str,
    content_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if content_type not in ("product", "knowledge", "article", "video"):
        raise HTTPException(status_code=400, detail="不支持的收藏类型")

    result = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.content_type == content_type,
            Favorite.content_id == content_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        return {"message": "已取消收藏", "is_favorited": False}

    fav = Favorite(
        user_id=current_user.id,
        content_type=content_type,
        content_id=content_id,
    )
    db.add(fav)
    await db.flush()
    return {"message": "收藏成功，可在「我的-收藏」中查看", "is_favorited": True}


@router.get("/status")
async def favorite_status(
    content_type: str,
    content_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """商品/文章详情页加载时回显收藏状态"""
    result = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.content_type == content_type,
            Favorite.content_id == content_id,
        )
    )
    return {"is_favorited": result.scalar_one_or_none() is not None}


@router.get("")
async def list_favorites(
    tab: Optional[str] = "product",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Favorite).where(Favorite.user_id == current_user.id)
    count_query = select(func.count(Favorite.id)).where(Favorite.user_id == current_user.id)

    if tab:
        if tab == "knowledge":
            query = query.where(Favorite.content_type.in_(["article", "video", "knowledge"]))
            count_query = count_query.where(Favorite.content_type.in_(["article", "video", "knowledge"]))
        else:
            query = query.where(Favorite.content_type == tab)
            count_query = count_query.where(Favorite.content_type == tab)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Favorite.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    favorites = result.scalars().all()

    items = []
    for fav in favorites:
        item_data = {
            "id": fav.id,
            "content_type": fav.content_type,
            "content_id": fav.content_id,
            "created_at": fav.created_at.isoformat() if fav.created_at else None,
            "detail": None,
        }

        if fav.content_type == "product":
            p_result = await db.execute(select(Product).where(Product.id == fav.content_id))
            product = p_result.scalar_one_or_none()
            if product:
                item_data["detail"] = {
                    "id": product.id,
                    "name": product.name,
                    "sale_price": float(product.sale_price),
                    "images": product.images,
                    "status": product.status if isinstance(product.status, str) else product.status.value,
                }
        elif fav.content_type in ("article", "knowledge"):
            a_result = await db.execute(select(Article).where(Article.id == fav.content_id))
            article = a_result.scalar_one_or_none()
            if article:
                item_data["detail"] = {
                    "id": article.id,
                    "title": article.title,
                    "cover_image": article.cover_image,
                    "summary": article.summary,
                }

        items.append(item_data)

    return {"items": items, "total": total, "page": page, "page_size": page_size}
