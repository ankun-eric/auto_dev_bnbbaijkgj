"""历史报告与对比分析 API。

端点：
- GET  /api/report-history/list              - 历史报告列表（分页）
- GET  /api/report-history/{id}              - 报告详情
- GET  /api/report-history/comparison/{id}   - 对比报告详情
- POST /api/report-history/compare           - 发起对比分析
- DELETE /api/report-history/{id}            - 软删除报告
- POST /api/report-history/share             - 生成分享
- GET  /api/report-history/shared/{token}    - 查看分享报告
- POST /api/report-history/save-medical      - 保存到就医资料
- POST /api/report-history/sync              - 从 AI 对话同步报告到历史
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    ChatSession,
    CheckupIndicator,
    CheckupReport,
    FamilyMember,
    ReportHistory,
    User,
)
from app.services.ai_service import call_ai_model_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/report-history", tags=["历史报告与对比分析"])


# ──────────────── Schemas ────────────────


class ReportHistoryItem(BaseModel):
    id: int
    report_name: str
    report_date: Optional[str] = None
    source_type: str
    ai_summary: Optional[str] = None
    is_comparison: bool = False
    created_at: Optional[str] = None
    share_token: Optional[str] = None


class ReportHistoryListResponse(BaseModel):
    items: List[ReportHistoryItem]
    total: int
    page: int
    page_size: int


class IndicatorItem(BaseModel):
    name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None


class ReportHistoryDetailResponse(BaseModel):
    id: int
    report_name: str
    report_date: Optional[str] = None
    source_type: str
    original_images: Optional[List[str]] = None
    ai_interpretation: Optional[str] = None
    indicators_data: Optional[List[IndicatorItem]] = None
    is_comparison: bool = False


class ComparisonReportInfo(BaseModel):
    id: Optional[int] = None
    report_name: Optional[str] = None
    report_date: Optional[str] = None


class ComparisonDetailResponse(BaseModel):
    id: int
    comparison_content: Optional[Dict[str, Any]] = None
    report_a_info: Optional[ComparisonReportInfo] = None
    report_b_info: Optional[ComparisonReportInfo] = None


class CompareRequest(BaseModel):
    member_id: int
    report_history_ids: List[int] = Field(..., min_length=2, max_length=2)


class CompareResponse(BaseModel):
    id: int
    message: str = "对比分析完成"


class ShareRequest(BaseModel):
    report_history_id: int
    share_type: str = "link"


class ShareResponse(BaseModel):
    share_token: str
    share_type: str
    share_url: str


class SaveMedicalRequest(BaseModel):
    report_history_id: int


class SyncRequest(BaseModel):
    report_id: int
    session_id: int
    member_id: int


# ──────────────── Helpers ────────────────


def _extract_images(report: CheckupReport) -> List[str]:
    """从 CheckupReport 提取所有原图 URL。"""
    images: list[str] = []
    file_urls_val = getattr(report, "file_urls", None)
    if isinstance(file_urls_val, list) and file_urls_val:
        images = [u for u in file_urls_val if u]
    elif isinstance(file_urls_val, str) and file_urls_val:
        try:
            parsed = json.loads(file_urls_val)
            if isinstance(parsed, list):
                images = [u for u in parsed if u]
        except Exception:
            pass
    if not images:
        if report.file_url:
            images.append(report.file_url)
        if report.thumbnail_url and report.thumbnail_url != report.file_url:
            images.append(report.thumbnail_url)
    return images


def _report_title(report: CheckupReport) -> str:
    if getattr(report, "title", None):
        return report.title  # type: ignore[return-value]
    d = report.report_date or (report.created_at.date() if report.created_at else datetime.utcnow().date())
    return f"{d.strftime('%Y-%m-%d')} 体检报告"


async def _load_indicators_from_report(db: AsyncSession, report_id: int) -> List[Dict[str, Any]]:
    """从 CheckupIndicator 表加载指标数据。"""
    q = await db.execute(
        select(CheckupIndicator).where(CheckupIndicator.report_id == report_id)
    )
    rows = q.scalars().all()
    result = []
    for ind in rows:
        status_val = ind.status.value if hasattr(ind.status, "value") else str(ind.status) if ind.status else None
        result.append({
            "name": ind.indicator_name,
            "value": ind.value,
            "unit": ind.unit,
            "reference_range": ind.reference_range,
            "status": status_val,
            "category": ind.category,
        })
    return result


async def _verify_ownership(db: AsyncSession, record: ReportHistory, user: User) -> None:
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="报告不存在")
    if record.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该报告")


async def _get_report_history_info(db: AsyncSession, record_id: int) -> Optional[ComparisonReportInfo]:
    """获取一条 ReportHistory 的简要信息，用于对比报告详情。"""
    rec = await db.get(ReportHistory, record_id)
    if not rec:
        return None
    return ComparisonReportInfo(
        id=rec.id,
        report_name=rec.report_name,
        report_date=rec.report_date.strftime("%Y-%m-%d") if rec.report_date else None,
    )


# ──────────────── 1. 历史报告列表 ────────────────


@router.get("/list", response_model=ReportHistoryListResponse)
async def report_history_list(
    member_id: int = Query(..., description="咨询人ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fm = await db.get(FamilyMember, member_id)
    if not fm or fm.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="咨询人不存在或无权限")

    base_filter = and_(
        ReportHistory.family_member_id == member_id,
        ReportHistory.user_id == current_user.id,
        ReportHistory.is_deleted.is_(False),
    )

    count_q = await db.execute(select(func.count()).select_from(ReportHistory).where(base_filter))
    total = count_q.scalar() or 0

    offset = (page - 1) * page_size
    q = await db.execute(
        select(ReportHistory)
        .where(base_filter)
        .order_by(desc(ReportHistory.report_date), desc(ReportHistory.created_at))
        .offset(offset)
        .limit(page_size)
    )
    rows = q.scalars().all()

    items = []
    for r in rows:
        items.append(ReportHistoryItem(
            id=r.id,
            report_name=r.report_name,
            report_date=r.report_date.strftime("%Y-%m-%d") if r.report_date else None,
            source_type=r.source_type or "体检报告",
            ai_summary=r.ai_summary,
            is_comparison=bool(r.is_comparison),
            created_at=r.created_at.isoformat() if r.created_at else None,
            share_token=r.share_token,
        ))

    return ReportHistoryListResponse(items=items, total=total, page=page, page_size=page_size)


# ──────────────── 2. 报告详情 ────────────────


@router.get("/comparison/{record_id}", response_model=ComparisonDetailResponse)
async def report_history_comparison(
    record_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对比报告详情（路由在通用详情之前注册以避免路径冲突）。"""
    record = await db.get(ReportHistory, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="报告不存在")
    await _verify_ownership(db, record, current_user)

    if not record.is_comparison:
        raise HTTPException(status_code=400, detail="该报告不是对比报告")

    report_a_info = None
    report_b_info = None
    if record.compare_report_a_id:
        report_a_info = await _get_report_history_info(db, record.compare_report_a_id)
    if record.compare_report_b_id:
        report_b_info = await _get_report_history_info(db, record.compare_report_b_id)

    return ComparisonDetailResponse(
        id=record.id,
        comparison_content=record.comparison_content,
        report_a_info=report_a_info,
        report_b_info=report_b_info,
    )


@router.get("/{record_id}", response_model=ReportHistoryDetailResponse)
async def report_history_detail(
    record_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(ReportHistory, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="报告不存在")
    await _verify_ownership(db, record, current_user)

    indicators = record.indicators_data
    if not record.is_comparison and not indicators and record.report_id:
        indicators = await _load_indicators_from_report(db, record.report_id)

    indicator_items = None
    if indicators and isinstance(indicators, list):
        indicator_items = [
            IndicatorItem(
                name=ind.get("name", ""),
                value=ind.get("value"),
                unit=ind.get("unit"),
                reference_range=ind.get("reference_range"),
                status=ind.get("status"),
                category=ind.get("category"),
            )
            for ind in indicators
        ]

    return ReportHistoryDetailResponse(
        id=record.id,
        report_name=record.report_name,
        report_date=record.report_date.strftime("%Y-%m-%d") if record.report_date else None,
        source_type=record.source_type or "体检报告",
        original_images=record.original_images,
        ai_interpretation=record.ai_interpretation,
        indicators_data=indicator_items,
        is_comparison=bool(record.is_comparison),
    )


# ──────────────── 4. 发起对比分析 ────────────────


_COMPARE_SYSTEM_PROMPT = """\
你是一位资深健康顾问。请根据以下两份体检报告的指标数据进行对比分析。
请严格返回以下 JSON 格式（不要包含其他文字）：
{
  "indicator_changes": [{"name": "指标名", "report_a_value": "值A", "report_b_value": "值B", "change": "上升/下降/不变", "significance": "说明"}],
  "improved_indicators": ["改善的指标名列表"],
  "worsened_indicators": ["恶化的指标名列表"],
  "health_advice": "综合健康建议文本",
  "risk_warnings": ["风险预警列表"]
}
"""


@router.post("/compare", response_model=CompareResponse)
async def report_history_compare(
    body: CompareRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.report_history_ids[0] == body.report_history_ids[1]:
        raise HTTPException(status_code=400, detail="不能对比同一份报告")

    fm = await db.get(FamilyMember, body.member_id)
    if not fm or fm.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="咨询人不存在或无权限")

    report_a = await db.get(ReportHistory, body.report_history_ids[0])
    report_b = await db.get(ReportHistory, body.report_history_ids[1])

    if not report_a or report_a.is_deleted:
        raise HTTPException(status_code=404, detail=f"报告 {body.report_history_ids[0]} 不存在")
    if not report_b or report_b.is_deleted:
        raise HTTPException(status_code=404, detail=f"报告 {body.report_history_ids[1]} 不存在")

    if report_a.user_id != current_user.id or report_b.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问报告")
    if report_a.family_member_id != body.member_id or report_b.family_member_id != body.member_id:
        raise HTTPException(status_code=400, detail="两份报告必须属于同一咨询人")

    indicators_a = report_a.indicators_data or []
    indicators_b = report_b.indicators_data or []
    interp_a = report_a.ai_interpretation or ""
    interp_b = report_b.ai_interpretation or ""

    user_msg = (
        f"## 报告A：{report_a.report_name}（{report_a.report_date or '未知日期'}）\n"
        f"### 指标数据\n{json.dumps(indicators_a, ensure_ascii=False, indent=2)}\n"
        f"### AI 解读\n{interp_a}\n\n"
        f"## 报告B：{report_b.report_name}（{report_b.report_date or '未知日期'}）\n"
        f"### 指标数据\n{json.dumps(indicators_b, ensure_ascii=False, indent=2)}\n"
        f"### AI 解读\n{interp_b}\n\n"
        f"请对比两份报告，分析指标变化、改善与恶化情况，给出综合健康建议和风险预警。"
    )

    messages = [
        {"role": "system", "content": _COMPARE_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    full_text = ""
    try:
        async for chunk in call_ai_model_stream(messages=messages, system_prompt="", db=db):
            ctype = chunk.get("type")
            content = chunk.get("content", "") or ""
            if ctype == "delta" and content:
                full_text += content
            elif ctype == "done":
                final = chunk.get("content") or full_text
                if final:
                    full_text = final
    except Exception as e:
        logger.error("AI 对比分析失败: %s", e)
        raise HTTPException(status_code=500, detail="AI 对比分析失败，请稍后重试")

    comparison_content: Dict[str, Any] = {}
    try:
        cleaned = full_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        comparison_content = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("AI 对比分析返回非 JSON，原文保存")
        comparison_content = {
            "raw_text": full_text,
            "indicator_changes": [],
            "improved_indicators": [],
            "worsened_indicators": [],
            "health_advice": full_text,
            "risk_warnings": [],
        }

    date_a_str = report_a.report_date.strftime("%Y-%m-%d") if report_a.report_date else "未知"
    date_b_str = report_b.report_date.strftime("%Y-%m-%d") if report_b.report_date else "未知"
    compare_name = f"{report_a.report_name} vs {report_b.report_name}"

    new_record = ReportHistory(
        user_id=current_user.id,
        family_member_id=body.member_id,
        report_name=compare_name[:200],
        report_date=datetime.utcnow().date(),
        source_type="对比报告",
        ai_summary=comparison_content.get("health_advice", "")[:500] if isinstance(comparison_content, dict) else None,
        is_comparison=True,
        compare_report_a_id=report_a.id,
        compare_report_b_id=report_b.id,
        comparison_content=comparison_content,
        ai_interpretation=full_text,
    )
    db.add(new_record)
    await db.flush()

    return CompareResponse(id=new_record.id, message="对比分析完成")


# ──────────────── 5. 删除报告 ────────────────


@router.delete("/{record_id}")
async def report_history_delete(
    record_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(ReportHistory, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="报告不存在")
    await _verify_ownership(db, record, current_user)

    record.is_deleted = True
    record.updated_at = datetime.utcnow()

    if not record.is_comparison:
        cascade_q = await db.execute(
            select(ReportHistory).where(
                and_(
                    ReportHistory.user_id == current_user.id,
                    ReportHistory.is_comparison.is_(True),
                    ReportHistory.is_deleted.is_(False),
                    or_(
                        ReportHistory.compare_report_a_id == record_id,
                        ReportHistory.compare_report_b_id == record_id,
                    ),
                )
            )
        )
        for comp in cascade_q.scalars().all():
            comp.is_deleted = True
            comp.updated_at = datetime.utcnow()

    return {"success": True, "message": "删除成功"}


# ──────────────── 6. 生成分享 ────────────────


@router.post("/share", response_model=ShareResponse)
async def report_history_share(
    body: ShareRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(ReportHistory, body.report_history_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="报告不存在")
    await _verify_ownership(db, record, current_user)

    if not record.share_token:
        record.share_token = uuid.uuid4().hex
        record.updated_at = datetime.utcnow()

    share_url = f"/api/report-history/shared/{record.share_token}"

    return ShareResponse(
        share_token=record.share_token,
        share_type=body.share_type,
        share_url=share_url,
    )


# ──────────────── 7. 查看分享报告 ────────────────


@router.get("/shared/{share_token}")
async def report_history_shared(
    share_token: str = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(
        select(ReportHistory).where(
            and_(
                ReportHistory.share_token == share_token,
                ReportHistory.is_deleted.is_(False),
            )
        )
    )
    record = q.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="分享的报告不存在或已被删除")

    indicators = record.indicators_data
    if not record.is_comparison and not indicators and record.report_id:
        indicators = await _load_indicators_from_report(db, record.report_id)

    result: Dict[str, Any] = {
        "id": record.id,
        "report_name": record.report_name,
        "report_date": record.report_date.strftime("%Y-%m-%d") if record.report_date else None,
        "source_type": record.source_type,
        "ai_summary": record.ai_summary,
        "original_images": record.original_images,
        "ai_interpretation": record.ai_interpretation,
        "indicators_data": indicators,
        "is_comparison": bool(record.is_comparison),
    }

    if record.is_comparison:
        result["comparison_content"] = record.comparison_content
        if record.compare_report_a_id:
            a_info = await _get_report_history_info(db, record.compare_report_a_id)
            result["report_a_info"] = a_info.model_dump() if a_info else None
        if record.compare_report_b_id:
            b_info = await _get_report_history_info(db, record.compare_report_b_id)
            result["report_b_info"] = b_info.model_dump() if b_info else None

    return result


# ──────────────── 8. 保存到就医资料 ────────────────


@router.post("/save-medical")
async def report_history_save_medical(
    body: SaveMedicalRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(ReportHistory, body.report_history_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="报告不存在")
    await _verify_ownership(db, record, current_user)

    return {"success": True, "message": "已保存到就医资料"}


# ──────────────── 9. 同步报告到历史记录 ────────────────


@router.post("/sync")
async def report_history_sync(
    body: SyncRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(CheckupReport, body.report_id)
    if not report or report.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    fm = await db.get(FamilyMember, body.member_id)
    if not fm or fm.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="咨询人不存在或无权限")

    session = await db.get(ChatSession, body.session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")

    existing_q = await db.execute(
        select(ReportHistory).where(
            and_(
                ReportHistory.report_id == body.report_id,
                ReportHistory.session_id == body.session_id,
                ReportHistory.user_id == current_user.id,
                ReportHistory.is_deleted.is_(False),
            )
        )
    )
    existing = existing_q.scalar_one_or_none()
    if existing:
        return {"success": True, "id": existing.id, "message": "记录已存在"}

    images = _extract_images(report)
    indicators = await _load_indicators_from_report(db, report.id)

    ai_interpretation = report.ai_analysis or ""
    ai_summary = None
    if report.ai_analysis:
        ai_summary = report.ai_analysis[:200]

    new_record = ReportHistory(
        user_id=current_user.id,
        family_member_id=body.member_id,
        report_id=report.id,
        session_id=body.session_id,
        report_name=report.title or _report_title(report),
        report_date=report.report_date,
        source_type="体检报告",
        ai_summary=ai_summary,
        is_comparison=False,
        original_images=images if images else None,
        ai_interpretation=ai_interpretation if ai_interpretation else None,
        indicators_data=indicators if indicators else None,
    )
    db.add(new_record)
    await db.flush()

    return {"success": True, "id": new_record.id, "message": "同步成功"}
