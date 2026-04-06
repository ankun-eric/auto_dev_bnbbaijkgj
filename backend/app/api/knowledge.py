from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    KnowledgeBase,
    KnowledgeEntry,
    KnowledgeEntryProduct,
    KnowledgeFallbackConfig,
    KnowledgeHitLog,
    KnowledgeImportTask,
    KnowledgeMissedQuestion,
    KnowledgeSceneBinding,
    KnowledgeSearchConfig,
)
from app.schemas.knowledge import (
    ChatFeedbackRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeEntryCreate,
    KnowledgeEntryResponse,
    KnowledgeEntryUpdate,
    KnowledgeFallbackConfigSchema,
    KnowledgeImportRequest,
    KnowledgeImportTaskResponse,
    KnowledgeSceneBindingSchema,
    KnowledgeSearchConfigSchema,
    StatsOverview,
    TopHitItem,
    TrendPoint,
)

router = APIRouter(prefix="/api", tags=["知识库管理"])

admin_dep = require_role("admin")


def _day_label(d) -> str:
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%m-%d")


# ── 知识库 CRUD ──


@router.get("/admin/knowledge-bases")
async def list_knowledge_bases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeBase)
    count_query = select(func.count(KnowledgeBase.id))

    if keyword:
        query = query.where(KnowledgeBase.name.contains(keyword))
        count_query = count_query.where(KnowledgeBase.name.contains(keyword))
    if status:
        query = query.where(KnowledgeBase.status == status)
        count_query = count_query.where(KnowledgeBase.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(KnowledgeBase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [KnowledgeBaseResponse.model_validate(kb) for kb in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/admin/knowledge-bases")
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    kb = KnowledgeBase(**data.model_dump(), updated_by=current_user.id)
    db.add(kb)
    await db.flush()
    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


# ── 检索策略（静态路由，必须在 {kb_id} 之前定义）──


@router.get("/admin/knowledge-bases/search-config")
async def get_global_search_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeSearchConfig).where(KnowledgeSearchConfig.scope == "global")
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        return {"scope": "global", "config_json": {"match_threshold": 0.6, "max_results": 3}}
    return {"scope": cfg.scope, "config_json": cfg.config_json}


@router.put("/admin/knowledge-bases/search-config")
async def update_global_search_config(
    data: KnowledgeSearchConfigSchema,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeSearchConfig).where(KnowledgeSearchConfig.scope == "global")
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        cfg.config_json = data.config_json
        cfg.updated_at = datetime.utcnow()
    else:
        db.add(KnowledgeSearchConfig(scope="global", config_json=data.config_json))
    return {"message": "全局检索策略更新成功"}


# ── 兜底策略（静态路由）──


@router.get("/admin/knowledge-bases/fallback-config")
async def get_fallback_config(
    scene: str = Query("default"),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeFallbackConfig).where(KnowledgeFallbackConfig.scene == scene)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        return {
            "scene": scene,
            "strategy": "ai_fallback",
            "custom_text": None,
            "recommend_count": 3,
        }
    return {
        "scene": cfg.scene,
        "strategy": cfg.strategy.value if hasattr(cfg.strategy, "value") else cfg.strategy,
        "custom_text": cfg.custom_text,
        "recommend_count": cfg.recommend_count,
    }


@router.put("/admin/knowledge-bases/fallback-config")
async def update_fallback_config(
    data: KnowledgeFallbackConfigSchema,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeFallbackConfig).where(KnowledgeFallbackConfig.scene == data.scene)
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        cfg.strategy = data.strategy
        cfg.custom_text = data.custom_text
        cfg.recommend_count = data.recommend_count
        cfg.updated_at = datetime.utcnow()
    else:
        db.add(KnowledgeFallbackConfig(**data.model_dump()))
    return {"message": "兜底策略更新成功"}


# ── 场景绑定（静态路由）──


@router.get("/admin/knowledge-bases/scene-bindings")
async def get_scene_bindings(
    scene: Optional[str] = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeSceneBinding)
    if scene:
        query = query.where(KnowledgeSceneBinding.scene == scene)
    result = await db.execute(query.order_by(KnowledgeSceneBinding.scene))
    items = []
    for b in result.scalars().all():
        items.append({
            "id": b.id,
            "scene": b.scene,
            "kb_id": b.kb_id,
            "is_primary": b.is_primary,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items}


@router.put("/admin/knowledge-bases/scene-bindings")
async def update_scene_bindings(
    bindings: list[KnowledgeSceneBindingSchema],
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if bindings:
        scenes = {b.scene for b in bindings}
        for scene in scenes:
            await db.execute(
                delete(KnowledgeSceneBinding).where(KnowledgeSceneBinding.scene == scene)
            )
        for b in bindings:
            db.add(KnowledgeSceneBinding(**b.model_dump()))
    return {"message": "场景绑定更新成功"}


# ── 统计（静态路由）──


@router.get("/admin/knowledge-bases/stats/overview")
async def stats_overview(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    total_kb = (await db.execute(select(func.count(KnowledgeBase.id)))).scalar() or 0
    total_entries = (await db.execute(select(func.count(KnowledgeEntry.id)))).scalar() or 0
    active_entries = (
        await db.execute(
            select(func.count(KnowledgeEntry.id)).where(KnowledgeEntry.status == "active")
        )
    ).scalar() or 0
    total_hits = (await db.execute(select(func.count(KnowledgeHitLog.id)))).scalar() or 0
    total_misses = (await db.execute(select(func.count(KnowledgeMissedQuestion.id)))).scalar() or 0
    avg_time = (
        await db.execute(select(func.avg(KnowledgeHitLog.search_time_ms)))
    ).scalar() or 0.0

    hit_rate = 0.0
    total_queries = total_hits + total_misses
    if total_queries > 0:
        hit_rate = round(total_hits / total_queries * 100, 1)

    return StatsOverview(
        total_knowledge_bases=total_kb,
        total_entries=total_entries,
        active_entries=active_entries,
        total_hits=total_hits,
        total_misses=total_misses,
        hit_rate=hit_rate,
        avg_search_time_ms=round(float(avg_time), 1),
    )


@router.get("/admin/knowledge-bases/stats/top-hits")
async def stats_top_hits(
    limit: int = Query(10, ge=1, le=50),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeEntry, KnowledgeBase.name)
        .join(KnowledgeBase, KnowledgeEntry.kb_id == KnowledgeBase.id)
        .where(KnowledgeEntry.hit_count > 0)
        .order_by(KnowledgeEntry.hit_count.desc())
        .limit(limit)
    )
    items = []
    for entry, kb_name in result.all():
        items.append(TopHitItem(
            entry_id=entry.id,
            question=entry.question,
            title=entry.title,
            hit_count=entry.hit_count,
            kb_name=kb_name,
        ))
    return {"items": items}


@router.get("/admin/knowledge-bases/stats/missed-questions")
async def stats_missed_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(KnowledgeMissedQuestion.id)))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(KnowledgeMissedQuestion)
        .order_by(KnowledgeMissedQuestion.count.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        {
            "id": q.id,
            "question": q.question,
            "scene": q.scene,
            "count": q.count,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
        for q in result.scalars().all()
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/admin/knowledge-bases/stats/trend")
async def stats_trend(
    days: int = Query(7, ge=1, le=90),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    end = datetime.utcnow().date()
    start = end - timedelta(days=days - 1)
    start_dt = datetime.combine(start, datetime.min.time())

    labels = [_day_label(start + timedelta(days=i)) for i in range(days)]

    hit_rows = (
        await db.execute(
            select(func.date(KnowledgeHitLog.created_at), func.count(KnowledgeHitLog.id))
            .where(KnowledgeHitLog.created_at >= start_dt)
            .group_by(func.date(KnowledgeHitLog.created_at))
        )
    ).all()
    hits_map: dict[str, int] = {}
    for row in hit_rows:
        if row[0]:
            hits_map[_day_label(row[0])] = int(row[1] or 0)

    miss_rows = (
        await db.execute(
            select(func.date(KnowledgeMissedQuestion.created_at), func.count(KnowledgeMissedQuestion.id))
            .where(KnowledgeMissedQuestion.created_at >= start_dt)
            .group_by(func.date(KnowledgeMissedQuestion.created_at))
        )
    ).all()
    misses_map: dict[str, int] = {}
    for row in miss_rows:
        if row[0]:
            misses_map[_day_label(row[0])] = int(row[1] or 0)

    trend = [
        TrendPoint(date=lab, hits=hits_map.get(lab, 0), misses=misses_map.get(lab, 0))
        for lab in labels
    ]
    return {"items": trend}


@router.get("/admin/knowledge-bases/stats/distribution")
async def stats_distribution(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeBase.name, func.count(KnowledgeHitLog.id))
        .join(KnowledgeHitLog, KnowledgeBase.id == KnowledgeHitLog.kb_id)
        .group_by(KnowledgeBase.id, KnowledgeBase.name)
        .order_by(func.count(KnowledgeHitLog.id).desc())
    )
    items = [{"kb_name": name, "hit_count": cnt} for name, cnt in result.all()]
    return {"items": items}


# ── 批量导入（静态路由）──


@router.post("/admin/knowledge-bases/import")
async def import_entries(
    data: KnowledgeImportRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == data.kb_id))
    if not kb_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="知识库不存在")

    task = KnowledgeImportTask(
        kb_id=data.kb_id,
        source_type=data.source_type,
        status="preview",
        result_json={
            "total": len(data.entries),
            "entries": [e.model_dump() for e in data.entries],
        },
        created_by=current_user.id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return KnowledgeImportTaskResponse.model_validate(task)


@router.get("/admin/knowledge-bases/import/{task_id}")
async def get_import_task(
    task_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeImportTask).where(KnowledgeImportTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return KnowledgeImportTaskResponse.model_validate(task)


@router.post("/admin/knowledge-bases/import/{task_id}/confirm")
async def confirm_import(
    task_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeImportTask).where(KnowledgeImportTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    if task.status != "preview":
        raise HTTPException(status_code=400, detail="该任务已处理")

    entries_data = (task.result_json or {}).get("entries", [])
    created = 0
    for ed in entries_data:
        entry = KnowledgeEntry(
            kb_id=task.kb_id,
            type=ed.get("type", "qa"),
            question=ed.get("question"),
            title=ed.get("title"),
            content_json=ed.get("content_json"),
            keywords=ed.get("keywords"),
            display_mode=ed.get("display_mode", "direct"),
            status=ed.get("status", "active"),
            updated_by=current_user.id,
        )
        db.add(entry)
        created += 1

    task.status = "completed"
    task.result_json = {**(task.result_json or {}), "created": created}
    task.updated_at = datetime.utcnow()

    await db.flush()
    await _refresh_kb_counts(task.kb_id, db)
    return {"message": f"成功导入 {created} 条知识条目", "created": created}


# ── 知识库 {kb_id} 参数化路由 ──


@router.put("/admin/knowledge-bases/{kb_id}")
async def update_knowledge_base(
    kb_id: int,
    data: KnowledgeBaseUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(kb, key, value)
    kb.updated_by = current_user.id
    kb.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


@router.delete("/admin/knowledge-bases/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    confirm: bool = Query(False),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    if not confirm:
        entry_count = (
            await db.execute(
                select(func.count(KnowledgeEntry.id)).where(KnowledgeEntry.kb_id == kb_id)
            )
        ).scalar() or 0
        return {
            "require_confirm": True,
            "message": f"该知识库下有 {entry_count} 条知识条目，确定删除吗？",
            "entry_count": entry_count,
        }

    await db.execute(delete(KnowledgeEntryProduct).where(
        KnowledgeEntryProduct.entry_id.in_(
            select(KnowledgeEntry.id).where(KnowledgeEntry.kb_id == kb_id)
        )
    ))
    await db.execute(delete(KnowledgeHitLog).where(KnowledgeHitLog.kb_id == kb_id))
    await db.execute(delete(KnowledgeEntry).where(KnowledgeEntry.kb_id == kb_id))
    await db.execute(delete(KnowledgeSceneBinding).where(KnowledgeSceneBinding.kb_id == kb_id))
    await db.delete(kb)
    return {"message": "删除成功"}


# ── 知识条目 CRUD ──


@router.get("/admin/knowledge-bases/{kb_id}/entries")
async def list_entries(
    kb_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    entry_type: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: Optional[str] = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeEntry).where(KnowledgeEntry.kb_id == kb_id)
    count_query = select(func.count(KnowledgeEntry.id)).where(KnowledgeEntry.kb_id == kb_id)

    if keyword:
        kw_filter = KnowledgeEntry.question.contains(keyword) | KnowledgeEntry.title.contains(keyword)
        query = query.where(kw_filter)
        count_query = count_query.where(kw_filter)
    if entry_type:
        query = query.where(KnowledgeEntry.type == entry_type)
        count_query = count_query.where(KnowledgeEntry.type == entry_type)
    if status:
        query = query.where(KnowledgeEntry.status == status)
        count_query = count_query.where(KnowledgeEntry.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    if sort_by == "hit_count":
        query = query.order_by(KnowledgeEntry.hit_count.desc())
    elif sort_by == "updated_at":
        query = query.order_by(KnowledgeEntry.updated_at.desc())
    else:
        query = query.order_by(KnowledgeEntry.created_at.desc())

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    items = [KnowledgeEntryResponse.model_validate(e) for e in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/admin/knowledge-bases/{kb_id}/entries")
async def create_entry(
    kb_id: int,
    data: KnowledgeEntryCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    if not kb_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="知识库不存在")

    entry = KnowledgeEntry(kb_id=kb_id, **data.model_dump(), updated_by=current_user.id)
    db.add(entry)
    await db.flush()
    await db.refresh(entry)

    await _refresh_kb_counts(kb_id, db)
    return KnowledgeEntryResponse.model_validate(entry)


@router.put("/admin/knowledge-bases/{kb_id}/entries/{eid}")
async def update_entry(
    kb_id: int,
    eid: int,
    data: KnowledgeEntryUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeEntry).where(KnowledgeEntry.id == eid, KnowledgeEntry.kb_id == kb_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    entry.updated_by = current_user.id
    entry.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(entry)

    await _refresh_kb_counts(kb_id, db)
    return KnowledgeEntryResponse.model_validate(entry)


@router.delete("/admin/knowledge-bases/{kb_id}/entries/{eid}")
async def delete_entry(
    kb_id: int,
    eid: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeEntry).where(KnowledgeEntry.id == eid, KnowledgeEntry.kb_id == kb_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    await db.execute(delete(KnowledgeEntryProduct).where(KnowledgeEntryProduct.entry_id == eid))
    await db.execute(delete(KnowledgeHitLog).where(KnowledgeHitLog.entry_id == eid))
    await db.delete(entry)

    await _refresh_kb_counts(kb_id, db)
    return {"message": "删除成功"}


async def _refresh_kb_counts(kb_id: int, db: AsyncSession) -> None:
    total = (
        await db.execute(
            select(func.count(KnowledgeEntry.id)).where(KnowledgeEntry.kb_id == kb_id)
        )
    ).scalar() or 0
    active = (
        await db.execute(
            select(func.count(KnowledgeEntry.id)).where(
                KnowledgeEntry.kb_id == kb_id, KnowledgeEntry.status == "active"
            )
        )
    ).scalar() or 0
    await db.execute(
        update(KnowledgeBase)
        .where(KnowledgeBase.id == kb_id)
        .values(entry_count=total, active_entry_count=active, updated_at=datetime.utcnow())
    )
