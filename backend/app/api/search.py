import base64
import hashlib
import hmac
import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import String, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Article,
    AsrConfig,
    ContentStatus,
    DrugSearchKeyword,
    News,
    PointsMallItem,
    SearchBlockWord,
    SearchHistory,
    SearchHotWord,
    SearchLog,
    SearchRecommendWord,
    ServiceItem,
    User,
)
from app.schemas.search import (
    AsrRecognizeResponse,
    DrugSearchKeywordResponse,
    SearchLogCreate,
    SearchResponse,
    SearchResultItem,
    SearchSuggestItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["搜索"])

# ──────── ASR 频率限制 & 辅助函数 ────────

_asr_rate_limit: dict[str, list[float]] = defaultdict(list)
_ASR_RATE_LIMIT_MAX = 10
_ASR_RATE_LIMIT_WINDOW = 60.0

TENCENT_ASR_ENDPOINT = "asr.tencentcloudapi.com"
TENCENT_ASR_URL = f"https://{TENCENT_ASR_ENDPOINT}"

_ASR_FORMAT_MAP = {"wav": "wav", "mp3": "mp3", "m4a": "m4a", "webm": "webm"}


def _check_asr_rate_limit(ip: str) -> bool:
    now = time.time()
    timestamps = _asr_rate_limit[ip]
    _asr_rate_limit[ip] = [t for t in timestamps if now - t < _ASR_RATE_LIMIT_WINDOW]
    if len(_asr_rate_limit[ip]) >= _ASR_RATE_LIMIT_MAX:
        return False
    _asr_rate_limit[ip].append(now)
    return True


def _tc3_hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _build_asr_authorization(
    secret_id: str, secret_key: str, payload: str, timestamp: int,
) -> str:
    service = "asr"
    action = "SentenceRecognition"
    algorithm = "TC3-HMAC-SHA256"
    date_str = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

    ct = "application/json; charset=utf-8"
    canonical_headers = (
        f"content-type:{ct}\nhost:{TENCENT_ASR_ENDPOINT}\nx-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    )

    credential_scope = f"{date_str}/{service}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

    secret_date = _tc3_hmac_sha256(("TC3" + secret_key).encode("utf-8"), date_str)
    secret_service = _tc3_hmac_sha256(secret_date, service)
    secret_signing = _tc3_hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


async def _call_tencent_asr(
    secret_id: str, secret_key: str, audio_data: bytes, voice_format: str,
) -> dict:
    audio_b64 = base64.b64encode(audio_data).decode("utf-8")
    body_obj = {
        "EngSerViceType": "16k_zh",
        "SourceType": 1,
        "Data": audio_b64,
        "DataLen": len(audio_data),
        "VoiceFormat": _ASR_FORMAT_MAP.get(voice_format, voice_format),
    }
    payload = json.dumps(body_obj)

    timestamp = int(time.time())
    action = "SentenceRecognition"
    version = "2019-06-14"
    ct = "application/json; charset=utf-8"

    authorization = _build_asr_authorization(secret_id, secret_key, payload, timestamp)

    headers = {
        "Authorization": authorization,
        "Content-Type": ct,
        "Host": TENCENT_ASR_ENDPOINT,
        "X-TC-Action": action,
        "X-TC-Version": version,
        "X-TC-Timestamp": str(timestamp),
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(TENCENT_ASR_URL, headers=headers, content=payload)
        resp.raise_for_status()
        return resp.json()


async def _get_optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> Optional[User]:
    from app.core.config import settings
    from jose import JWTError, jwt

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        result = await db.execute(select(User).where(User.id == int(user_id)))
        return result.scalar_one_or_none()
    except (JWTError, ValueError):
        return None


def _compute_score(keyword: str, title: str, summary: Optional[str], tags: Optional[list]) -> float:
    kw = keyword.lower()
    score = 0.0
    if title and kw in title.lower():
        score += 100.0
        if title.lower().startswith(kw):
            score += 50.0
    if tags:
        tag_str = " ".join(str(t) for t in tags).lower() if isinstance(tags, list) else str(tags).lower()
        if kw in tag_str:
            score += 50.0
    if summary and kw in summary.lower():
        score += 20.0
    return score


# ──────── A01: 统一搜索 ────────


@router.get("", response_model=SearchResponse)
async def unified_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
    type: str = Query("all", description="搜索类型: all/article/news/service/points_mall"),
    source: str = Query("text", description="搜索来源: text/voice"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    current_user = await _get_optional_user(request, db)

    block_result = await db.execute(
        select(SearchBlockWord).where(
            SearchBlockWord.keyword == q,
            SearchBlockWord.is_active == True,  # noqa: E712
        )
    )
    search_source = source if source in ("text", "voice") else "text"

    block_word = block_result.scalar_one_or_none()
    if block_word:
        tip = block_word.tip_content if block_word.block_mode == "tip" else None
        empty_response = SearchResponse(
            items=[], total=0,
            type_counts={"article": 0, "news": 0, "service": 0, "points_mall": 0},
            block_tip=tip, page=page, page_size=page_size,
        )
        await _record_search_log(db, current_user, q, 0, {}, request, search_source)
        return empty_response

    like_pattern = f"%{q}%"
    all_items: list[SearchResultItem] = []
    type_counts = {"article": 0, "news": 0, "service": 0, "points_mall": 0}

    if type in ("all", "article"):
        stmt = select(Article).where(
            Article.status == ContentStatus.published,
            or_(
                Article.title.like(like_pattern),
                Article.summary.like(like_pattern),
                Article.tags.cast(String).like(like_pattern),
            ),
        )
        result = await db.execute(stmt)
        articles = result.scalars().all()
        type_counts["article"] = len(articles)
        for a in articles:
            tags_val = a.tags if isinstance(a.tags, list) else None
            score = _compute_score(q, a.title, a.summary, tags_val)
            all_items.append(SearchResultItem(
                id=a.id, type="article", title=a.title,
                summary=a.summary, cover_image=a.cover_image,
                tags=a.tags, score=score,
            ))

    if type in ("all", "news"):
        stmt = select(News).where(
            News.status == ContentStatus.published,
            or_(
                News.title.like(like_pattern),
                News.summary.like(like_pattern),
                News.tags.like(like_pattern),
            ),
        )
        result = await db.execute(stmt)
        news_rows = result.scalars().all()
        type_counts["news"] = len(news_rows)
        for n in news_rows:
            tags_list = [t.strip() for t in (n.tags or "").split(",") if t.strip()]
            score = _compute_score(q, n.title, n.summary, tags_list)
            all_items.append(SearchResultItem(
                id=n.id, type="news", title=n.title,
                summary=n.summary, cover_image=n.cover_image,
                tags=tags_list, score=score,
            ))

    if type in ("all", "service"):
        stmt = select(ServiceItem).where(
            ServiceItem.status == "active",
            or_(
                ServiceItem.name.like(like_pattern),
                ServiceItem.description.like(like_pattern),
            ),
        )
        result = await db.execute(stmt)
        services = result.scalars().all()
        type_counts["service"] = len(services)
        for s in services:
            imgs = s.images if isinstance(s.images, list) and s.images else None
            cover = imgs[0] if imgs else None
            score = _compute_score(q, s.name, s.description, None)
            all_items.append(SearchResultItem(
                id=s.id, type="service", title=s.name,
                summary=s.description, cover_image=cover,
                score=score,
            ))

    if type in ("all", "points_mall"):
        stmt = select(PointsMallItem).where(
            PointsMallItem.status == "active",
            or_(
                PointsMallItem.name.like(like_pattern),
                PointsMallItem.description.like(like_pattern),
            ),
        )
        result = await db.execute(stmt)
        mall_items = result.scalars().all()
        type_counts["points_mall"] = len(mall_items)
        for m in mall_items:
            imgs = m.images if isinstance(m.images, list) and m.images else None
            cover = imgs[0] if imgs else None
            score = _compute_score(q, m.name, m.description, None)
            all_items.append(SearchResultItem(
                id=m.id, type="points_mall", title=m.name,
                summary=m.description, cover_image=cover,
                score=score,
            ))

    all_items.sort(key=lambda x: x.score, reverse=True)
    total = len(all_items)
    start = (page - 1) * page_size
    paged_items = all_items[start : start + page_size]

    if current_user:
        await _upsert_search_history(db, current_user.id, q)
    await _update_hot_word(db, q, total)
    await _record_search_log(db, current_user, q, total, type_counts, request, search_source)

    return SearchResponse(
        items=paged_items, total=total, type_counts=type_counts,
        block_tip=None, page=page, page_size=page_size,
    )


async def _upsert_search_history(db: AsyncSession, user_id: int, keyword: str) -> None:
    result = await db.execute(
        select(SearchHistory).where(
            SearchHistory.user_id == user_id,
            SearchHistory.keyword == keyword,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.search_count += 1
        existing.updated_at = datetime.utcnow()
    else:
        db.add(SearchHistory(user_id=user_id, keyword=keyword))


async def _update_hot_word(db: AsyncSession, keyword: str, result_count: int) -> None:
    result = await db.execute(
        select(SearchHotWord).where(SearchHotWord.keyword == keyword)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.search_count += 1
        existing.result_count = result_count
        existing.updated_at = datetime.utcnow()
    else:
        db.add(SearchHotWord(keyword=keyword, search_count=1, result_count=result_count))


async def _record_search_log(
    db: AsyncSession, user: Optional[User], keyword: str,
    result_count: int, type_counts: dict, request: Request,
    source: str = "text",
) -> None:
    ip = request.client.host if request.client else None
    db.add(SearchLog(
        user_id=user.id if user else None,
        keyword=keyword,
        result_count=result_count,
        result_counts_json=json.dumps(type_counts) if type_counts else None,
        source=source,
        ip_address=ip,
    ))


# ──────── A02: 联想词建议 ────────


@router.get("/suggest", response_model=list[SearchSuggestItem])
async def search_suggest(
    q: str = Query(..., min_length=1, max_length=200),
    db: AsyncSession = Depends(get_db),
):
    like_pattern = f"%{q}%"

    recommend_result = await db.execute(
        select(SearchRecommendWord).where(
            SearchRecommendWord.is_active == True,  # noqa: E712
            SearchRecommendWord.keyword.like(like_pattern),
        ).order_by(SearchRecommendWord.sort_order).limit(10)
    )
    recommends = recommend_result.scalars().all()

    hot_result = await db.execute(
        select(SearchHotWord).where(
            SearchHotWord.keyword.like(like_pattern),
        ).order_by(SearchHotWord.search_count.desc()).limit(10)
    )
    hot_words = hot_result.scalars().all()

    drug_result = await db.execute(
        select(DrugSearchKeyword).where(
            DrugSearchKeyword.is_active == True,  # noqa: E712
            DrugSearchKeyword.keyword.like(like_pattern),
        ).limit(5)
    )
    drug_keywords = drug_result.scalars().all()

    seen = set()
    items: list[SearchSuggestItem] = []

    for dk in drug_keywords:
        if dk.keyword not in seen:
            seen.add(dk.keyword)
            items.append(SearchSuggestItem(
                keyword=dk.keyword, category_hint="拍照识药", is_drug_keyword=True,
            ))

    for r in recommends:
        if r.keyword not in seen:
            seen.add(r.keyword)
            items.append(SearchSuggestItem(
                keyword=r.keyword, category_hint=r.category_hint,
            ))

    for h in hot_words:
        if h.keyword not in seen:
            seen.add(h.keyword)
            items.append(SearchSuggestItem(
                keyword=h.keyword, category_hint=h.category_hint,
            ))

    return items[:15]


# ──────── A03: 热门搜索词 ────────


@router.get("/hot")
async def hot_keywords(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    recommend_result = await db.execute(
        select(SearchRecommendWord).where(
            SearchRecommendWord.is_active == True,  # noqa: E712
        ).order_by(SearchRecommendWord.sort_order).limit(limit)
    )
    recommends = recommend_result.scalars().all()

    seen = {r.keyword for r in recommends}
    remaining = limit - len(recommends)

    hot_items = []
    if remaining > 0:
        hot_result = await db.execute(
            select(SearchHotWord).order_by(SearchHotWord.search_count.desc()).limit(remaining + len(seen))
        )
        for h in hot_result.scalars().all():
            if h.keyword not in seen:
                hot_items.append({"keyword": h.keyword, "category_hint": h.category_hint, "source": "auto"})
                seen.add(h.keyword)
                if len(hot_items) >= remaining:
                    break

    result = [
        {"keyword": r.keyword, "category_hint": r.category_hint, "source": "recommend"}
        for r in recommends
    ] + hot_items

    return result[:limit]


# ──────── A04: 获取搜索历史（需登录） ────────


@router.get("/history")
async def get_search_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchHistory).where(
            SearchHistory.user_id == current_user.id,
        ).order_by(SearchHistory.updated_at.desc()).limit(limit)
    )
    histories = result.scalars().all()
    return [
        {"id": h.id, "keyword": h.keyword, "search_count": h.search_count, "updated_at": h.updated_at.isoformat()}
        for h in histories
    ]


# ──────── A05: 删除单条历史 ────────


@router.delete("/history/{history_id}")
async def delete_search_history(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchHistory).where(
            SearchHistory.id == history_id,
            SearchHistory.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.delete(record)
    return {"message": "删除成功"}


# ──────── A06: 清空搜索历史 ────────


@router.delete("/history")
async def clear_search_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete as sql_delete

    await db.execute(
        sql_delete(SearchHistory).where(SearchHistory.user_id == current_user.id)
    )
    return {"message": "已清空搜索历史"}


# ──────── A07: 记录搜索点击 ────────


@router.post("/log")
async def record_search_click(
    data: SearchLogCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    current_user = await _get_optional_user(request, db)
    ip = request.client.host if request.client else None
    db.add(SearchLog(
        user_id=current_user.id if current_user else None,
        keyword=data.keyword,
        clicked_type=data.clicked_type,
        clicked_item_id=data.clicked_item_id,
        ip_address=ip,
    ))
    return {"message": "记录成功"}


# ──────── A08: 获取ASR临时凭证 ────────


@router.post("/asr/token")
async def get_asr_token(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AsrConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config or not config.is_enabled:
        raise HTTPException(status_code=400, detail="语音识别服务未启用")

    secret_key = ""
    if config.secret_key_encrypted:
        try:
            secret_key = base64.b64decode(config.secret_key_encrypted).decode("utf-8")
        except Exception:
            secret_key = config.secret_key_encrypted

    return {
        "provider": config.provider,
        "app_id": config.app_id,
        "secret_id": config.secret_id,
        "temp_credential": secret_key[:8] + "****" if len(secret_key) > 8 else "****",
        "supported_dialects": config.supported_dialects,
    }


# ──────── A08-B: 语音识别 ────────


@router.post("/asr/recognize", response_model=AsrRecognizeResponse)
async def asr_recognize(
    request: Request,
    audio_file: UploadFile = File(..., description="录音文件（wav/mp3/m4a/webm）"),
    format: str = Form("wav", description="音频格式"),
    sample_rate: int = Form(16000, description="采样率"),
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_asr_rate_limit(client_ip):
        return AsrRecognizeResponse(
            success=False, error="请求过于频繁，请稍后再试", error_code="RATE_LIMITED",
        )

    result = await db.execute(select(AsrConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config or not config.is_enabled:
        return AsrRecognizeResponse(
            success=False, error="ASR 服务未启用", error_code="ASR_DISABLED",
        )

    secret_key = ""
    if config.secret_key_encrypted:
        try:
            secret_key = base64.b64decode(config.secret_key_encrypted).decode("utf-8")
        except Exception:
            secret_key = config.secret_key_encrypted

    audio_data = await audio_file.read()
    if not audio_data:
        return AsrRecognizeResponse(
            success=False, error="音频文件为空", error_code="AUDIO_EMPTY",
        )

    try:
        resp_data = await _call_tencent_asr(
            secret_id=config.secret_id or "",
            secret_key=secret_key,
            audio_data=audio_data,
            voice_format=format,
        )
    except httpx.TimeoutException:
        return AsrRecognizeResponse(
            success=False, error="语音识别超时，请重试", error_code="RECOGNIZE_TIMEOUT",
        )
    except Exception as e:
        logger.error("ASR call failed: %s", e, exc_info=True)
        return AsrRecognizeResponse(
            success=False, error=f"语音识别服务异常: {e}", error_code="ASR_ERROR",
        )

    response_body = resp_data.get("Response", {})
    if "Error" in response_body:
        err = response_body["Error"]
        return AsrRecognizeResponse(
            success=False,
            error=f"语音识别失败({err.get('Code', '')}): {err.get('Message', '')}",
            error_code="ASR_API_ERROR",
        )

    text = response_body.get("Result", "")
    if not text or not text.strip():
        return AsrRecognizeResponse(
            success=False, error="未检测到语音内容", error_code="AUDIO_EMPTY",
        )

    return AsrRecognizeResponse(
        success=True,
        data={"text": text.strip(), "confidence": 0.95},
    )


# ──────── A09: 拍照识药触发词 ────────


@router.get("/drug-keywords", response_model=list[DrugSearchKeywordResponse])
async def get_drug_keywords(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DrugSearchKeyword).where(DrugSearchKeyword.is_active == True)  # noqa: E712
    )
    return result.scalars().all()
