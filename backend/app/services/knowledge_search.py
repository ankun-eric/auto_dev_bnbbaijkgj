import json
import math
import time
from typing import Any, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    KnowledgeBase,
    KnowledgeEntry,
    KnowledgeFallbackConfig,
    KnowledgeHitLog,
    KnowledgeMissedQuestion,
    KnowledgeSceneBinding,
    KnowledgeSearchConfig,
    MatchType,
)
from app.services.ai_service import call_ai_model


async def search_knowledge(
    question: str,
    scene: str,
    db: AsyncSession,
    session_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> dict[str, Any]:
    start = time.time()

    kb_ids = await _get_scene_kb_ids(scene, db)
    if not kb_ids:
        result = await db.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.is_global == True,
                KnowledgeBase.status == "active",
            )
        )
        kb_ids = [r[0] for r in result.all()]

    if not kb_ids:
        await _log_miss(question, scene, db)
        return {"hits": [], "fallback": await _get_fallback(scene, db)}

    config = await _get_search_config(scene, db)
    match_threshold = config.get("match_threshold", 0.6)

    hit = await _exact_match(question, kb_ids, db)
    if hit:
        elapsed = int((time.time() - start) * 1000)
        log_id = await _log_hit(hit, MatchType.exact, 1.0, question, elapsed, session_id, message_id, db)
        if log_id is not None:
            hit["hit_log_id"] = log_id
        return {"hits": [hit], "match_type": "exact", "search_time_ms": elapsed}

    hits = await _keyword_match(question, kb_ids, db, threshold=match_threshold)
    if hits:
        elapsed = int((time.time() - start) * 1000)
        for h in hits:
            log_id = await _log_hit(h, MatchType.keyword, h.get("score", 0.8), question, elapsed, session_id, message_id, db)
            if log_id is not None:
                h["hit_log_id"] = log_id
        return {"hits": hits, "match_type": "keyword", "search_time_ms": elapsed}

    await _log_miss(question, scene, db)
    elapsed = int((time.time() - start) * 1000)
    return {"hits": [], "fallback": await _get_fallback(scene, db), "search_time_ms": elapsed}


async def _get_scene_kb_ids(scene: str, db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(KnowledgeSceneBinding.kb_id).where(KnowledgeSceneBinding.scene == scene)
    )
    return [r[0] for r in result.all()]


async def _exact_match(
    question: str, kb_ids: list[int], db: AsyncSession
) -> Optional[dict[str, Any]]:
    result = await db.execute(
        select(KnowledgeEntry)
        .where(
            KnowledgeEntry.kb_id.in_(kb_ids),
            KnowledgeEntry.status == "active",
            KnowledgeEntry.type == "qa",
            KnowledgeEntry.question.like(f"%{question}%"),
        )
        .limit(1)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        return None
    return _entry_to_hit(entry)


async def _keyword_match(
    question: str,
    kb_ids: list[int],
    db: AsyncSession,
    threshold: float = 0.6,
) -> list[dict[str, Any]]:
    words = _simple_tokenize(question)
    if not words:
        return []

    result = await db.execute(
        select(KnowledgeEntry).where(
            KnowledgeEntry.kb_id.in_(kb_ids),
            KnowledgeEntry.status == "active",
        )
    )
    entries = result.scalars().all()

    scored: list[tuple[float, Any]] = []
    for entry in entries:
        score = _calc_keyword_score(words, entry)
        if score >= threshold:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    hits = []
    for score, entry in scored[:3]:
        hit = _entry_to_hit(entry)
        hit["score"] = round(score, 3)
        hits.append(hit)
    return hits


def _simple_tokenize(text: str) -> list[str]:
    import re
    text = re.sub(r"[^\w\u4e00-\u9fff]", " ", text)
    parts = text.split()
    words = []
    for p in parts:
        if len(p) <= 4:
            words.append(p.lower())
        else:
            words.append(p.lower())
            for i in range(0, len(p) - 1, 2):
                words.append(p[i : i + 2].lower())
    return list(set(words))


def _calc_keyword_score(words: list[str], entry) -> float:
    searchable = ""
    if entry.question:
        searchable += entry.question.lower()
    if entry.title:
        searchable += " " + entry.title.lower()
    if entry.keywords:
        kw_list = entry.keywords if isinstance(entry.keywords, list) else []
        searchable += " " + " ".join(str(k).lower() for k in kw_list)
    if entry.content_json:
        if isinstance(entry.content_json, dict):
            searchable += " " + json.dumps(entry.content_json, ensure_ascii=False).lower()
        elif isinstance(entry.content_json, str):
            searchable += " " + entry.content_json.lower()

    if not searchable or not words:
        return 0.0
    matched = sum(1 for w in words if w in searchable)
    return matched / len(words)


def _entry_to_hit(entry) -> dict[str, Any]:
    return {
        "entry_id": entry.id,
        "kb_id": entry.kb_id,
        "type": entry.type.value if hasattr(entry.type, "value") else entry.type,
        "question": entry.question,
        "title": entry.title,
        "content_json": entry.content_json,
        "display_mode": entry.display_mode.value if hasattr(entry.display_mode, "value") else entry.display_mode,
    }


async def _get_search_config(scene: str, db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(
        select(KnowledgeSearchConfig).where(KnowledgeSearchConfig.scope == scene)
    )
    cfg = result.scalar_one_or_none()
    if cfg and cfg.config_json:
        return cfg.config_json

    result = await db.execute(
        select(KnowledgeSearchConfig).where(KnowledgeSearchConfig.scope == "global")
    )
    cfg = result.scalar_one_or_none()
    if cfg and cfg.config_json:
        return cfg.config_json

    return {"match_threshold": 0.6, "max_results": 3}


async def _log_hit(
    hit: dict,
    match_type: MatchType,
    score: float,
    question: str,
    elapsed_ms: int,
    session_id: Optional[int],
    message_id: Optional[int],
    db: AsyncSession,
) -> Optional[int]:
    log = KnowledgeHitLog(
        entry_id=hit["entry_id"],
        kb_id=hit["kb_id"],
        match_type=match_type,
        match_score=score,
        user_question=question,
        search_time_ms=elapsed_ms,
        session_id=session_id,
        message_id=message_id,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)

    await db.execute(
        update(KnowledgeEntry)
        .where(KnowledgeEntry.id == hit["entry_id"])
        .values(hit_count=KnowledgeEntry.hit_count + 1, last_hit_at=func.now())
    )
    hit["match_type"] = match_type.value if hasattr(match_type, "value") else str(match_type)
    hit["match_score"] = float(score)
    kb_name_row = await db.execute(select(KnowledgeBase.name).where(KnowledgeBase.id == hit["kb_id"]))
    hit["kb_name"] = kb_name_row.scalar_one_or_none() or ""

    return log.id


async def _log_miss(question: str, scene: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(KnowledgeMissedQuestion).where(
            KnowledgeMissedQuestion.question == question,
            KnowledgeMissedQuestion.scene == scene,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.count += 1
    else:
        db.add(KnowledgeMissedQuestion(question=question, scene=scene))


async def _get_fallback(scene: str, db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(
        select(KnowledgeFallbackConfig).where(KnowledgeFallbackConfig.scene == scene)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        result = await db.execute(
            select(KnowledgeFallbackConfig).where(KnowledgeFallbackConfig.scene == "default")
        )
        cfg = result.scalar_one_or_none()

    if cfg:
        return {
            "strategy": cfg.strategy.value if hasattr(cfg.strategy, "value") else cfg.strategy,
            "custom_text": cfg.custom_text,
            "recommend_count": cfg.recommend_count,
        }
    return {"strategy": "ai_fallback", "custom_text": None, "recommend_count": 3}


async def extract_keywords(text: str, db: AsyncSession) -> list[str]:
    messages = [{"role": "user", "content": f"请从以下文本中提取3-5个关键词，用JSON数组格式返回，不要其他内容:\n{text}"}]
    result = await call_ai_model(messages, "你是一个关键词提取助手，只返回JSON数组。", db)
    try:
        if isinstance(result, dict):
            result = result.get("content", "[]")
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return _simple_tokenize(text)[:5]
