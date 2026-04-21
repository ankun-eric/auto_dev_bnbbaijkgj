from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Article,
    ArticleCategory,
    Comment,
    ContentStatus,
    ContentTypeEnum,
    Favorite,
    News,
    User,
)
from app.schemas.content import (
    ArticleCategoryResponse,
    ArticleResponse,
    CommentCreate,
    CommentResponse,
    NewsResponse,
)

router = APIRouter(prefix="/api/content", tags=["健康知识"])


@router.get("/articles")
async def list_articles(
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Article).where(Article.status == ContentStatus.published)
    count_query = select(func.count(Article.id)).where(Article.status == ContentStatus.published)

    if category:
        query = query.where(Article.category == category)
        count_query = count_query.where(Article.category == category)
    if keyword:
        query = query.where(Article.title.contains(keyword))
        count_query = count_query.where(Article.title.contains(keyword))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Article.is_top.desc(), Article.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    articles = result.scalars().all()
    # 兼容旧文章：content_html 为空时用 content 回退
    for a in articles:
        if not a.content_html and a.content:
            a.content_html = f"<p>{a.content}</p>"
    items = [ArticleResponse.model_validate(a) for a in articles]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    article.view_count += 1
    await db.flush()
    # 兼容：旧文章 content_html 为空时，用 content 包 <p> 回退
    if not article.content_html and article.content:
        article.content_html = f"<p>{article.content}</p>"
    return ArticleResponse.model_validate(article)


@router.get("/comments")
async def list_comments(
    content_type: str = Query(...),
    content_id: int = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(
        select(func.count(Comment.id)).where(Comment.content_type == content_type, Comment.content_id == content_id)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Comment)
        .where(Comment.content_type == content_type, Comment.content_id == content_id, Comment.parent_id == None)
        .order_by(Comment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [CommentResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/comments", response_model=CommentResponse)
async def create_comment(
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comment = Comment(
        content_type=data.content_type,
        content_id=data.content_id,
        user_id=current_user.id,
        parent_id=data.parent_id,
        content=data.content,
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return CommentResponse.model_validate(comment)


@router.post("/favorites")
async def toggle_favorite(
    content_type: str = Query(...),
    content_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
        if content_type == "article":
            ar = await db.execute(select(Article).where(Article.id == content_id))
            article = ar.scalar_one_or_none()
            if article:
                article.like_count = max(0, article.like_count - 1)
        elif content_type == "news":
            nr = await db.execute(select(News).where(News.id == content_id))
            news_item = nr.scalar_one_or_none()
            if news_item:
                news_item.like_count = max(0, (news_item.like_count or 0) - 1)
        return {"message": "已取消收藏", "favorited": False}
    else:
        fav = Favorite(user_id=current_user.id, content_type=content_type, content_id=content_id)
        db.add(fav)
        if content_type == "article":
            ar = await db.execute(select(Article).where(Article.id == content_id))
            article = ar.scalar_one_or_none()
            if article:
                article.like_count += 1
        elif content_type == "news":
            nr = await db.execute(select(News).where(News.id == content_id))
            news_item = nr.scalar_one_or_none()
            if news_item:
                news_item.like_count = (news_item.like_count or 0) + 1
        return {"message": "已收藏", "favorited": True}


# ──────────────── v8 文章分类 ────────────────


@router.get("/article-categories")
async def list_article_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ArticleCategory)
        .where(ArticleCategory.is_enabled == True)  # noqa: E712
        .order_by(ArticleCategory.sort_order.asc(), ArticleCategory.id.asc())
    )
    items = [ArticleCategoryResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items}


# ──────────────── v8 资讯 ────────────────


@router.get("/news")
async def list_news(
    tag: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(News).where(News.status == ContentStatus.published)
    count_query = select(func.count(News.id)).where(News.status == ContentStatus.published)
    if tag:
        query = query.where(News.tags.contains(tag))
        count_query = count_query.where(News.tags.contains(tag))
    if keyword:
        query = query.where(or_(News.title.contains(keyword), News.summary.contains(keyword)))
        count_query = count_query.where(or_(News.title.contains(keyword), News.summary.contains(keyword)))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 默认按 is_top DESC, published_at DESC 排序
    order_col = func.coalesce(News.published_at, News.created_at)
    result = await db.execute(
        query.order_by(News.is_top.desc(), order_col.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [NewsResponse.from_model(n) for n in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/news/latest")
async def latest_news(
    limit: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    """首页板块专用：取最新 N 条已发布资讯"""
    order_col = func.coalesce(News.published_at, News.created_at)
    result = await db.execute(
        select(News)
        .where(News.status == ContentStatus.published)
        .order_by(News.is_top.desc(), order_col.desc())
        .limit(limit)
    )
    items = [NewsResponse.from_model(n) for n in result.scalars().all()]
    return {"items": items}


@router.get("/news/{news_id}")
async def get_news_detail(news_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(News).where(News.id == news_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="资讯不存在")
    item.view_count = (item.view_count or 0) + 1
    await db.flush()
    return NewsResponse.from_model(item)


@router.get("/favorites")
async def list_favorites(
    content_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Favorite).where(Favorite.user_id == current_user.id)
    count_query = select(func.count(Favorite.id)).where(Favorite.user_id == current_user.id)

    if content_type:
        query = query.where(Favorite.content_type == content_type)
        count_query = count_query.where(Favorite.content_type == content_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Favorite.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    favorites = result.scalars().all()
    items = [{"id": f.id, "content_type": f.content_type, "content_id": f.content_id, "created_at": f.created_at.isoformat()} for f in favorites]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
