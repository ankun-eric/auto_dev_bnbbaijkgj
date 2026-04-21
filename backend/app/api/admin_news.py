"""v8 新增：资讯管理（admin）+ 文章分类管理（admin）。

- 权限：admin / superuser / content_editor 均可访问（通过 require_role("admin", "content_editor") 放行）
- 文章（articles）的 admin CRUD 保留在原有 admin.py 中。本文件仅新增资讯和分类相关接口，以及标签联想接口。
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    Article,
    ArticleCategory,
    ContentStatus,
    News,
    NewsTagHistory,
)
from app.schemas.content import (
    ArticleCategoryCreate,
    ArticleCategoryResponse,
    ArticleCategoryUpdate,
    NewsCreate,
    NewsResponse,
    NewsTagSuggestItem,
    NewsUpdate,
)

# 允许 admin 或 content_editor
content_admin_dep = require_role("admin", "content_editor")

router = APIRouter(prefix="/api/admin", tags=["内容管理-管理端"])


# ──────────────── 文章分类 ────────────────

@router.get("/article-categories")
async def admin_list_article_categories(
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ArticleCategory).order_by(ArticleCategory.sort_order.asc(), ArticleCategory.id.asc())
    )
    items = [ArticleCategoryResponse.model_validate(c) for c in result.scalars().all()]
    return {"items": items, "total": len(items)}


@router.post("/article-categories", response_model=ArticleCategoryResponse)
async def admin_create_article_category(
    data: ArticleCategoryCreate,
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    # 唯一性检查
    exist = await db.execute(select(ArticleCategory).where(ArticleCategory.name == data.name))
    if exist.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该分类名称已存在")
    cat = ArticleCategory(
        name=data.name,
        sort_order=data.sort_order or 0,
        is_enabled=bool(data.is_enabled) if data.is_enabled is not None else True,
    )
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return ArticleCategoryResponse.model_validate(cat)


@router.put("/article-categories/{cat_id}", response_model=ArticleCategoryResponse)
async def admin_update_article_category(
    cat_id: int,
    data: ArticleCategoryUpdate,
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ArticleCategory).where(ArticleCategory.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    payload = data.model_dump(exclude_unset=True)
    if "name" in payload and payload["name"] != cat.name:
        dup = await db.execute(
            select(ArticleCategory).where(
                ArticleCategory.name == payload["name"], ArticleCategory.id != cat_id
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="分类名称已被其它分类占用")
    for k, v in payload.items():
        setattr(cat, k, v)
    await db.flush()
    await db.refresh(cat)
    return ArticleCategoryResponse.model_validate(cat)


@router.delete("/article-categories/{cat_id}")
async def admin_delete_article_category(
    cat_id: int,
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ArticleCategory).where(ArticleCategory.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    # 检查是否仍有文章
    article_cnt_res = await db.execute(
        select(func.count(Article.id)).where(Article.category == cat.name)
    )
    cnt = article_cnt_res.scalar() or 0
    if cnt > 0:
        raise HTTPException(status_code=400, detail=f"该分类下仍有 {cnt} 篇文章，请先迁移再删除")
    await db.delete(cat)
    await db.flush()
    return {"message": "删除成功"}


# ──────────────── 资讯 CRUD ────────────────

def _serialize_tags(tags: Optional[List[str]]) -> Optional[str]:
    if not tags:
        return None
    cleaned = []
    for t in tags[:10]:
        if not t:
            continue
        t = str(t).strip()
        if not t:
            continue
        if len(t) > 20:
            t = t[:20]
        if t not in cleaned:
            cleaned.append(t)
    return ",".join(cleaned) if cleaned else None


async def _upsert_tag_history(db: AsyncSession, tags: Optional[List[str]]):
    if not tags:
        return
    now = datetime.utcnow()
    for t in tags:
        t = str(t).strip()
        if not t:
            continue
        if len(t) > 50:
            t = t[:50]
        res = await db.execute(select(NewsTagHistory).where(NewsTagHistory.tag == t))
        existing = res.scalar_one_or_none()
        if existing:
            existing.use_count = (existing.use_count or 0) + 1
            existing.last_used_at = now
        else:
            db.add(NewsTagHistory(tag=t, use_count=1, last_used_at=now))
    await db.flush()


@router.get("/news")
async def admin_list_news(
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(News)
    count_query = select(func.count(News.id))
    if status:
        query = query.where(News.status == status)
        count_query = count_query.where(News.status == status)
    if tag:
        query = query.where(News.tags.contains(tag))
        count_query = count_query.where(News.tags.contains(tag))
    if keyword:
        cond = or_(News.title.contains(keyword), News.summary.contains(keyword))
        query = query.where(cond)
        count_query = count_query.where(cond)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    order_col = func.coalesce(News.published_at, News.created_at)
    result = await db.execute(
        query.order_by(News.is_top.desc(), order_col.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [NewsResponse.from_model(n) for n in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/news/tags/suggest")
async def admin_news_tag_suggest(
    q: str = Query("", description="标签模糊匹配关键词"),
    limit: int = Query(10, ge=1, le=50),
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(NewsTagHistory)
    if q:
        query = query.where(NewsTagHistory.tag.contains(q))
    query = query.order_by(NewsTagHistory.use_count.desc(), NewsTagHistory.last_used_at.desc()).limit(limit)
    result = await db.execute(query)
    items = [NewsTagSuggestItem(tag=t.tag, use_count=t.use_count or 0) for t in result.scalars().all()]
    return {"items": items}


@router.get("/news/{news_id}")
async def admin_get_news(
    news_id: int,
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(News).where(News.id == news_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="资讯不存在")
    return NewsResponse.from_model(item)


@router.post("/news", response_model=NewsResponse)
async def admin_create_news(
    data: NewsCreate,
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    # 校验
    if not data.title or not data.title.strip():
        raise HTTPException(status_code=400, detail="标题不能为空")
    if not data.content_html or not data.content_html.strip():
        raise HTTPException(status_code=400, detail="正文不能为空")
    tag_list = list(data.tags or [])
    if len(tag_list) > 10:
        raise HTTPException(status_code=400, detail="标签最多 10 个")
    for t in tag_list:
        if t and len(t) > 20:
            raise HTTPException(status_code=400, detail="每个标签不能超过 20 个字符")

    published_at = data.published_at
    status = data.status or "draft"
    if status == "published" and not published_at:
        published_at = datetime.utcnow()

    news_obj = News(
        title=data.title.strip(),
        cover_image=data.cover_image,
        summary=data.summary,
        content_html=data.content_html,
        tags=_serialize_tags(tag_list),
        source=data.source,
        status=status,
        is_top=bool(data.is_top),
        published_at=published_at,
    )
    db.add(news_obj)
    await db.flush()
    await _upsert_tag_history(db, tag_list)
    await db.refresh(news_obj)
    return NewsResponse.from_model(news_obj)


@router.put("/news/{news_id}", response_model=NewsResponse)
async def admin_update_news(
    news_id: int,
    data: NewsUpdate,
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(News).where(News.id == news_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="资讯不存在")

    payload = data.model_dump(exclude_unset=True)
    new_tags = payload.pop("tags", None)
    if new_tags is not None:
        if len(new_tags) > 10:
            raise HTTPException(status_code=400, detail="标签最多 10 个")
        for t in new_tags:
            if t and len(t) > 20:
                raise HTTPException(status_code=400, detail="每个标签不能超过 20 个字符")
        item.tags = _serialize_tags(new_tags)
        await _upsert_tag_history(db, new_tags)

    for k, v in payload.items():
        setattr(item, k, v)

    # 如果切换为 published 且 published_at 为空，自动补上
    if item.status == ContentStatus.published and not item.published_at:
        item.published_at = datetime.utcnow()
    item.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(item)
    return NewsResponse.from_model(item)


@router.delete("/news/{news_id}")
async def admin_delete_news(
    news_id: int,
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(News).where(News.id == news_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="资讯不存在")
    # 软删：改 status 为 archived
    item.status = ContentStatus.archived
    await db.flush()
    return {"message": "删除成功"}


@router.post("/news/{news_id}/publish")
async def admin_publish_news(
    news_id: int,
    target_status: str = Query("published", regex="^(published|archived|draft)$"),
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(News).where(News.id == news_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="资讯不存在")
    item.status = target_status
    if target_status == "published" and not item.published_at:
        item.published_at = datetime.utcnow()
    await db.flush()
    return {"message": "操作成功", "status": target_status}


@router.post("/news/{news_id}/top")
async def admin_toggle_top_news(
    news_id: int,
    current_user=Depends(content_admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(News).where(News.id == news_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="资讯不存在")
    item.is_top = not bool(item.is_top)
    await db.flush()
    return {"message": "操作成功", "is_top": bool(item.is_top)}
