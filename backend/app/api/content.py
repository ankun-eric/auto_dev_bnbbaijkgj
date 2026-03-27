from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Article, Comment, ContentStatus, ContentTypeEnum, Favorite, User, Video
from app.schemas.content import ArticleResponse, CommentCreate, CommentResponse, VideoResponse

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
        query.order_by(Article.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ArticleResponse.model_validate(a) for a in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    article.view_count += 1
    await db.flush()
    return ArticleResponse.model_validate(article)


@router.get("/videos")
async def list_videos(
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Video).where(Video.status == ContentStatus.published)
    count_query = select(func.count(Video.id)).where(Video.status == ContentStatus.published)

    if category:
        query = query.where(Video.category == category)
        count_query = count_query.where(Video.category == category)
    if keyword:
        query = query.where(Video.title.contains(keyword))
        count_query = count_query.where(Video.title.contains(keyword))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Video.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [VideoResponse.model_validate(v) for v in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/videos/{video_id}", response_model=VideoResponse)
async def get_video(video_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    video.view_count += 1
    await db.flush()
    return VideoResponse.model_validate(video)


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
        elif content_type == "video":
            vr = await db.execute(select(Video).where(Video.id == content_id))
            video = vr.scalar_one_or_none()
            if video:
                video.like_count = max(0, video.like_count - 1)
        return {"message": "已取消收藏", "favorited": False}
    else:
        fav = Favorite(user_id=current_user.id, content_type=content_type, content_id=content_id)
        db.add(fav)
        if content_type == "article":
            ar = await db.execute(select(Article).where(Article.id == content_id))
            article = ar.scalar_one_or_none()
            if article:
                article.like_count += 1
        elif content_type == "video":
            vr = await db.execute(select(Video).where(Video.id == content_id))
            video = vr.scalar_one_or_none()
            if video:
                video.like_count += 1
        return {"message": "已收藏", "favorited": True}


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
