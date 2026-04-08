import base64
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete as sql_delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    AsrConfig,
    SearchBlockWord,
    SearchLog,
    SearchRecommendWord,
    User,
)
from app.schemas.search import (
    AsrConfigResponse,
    AsrConfigUpdate,
    SearchBlockWordBatchImport,
    SearchBlockWordCreate,
    SearchBlockWordResponse,
    SearchBlockWordUpdate,
    SearchRecommendWordCreate,
    SearchRecommendWordResponse,
    SearchRecommendWordUpdate,
    SearchStatisticsResponse,
)

router = APIRouter(prefix="/api/admin/search", tags=["管理后台-搜索管理"])

admin_dep = Depends(require_role("admin"))


# ──────── B01: 推荐词列表 ────────


@router.get("/recommend-words")
async def list_recommend_words(
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SearchRecommendWord)
    count_stmt = select(func.count(SearchRecommendWord.id))

    if keyword:
        like_pattern = f"%{keyword}%"
        stmt = stmt.where(SearchRecommendWord.keyword.like(like_pattern))
        count_stmt = count_stmt.where(SearchRecommendWord.keyword.like(like_pattern))

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(SearchRecommendWord.sort_order).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = [SearchRecommendWordResponse.model_validate(r) for r in result.scalars().all()]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ──────── B02: 新增推荐词 ────────


@router.post("/recommend-words", response_model=SearchRecommendWordResponse)
async def create_recommend_word(
    data: SearchRecommendWordCreate,
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    word = SearchRecommendWord(**data.model_dump())
    db.add(word)
    await db.flush()
    await db.refresh(word)
    return SearchRecommendWordResponse.model_validate(word)


# ──────── B03: 编辑推荐词 ────────


@router.put("/recommend-words/{word_id}", response_model=SearchRecommendWordResponse)
async def update_recommend_word(
    word_id: int,
    data: SearchRecommendWordUpdate,
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SearchRecommendWord).where(SearchRecommendWord.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="推荐词不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(word, key, val)
    word.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(word)
    return SearchRecommendWordResponse.model_validate(word)


# ──────── B04: 删除推荐词 ────────


@router.delete("/recommend-words/{word_id}")
async def delete_recommend_word(
    word_id: int,
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SearchRecommendWord).where(SearchRecommendWord.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="推荐词不存在")
    await db.delete(word)
    return {"message": "删除成功"}


# ──────── B05: 搜索统计概览 ────────


@router.get("/statistics", response_model=SearchStatisticsResponse)
async def search_statistics(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    base_filter = []
    if start_date:
        base_filter.append(SearchLog.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        base_filter.append(SearchLog.created_at < datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59))

    # top keywords
    top_stmt = (
        select(SearchLog.keyword, func.count(SearchLog.id).label("cnt"))
        .where(*base_filter)
        .group_by(SearchLog.keyword)
        .order_by(func.count(SearchLog.id).desc())
        .limit(20)
    )
    top_result = await db.execute(top_stmt)
    top_keywords = [{"keyword": row[0], "count": row[1]} for row in top_result.all()]

    # daily trend
    trend_stmt = (
        select(
            func.date(SearchLog.created_at).label("day"),
            func.count(SearchLog.id).label("cnt"),
        )
        .where(*base_filter)
        .group_by(func.date(SearchLog.created_at))
        .order_by(func.date(SearchLog.created_at))
    )
    trend_result = await db.execute(trend_stmt)
    trend = [{"date": str(row[0]), "count": row[1]} for row in trend_result.all()]

    # no-result keywords
    no_result_stmt = (
        select(SearchLog.keyword, func.count(SearchLog.id).label("cnt"))
        .where(SearchLog.result_count == 0, *base_filter)
        .group_by(SearchLog.keyword)
        .order_by(func.count(SearchLog.id).desc())
        .limit(20)
    )
    no_result_result = await db.execute(no_result_stmt)
    no_result_keywords = [{"keyword": row[0], "count": row[1]} for row in no_result_result.all()]

    # type distribution (from clicked_type)
    type_dist_stmt = (
        select(SearchLog.clicked_type, func.count(SearchLog.id).label("cnt"))
        .where(SearchLog.clicked_type != None, *base_filter)  # noqa: E711
        .group_by(SearchLog.clicked_type)
    )
    type_dist_result = await db.execute(type_dist_stmt)
    type_distribution = {row[0]: row[1] for row in type_dist_result.all() if row[0]}

    return SearchStatisticsResponse(
        top_keywords=top_keywords,
        trend=trend,
        no_result_keywords=no_result_keywords,
        type_distribution=type_distribution,
    )


# ──────── B06: 屏蔽词列表 ────────


@router.get("/block-words")
async def list_block_words(
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SearchBlockWord)
    count_stmt = select(func.count(SearchBlockWord.id))

    if keyword:
        like_pattern = f"%{keyword}%"
        stmt = stmt.where(SearchBlockWord.keyword.like(like_pattern))
        count_stmt = count_stmt.where(SearchBlockWord.keyword.like(like_pattern))

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(SearchBlockWord.id.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = [SearchBlockWordResponse.model_validate(r) for r in result.scalars().all()]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ──────── B07: 新增屏蔽词 ────────


@router.post("/block-words", response_model=SearchBlockWordResponse)
async def create_block_word(
    data: SearchBlockWordCreate,
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(SearchBlockWord).where(SearchBlockWord.keyword == data.keyword)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该屏蔽词已存在")

    word = SearchBlockWord(**data.model_dump())
    db.add(word)
    await db.flush()
    await db.refresh(word)
    return SearchBlockWordResponse.model_validate(word)


# ──────── B08: 编辑屏蔽词 ────────


@router.put("/block-words/{word_id}", response_model=SearchBlockWordResponse)
async def update_block_word(
    word_id: int,
    data: SearchBlockWordUpdate,
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SearchBlockWord).where(SearchBlockWord.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="屏蔽词不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(word, key, val)
    await db.flush()
    await db.refresh(word)
    return SearchBlockWordResponse.model_validate(word)


# ──────── B09: 删除屏蔽词 ────────


@router.delete("/block-words/{word_id}")
async def delete_block_word(
    word_id: int,
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SearchBlockWord).where(SearchBlockWord.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="屏蔽词不存在")
    await db.delete(word)
    return {"message": "删除成功"}


# ──────── B10: 批量导入屏蔽词 ────────


@router.post("/block-words/batch")
async def batch_import_block_words(
    data: SearchBlockWordBatchImport,
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    added = 0
    skipped = 0
    for kw in data.keywords:
        kw = kw.strip()
        if not kw:
            continue
        existing = await db.execute(
            select(SearchBlockWord).where(SearchBlockWord.keyword == kw)
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue
        db.add(SearchBlockWord(
            keyword=kw,
            block_mode=data.block_mode,
            tip_content=data.tip_content,
        ))
        added += 1
    await db.flush()
    return {"added": added, "skipped": skipped, "total": added + skipped}


# ──────── B11: 获取ASR配置 ────────


@router.get("/asr-config", response_model=AsrConfigResponse)
async def get_asr_config(
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AsrConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="ASR配置不存在")

    resp = AsrConfigResponse.model_validate(config)
    if resp.secret_key_encrypted:
        resp.secret_key_encrypted = resp.secret_key_encrypted[:4] + "****"
    return resp


# ──────── B12: 更新ASR配置 ────────


@router.put("/asr-config", response_model=AsrConfigResponse)
async def update_asr_config(
    data: AsrConfigUpdate,
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AsrConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = AsrConfig()
        db.add(config)
        await db.flush()

    if data.provider is not None:
        config.provider = data.provider
    if data.app_id is not None:
        config.app_id = data.app_id
    if data.secret_id is not None:
        config.secret_id = data.secret_id
    if data.secret_key_raw is not None:
        config.secret_key_encrypted = base64.b64encode(data.secret_key_raw.encode("utf-8")).decode("utf-8")
    if data.is_enabled is not None:
        config.is_enabled = data.is_enabled
    if data.supported_dialects is not None:
        config.supported_dialects = data.supported_dialects

    config.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(config)

    resp = AsrConfigResponse.model_validate(config)
    if resp.secret_key_encrypted:
        resp.secret_key_encrypted = resp.secret_key_encrypted[:4] + "****"
    return resp


# ──────── B13: 测试ASR连接 ────────


@router.post("/asr-config/test")
async def test_asr_config(
    current_user: User = admin_dep,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AsrConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=400, detail="请先配置ASR参数")

    if not config.app_id or not config.secret_id or not config.secret_key_encrypted:
        return {"success": False, "message": "ASR配置不完整，请填写AppId、SecretId和SecretKey"}

    return {"success": True, "message": "ASR配置参数格式正确（实际连通性请通过语音输入测试）"}
