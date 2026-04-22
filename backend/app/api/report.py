import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    CheckupIndicator,
    CheckupReport,
    FamilyMember,
    HealthProfile,
    OcrConfig,
    PromptTemplate,
    ReportAlert,
    User,
)
from app.schemas.report import (
    AlertListResponse,
    AlertResponse,
    CompareIndicatorItem,
    CompareScoreDiff,
    EnhancedCategoryView,
    EnhancedIndicatorItem,
    EnhancedReportAnalysisResponse,
    FamilyMemberBrief,
    HealthScoreInfo,
    IndicatorDetail,
    IndicatorDetailAdvice,
    IndicatorResponse,
    OcrConfigResponse,
    OcrConfigUpdate,
    ReportAnalysisResponse,
    ReportCompareResponse,
    ReportDetailResponse,
    ReportListItem,
    ReportListResponse,
    ReportUploadResponse,
    ShareCreateResponse,
    ShareViewResponse,
    SummaryInfo,
    TrendAnalysisRequest,
    TrendAnalysisResponse,
    TrendDataPoint,
    TrendDataResponse,
    CategoryView,
)
from app.services.ai_service import analyze_report_compare, analyze_report_structured, analyze_trend
from app.services.ocr_service import (
    check_image_quality,
    ensure_access_token,
    extract_pdf_text,
    ocr_recognize,
)
from app.utils.cos_helper import try_cos_upload
from app.utils.file_helper import read_file_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["体检报告"])

ALLOWED_REPORT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
    "application/pdf",
}
MAX_REPORT_SIZE = 20 * 1024 * 1024
DISCLAIMER = "以上解读仅供健康参考，不构成医疗诊断或治疗建议，如有异常请及时就医。"


async def _get_ocr_config(db: AsyncSession) -> Optional[OcrConfig]:
    result = await db.execute(select(OcrConfig).limit(1))
    return result.scalar_one_or_none()


# ──────────────── Upload ────────────────


@router.post("/report/upload", response_model=ReportUploadResponse)
async def upload_report(
    file: UploadFile = File(...),
    family_member_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ocr_cfg = await _get_ocr_config(db)
    if not ocr_cfg or not ocr_cfg.enabled:
        raise HTTPException(status_code=503, detail="解读功能暂时维护中，请稍后再试")

    if file.content_type not in ALLOWED_REPORT_TYPES:
        raise HTTPException(status_code=400, detail="不支持的文件格式，请上传图片(JPG/PNG)或PDF")

    content = await file.read()
    if len(content) > MAX_REPORT_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过20MB")

    file_type = "pdf" if file.content_type == "application/pdf" else "image"

    if file_type == "image":
        quality = check_image_quality(content)
        if not quality["ok"]:
            raise HTTPException(status_code=400, detail=quality["message"])

    cos_url = await try_cos_upload(db, content, file.filename or "report.jpg", file.content_type, "reports/")
    if cos_url:
        file_url = cos_url
    else:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(file.filename or "report.jpg")[1]
        filename = f"report_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(settings.UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        file_url = f"/uploads/{filename}"

    ocr_text = ""
    ocr_result_dict = None
    try:
        if file_type == "pdf":
            ocr_text = extract_pdf_text(content)
        else:
            if ocr_cfg.api_key and ocr_cfg.secret_key_encrypted:
                token, expires_at = await ensure_access_token(
                    ocr_cfg.api_key, ocr_cfg.secret_key_encrypted,
                    ocr_cfg.access_token, ocr_cfg.token_expires_at,
                )
                ocr_cfg.access_token = token
                ocr_cfg.token_expires_at = expires_at
                await db.flush()
                ocr_text = await ocr_recognize(content, ocr_cfg.ocr_type or "general_basic", token)
        if ocr_text:
            ocr_result_dict = {"text": ocr_text}
    except Exception:
        pass

    report = CheckupReport(
        user_id=current_user.id,
        file_url=file_url,
        thumbnail_url=file_url if file_type == "image" else None,
        file_type=file_type,
        status="pending",
        ocr_result=ocr_result_dict,
        family_member_id=family_member_id,
    )
    db.add(report)
    await db.flush()

    return ReportUploadResponse(
        id=report.id,
        file_url=file_url,
        thumbnail_url=report.thumbnail_url,
        file_type=file_type,
        status="pending",
        message="上传成功，请调用解读接口进行AI解读",
    )


# ──────────────── OCR (internal) ────────────────


@router.post("/report/ocr")
async def report_ocr(
    report_id: int = Body(embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(CheckupReport, report_id)
    if not report or report.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    ocr_cfg = await _get_ocr_config(db)
    if not ocr_cfg or not ocr_cfg.enabled:
        raise HTTPException(status_code=503, detail="解读功能暂时维护中，请稍后再试")

    file_data = await read_file_content(report.file_url or "")
    if not file_data:
        raise HTTPException(status_code=404, detail="报告文件不存在或已失效，请重新上传")

    if report.file_type == "pdf":
        ocr_text = extract_pdf_text(file_data)
    else:
        if not ocr_cfg.api_key or not ocr_cfg.secret_key_encrypted:
            raise HTTPException(status_code=500, detail="OCR服务未配置API密钥")

        token, expires_at = await ensure_access_token(
            ocr_cfg.api_key,
            ocr_cfg.secret_key_encrypted,
            ocr_cfg.access_token,
            ocr_cfg.token_expires_at,
        )
        ocr_cfg.access_token = token
        ocr_cfg.token_expires_at = expires_at
        await db.flush()

        ocr_text = await ocr_recognize(file_data, ocr_cfg.ocr_type or "general_basic", token)

    report.ocr_result = {"text": ocr_text}
    await db.flush()

    return {"report_id": report_id, "ocr_text": ocr_text}


# ──────────────── AI Analyze ────────────────


def _risk_level_to_status(risk_level: int) -> str:
    """Map enhanced riskLevel (1-5) to legacy IndicatorStatus string."""
    if risk_level <= 2:
        return "normal"
    if risk_level <= 3:
        return "abnormal"
    return "critical"


@router.post("/report/analyze", deprecated=True)
async def analyze_report_deprecated(
    report_id: int = Body(embed=True, default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[2026-04-23] 已下线：结构化体检解读。请改用 POST /api/report/interpret/start。"""
    raise HTTPException(
        status_code=410,
        detail="该接口已下线，请改用 POST /api/report/interpret/start 进入对话式报告解读",
    )


async def _analyze_report_legacy_unused(
    report_id: int,
    current_user: User,
    db: AsyncSession,
):
    result = await db.execute(
        select(CheckupReport)
        .options(selectinload(CheckupReport.checkup_indicators))
        .where(CheckupReport.id == report_id, CheckupReport.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    ocr_cfg = await _get_ocr_config(db)
    if not ocr_cfg or not ocr_cfg.enabled:
        raise HTTPException(status_code=503, detail="解读功能暂时维护中，请稍后再试")

    ocr_text = ""
    if report.ocr_result and isinstance(report.ocr_result, dict):
        ocr_text = report.ocr_result.get("text", "")

    if not ocr_text:
        file_data = await read_file_content(report.file_url or "")
        if not file_data:
            raise HTTPException(
                status_code=400,
                detail="报告文件不存在或已失效，请重新上传",
            )
        if report.file_type == "pdf":
            ocr_text = extract_pdf_text(file_data)
        else:
            if ocr_cfg.api_key and ocr_cfg.secret_key_encrypted:
                token, expires_at = await ensure_access_token(
                    ocr_cfg.api_key, ocr_cfg.secret_key_encrypted,
                    ocr_cfg.access_token, ocr_cfg.token_expires_at,
                )
                ocr_cfg.access_token = token
                ocr_cfg.token_expires_at = expires_at
                ocr_text = await ocr_recognize(file_data, ocr_cfg.ocr_type or "general_basic", token)
        if ocr_text:
            report.ocr_result = {"text": ocr_text}

    if not ocr_text:
        raise HTTPException(
            status_code=400,
            detail="OCR未能识别到文字内容，请上传更清晰的体检报告图片",
        )

    report.status = "analyzing"
    await db.flush()

    user_profile = None
    use_health_profile = True

    if report.family_member_id:
        fm = await db.get(FamilyMember, report.family_member_id)
        if fm and not fm.is_self:
            user_profile = {
                "gender": fm.gender,
                "birthday": str(fm.birthday) if fm.birthday else None,
                "height": fm.height,
                "weight": fm.weight,
            }
            use_health_profile = False

    if use_health_profile:
        profile_result = await db.execute(
            select(HealthProfile)
            .where(HealthProfile.user_id == current_user.id)
            .order_by(HealthProfile.id.desc())
            .limit(1)
        )
        hp = profile_result.scalar_one_or_none()
        if hp:
            user_profile = {
                "gender": hp.gender,
                "birthday": str(hp.birthday) if hp.birthday else None,
                "height": hp.height,
                "weight": hp.weight,
            }

    tpl_result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.prompt_type == "checkup_report",
            PromptTemplate.is_active == True,  # noqa: E712
        )
    )
    active_tpl = tpl_result.scalar_one_or_none()
    custom_prompt = active_tpl.content if active_tpl else None

    try:
        analysis = await analyze_report_structured(ocr_text, user_profile, db, custom_prompt=custom_prompt)
    except Exception as e:
        logger.error(
            "AI解读失败 report_id=%s user_id=%s: %s",
            report_id, current_user.id, e, exc_info=True,
        )
        report.status = "failed"
        await db.flush()
        error_detail = str(e)
        if "timeout" in error_detail.lower() or "timed out" in error_detail.lower():
            raise HTTPException(status_code=500, detail="AI解读超时，请稍后重试")
        if "connect" in error_detail.lower():
            raise HTTPException(status_code=500, detail="AI服务连接失败，请稍后重试")
        raise HTTPException(status_code=500, detail=f"AI解读失败: {error_detail}")

    for old_ind in list(report.checkup_indicators):
        await db.delete(old_ind)
    await db.flush()

    abnormal_count = 0
    categories_out: list[EnhancedCategoryView] = []

    for cat in analysis.get("categories", []):
        cat_name = cat.get("name", cat.get("category_name", "其他"))
        cat_emoji = cat.get("emoji", "📋")
        cat_items: list[EnhancedIndicatorItem] = []

        for ind in cat.get("items", cat.get("indicators", [])):
            risk_level = ind.get("riskLevel", 2)
            risk_name = ind.get("riskName", "正常")
            status_val = _risk_level_to_status(risk_level)

            indicator = CheckupIndicator(
                report_id=report.id,
                indicator_name=ind.get("name", ""),
                value=ind.get("value"),
                unit=ind.get("unit"),
                reference_range=ind.get("referenceRange", ind.get("reference_range")),
                status=status_val,
                category=cat_name,
                advice=ind.get("detail", {}).get("explanation", "") if isinstance(ind.get("detail"), dict) else ind.get("advice"),
            )
            db.add(indicator)

            detail_raw = ind.get("detail")
            detail_obj = None
            if isinstance(detail_raw, dict):
                detail_obj = IndicatorDetailAdvice(
                    explanation=detail_raw.get("explanation"),
                    possibleCauses=detail_raw.get("possibleCauses"),
                    dietAdvice=detail_raw.get("dietAdvice"),
                    exerciseAdvice=detail_raw.get("exerciseAdvice"),
                    lifestyleAdvice=detail_raw.get("lifestyleAdvice"),
                    recheckAdvice=detail_raw.get("recheckAdvice"),
                    medicalAdvice=detail_raw.get("medicalAdvice"),
                )

            item = EnhancedIndicatorItem(
                name=ind.get("name", ""),
                value=ind.get("value"),
                unit=ind.get("unit"),
                referenceRange=ind.get("referenceRange", ind.get("reference_range")),
                riskLevel=risk_level,
                riskName=risk_name,
                detail=detail_obj,
            )
            cat_items.append(item)

            if risk_level >= 3:
                abnormal_count += 1

        categories_out.append(EnhancedCategoryView(name=cat_name, emoji=cat_emoji, items=cat_items))

    health_score_raw = analysis.get("healthScore")
    health_score_obj = None
    score_value = None
    if isinstance(health_score_raw, dict):
        score_value = health_score_raw.get("score")
        health_score_obj = HealthScoreInfo(
            score=score_value or 0,
            level=health_score_raw.get("level", "待分析"),
            comment=health_score_raw.get("comment", ""),
        )

    summary_raw = analysis.get("summary")
    summary_obj = None
    if isinstance(summary_raw, dict):
        summary_obj = SummaryInfo(
            totalItems=summary_raw.get("totalItems", 0),
            abnormalCount=summary_raw.get("abnormalCount", abnormal_count),
            excellentCount=summary_raw.get("excellentCount", 0),
            normalCount=summary_raw.get("normalCount", 0),
        )

    report.ai_analysis = health_score_obj.comment if health_score_obj else analysis.get("overall_assessment", "")
    report.ai_analysis_json = analysis
    report.abnormal_count = abnormal_count
    report.health_score = score_value
    report.status = "completed"
    await db.flush()

    return EnhancedReportAnalysisResponse(
        report_id=report.id,
        status="completed",
        healthScore=health_score_obj,
        summary=summary_obj,
        categories=categories_out,
        disclaimer=analysis.get("disclaimer", DISCLAIMER),
    )


# ──────────────── Detail ────────────────


@router.get("/report/detail/{report_id}", response_model=ReportDetailResponse)
async def get_report_detail(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CheckupReport)
        .options(selectinload(CheckupReport.checkup_indicators))
        .where(CheckupReport.id == report_id, CheckupReport.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    indicators = [
        IndicatorResponse(
            id=ind.id,
            report_id=ind.report_id,
            indicator_name=ind.indicator_name,
            value=ind.value,
            unit=ind.unit,
            reference_range=ind.reference_range,
            status=ind.status.value if hasattr(ind.status, "value") else str(ind.status),
            category=ind.category,
            advice=ind.advice,
            created_at=ind.created_at,
        )
        for ind in report.checkup_indicators
    ]

    return ReportDetailResponse(
        id=report.id,
        user_id=report.user_id,
        report_date=report.report_date,
        report_type=report.report_type,
        file_url=report.file_url,
        thumbnail_url=report.thumbnail_url,
        file_type=report.file_type,
        ocr_result=report.ocr_result,
        ai_analysis=report.ai_analysis,
        ai_analysis_json=report.ai_analysis_json,
        abnormal_count=report.abnormal_count or 0,
        health_score=getattr(report, "health_score", None),
        status=report.status,
        indicators=indicators,
        created_at=report.created_at,
    )


# ──────────────── List ────────────────


@router.get("/report/list", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_query = select(CheckupReport).where(CheckupReport.user_id == current_user.id)

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query
        .options(selectinload(CheckupReport.family_member))
        .order_by(CheckupReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    reports = result.scalars().all()

    items = []
    for r in reports:
        fm_brief = None
        if r.family_member:
            fm_brief = FamilyMemberBrief(
                id=r.family_member.id,
                nickname=r.family_member.nickname,
                relationship_type=r.family_member.relationship_type,
                is_self=r.family_member.is_self,
            )
        items.append(ReportListItem(
            id=r.id,
            report_date=r.report_date,
            report_type=r.report_type,
            file_url=r.file_url,
            thumbnail_url=r.thumbnail_url,
            file_type=r.file_type,
            abnormal_count=r.abnormal_count or 0,
            health_score=getattr(r, "health_score", None),
            ai_analysis_json=r.ai_analysis_json,
            status=r.status,
            family_member=fm_brief,
            created_at=r.created_at,
        ))

    return ReportListResponse(items=items, total=total, page=page, page_size=page_size)


# ──────────────── Compare ────────────────


@router.post("/report/compare", deprecated=True)
async def compare_reports_deprecated(
    report_id_1: int = Body(default=0),
    report_id_2: int = Body(default=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[2026-04-23] 已下线：结构化对比。请改用 POST /api/report/compare/start。"""
    raise HTTPException(
        status_code=410,
        detail="该接口已下线，请改用 POST /api/report/compare/start 进入对话式报告对比",
    )


async def _compare_reports_legacy_unused(
    report_id_1: int,
    report_id_2: int,
    current_user: User,
    db: AsyncSession,
):
    r1_result = await db.execute(
        select(CheckupReport)
        .options(selectinload(CheckupReport.checkup_indicators))
        .where(CheckupReport.id == report_id_1, CheckupReport.user_id == current_user.id)
    )
    report1 = r1_result.scalar_one_or_none()
    if not report1:
        raise HTTPException(status_code=404, detail="第一份报告不存在")

    r2_result = await db.execute(
        select(CheckupReport)
        .options(selectinload(CheckupReport.checkup_indicators))
        .where(CheckupReport.id == report_id_2, CheckupReport.user_id == current_user.id)
    )
    report2 = r2_result.scalar_one_or_none()
    if not report2:
        raise HTTPException(status_code=404, detail="第二份报告不存在")

    def _build_indicator_map(report_obj):
        ind_map = {}
        for ind in report_obj.checkup_indicators:
            ind_map[ind.indicator_name] = {
                "value": ind.value,
                "unit": ind.unit,
                "reference_range": ind.reference_range,
                "status": ind.status.value if hasattr(ind.status, "value") else str(ind.status),
                "category": ind.category,
            }
        return ind_map

    prev_map = _build_indicator_map(report1)
    curr_map = _build_indicator_map(report2)
    all_names = list(dict.fromkeys(list(prev_map.keys()) + list(curr_map.keys())))

    def _status_to_risk(s):
        if s == "critical":
            return 5
        if s == "abnormal":
            return 3
        return 2

    indicators_out: list[CompareIndicatorItem] = []
    for name in all_names:
        prev = prev_map.get(name)
        curr = curr_map.get(name)
        direction = "new" if prev is None else "same"
        prev_risk = _status_to_risk(prev["status"]) if prev else None
        curr_risk = _status_to_risk(curr["status"]) if curr else None

        if report1.ai_analysis_json and isinstance(report1.ai_analysis_json, dict):
            for cat in report1.ai_analysis_json.get("categories", []):
                for it in cat.get("items", cat.get("indicators", [])):
                    if it.get("name") == name:
                        prev_risk = it.get("riskLevel", prev_risk)
        if report2.ai_analysis_json and isinstance(report2.ai_analysis_json, dict):
            for cat in report2.ai_analysis_json.get("categories", []):
                for it in cat.get("items", cat.get("indicators", [])):
                    if it.get("name") == name:
                        curr_risk = it.get("riskLevel", curr_risk)

        indicators_out.append(CompareIndicatorItem(
            name=name,
            previousValue=prev["value"] if prev else None,
            currentValue=curr["value"] if curr else None,
            unit=(curr or prev or {}).get("unit"),
            change=None,
            direction=direction,
            previousRiskLevel=prev_risk,
            currentRiskLevel=curr_risk,
            suggestion=None,
        ))

    report1_json = report1.ai_analysis_json or {}
    report2_json = report2.ai_analysis_json or {}

    try:
        ai_compare = await analyze_report_compare(report1_json, report2_json, db)
    except Exception:
        ai_compare = {"aiSummary": "AI对比分析暂时不可用", "scoreDiff": None, "indicators": []}

    ai_ind_map = {item.get("name"): item for item in ai_compare.get("indicators", []) if item.get("name")}
    for item in indicators_out:
        ai_item = ai_ind_map.get(item.name)
        if ai_item:
            item.change = ai_item.get("change", item.change)
            item.direction = ai_item.get("direction", item.direction)
            item.suggestion = ai_item.get("suggestion", item.suggestion)

    prev_score = getattr(report1, "health_score", None)
    curr_score = getattr(report2, "health_score", None)
    score_diff_obj = None
    if prev_score is not None or curr_score is not None:
        diff = None
        if prev_score is not None and curr_score is not None:
            diff = curr_score - prev_score
        ai_score_comment = (ai_compare.get("scoreDiff") or {}).get("comment")
        score_diff_obj = CompareScoreDiff(
            previousScore=prev_score,
            currentScore=curr_score,
            diff=diff,
            comment=ai_score_comment,
        )

    return ReportCompareResponse(
        aiSummary=ai_compare.get("aiSummary"),
        scoreDiff=score_diff_obj,
        indicators=indicators_out,
        disclaimer=DISCLAIMER,
    )


# ──────────────── Trend ────────────────


@router.get("/report/trend/{indicator_name}", deprecated=True)
async def get_indicator_trend_deprecated(
    indicator_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[2026-04-23] 趋势分析已下线。"""
    raise HTTPException(status_code=410, detail="趋势分析已下线")


async def _get_indicator_trend_legacy_unused(
    indicator_name: str,
    current_user: User,
    db: AsyncSession,
):
    result = await db.execute(
        select(CheckupIndicator)
        .join(CheckupReport, CheckupIndicator.report_id == CheckupReport.id)
        .where(
            CheckupReport.user_id == current_user.id,
            CheckupIndicator.indicator_name == indicator_name,
        )
        .order_by(CheckupReport.created_at.asc())
    )
    indicators = result.scalars().all()

    report_ids = [ind.report_id for ind in indicators]
    reports_result = await db.execute(
        select(CheckupReport).where(CheckupReport.id.in_(report_ids))
    )
    reports_map = {r.id: r for r in reports_result.scalars().all()}

    data_points = []
    unit = None
    ref_range = None
    for ind in indicators:
        rpt = reports_map.get(ind.report_id)
        if not unit and ind.unit:
            unit = ind.unit
        if not ref_range and ind.reference_range:
            ref_range = ind.reference_range
        data_points.append(TrendDataPoint(
            report_id=ind.report_id,
            report_date=rpt.report_date if rpt else None,
            value=ind.value,
            status=ind.status.value if hasattr(ind.status, "value") else str(ind.status),
            created_at=ind.created_at,
        ))

    return TrendDataResponse(
        indicator_name=indicator_name,
        unit=unit,
        reference_range=ref_range,
        data_points=data_points,
    )


@router.post("/report/trend/analysis", deprecated=True)
async def trend_analysis_deprecated(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[2026-04-23] 趋势分析已下线。"""
    raise HTTPException(status_code=410, detail="趋势分析已下线")


async def _trend_analysis_legacy_unused(
    body,
    current_user: User,
    db: AsyncSession,
):
    result = await db.execute(
        select(CheckupIndicator)
        .join(CheckupReport, CheckupIndicator.report_id == CheckupReport.id)
        .where(
            CheckupReport.user_id == current_user.id,
            CheckupIndicator.indicator_name == body.indicator_name,
        )
        .order_by(CheckupReport.created_at.asc())
    )
    indicators = result.scalars().all()
    if not indicators:
        raise HTTPException(status_code=404, detail="未找到该指标的历史数据")

    report_ids = [ind.report_id for ind in indicators]
    reports_result = await db.execute(
        select(CheckupReport).where(CheckupReport.id.in_(report_ids))
    )
    reports_map = {r.id: r for r in reports_result.scalars().all()}

    trend_data = []
    for ind in indicators:
        rpt = reports_map.get(ind.report_id)
        trend_data.append({
            "date": str(rpt.report_date) if rpt and rpt.report_date else str(ind.created_at.date()),
            "value": ind.value,
            "unit": ind.unit,
            "status": ind.status.value if hasattr(ind.status, "value") else str(ind.status),
        })

    analysis_text = await analyze_trend(body.indicator_name, trend_data, db)
    return TrendAnalysisResponse(
        indicator_name=body.indicator_name,
        analysis=analysis_text,
        disclaimer=DISCLAIMER,
    )


# ──────────────── Alert ────────────────


@router.post("/report/alert/check")
async def check_alerts(
    report_id: int = Body(embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CheckupReport)
        .options(selectinload(CheckupReport.checkup_indicators))
        .where(CheckupReport.id == report_id, CheckupReport.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    new_alerts: list[dict] = []

    for ind in report.checkup_indicators:
        ind_status = ind.status.value if hasattr(ind.status, "value") else str(ind.status)
        if ind_status not in ("abnormal", "critical"):
            continue

        prev_result = await db.execute(
            select(CheckupIndicator)
            .join(CheckupReport, CheckupIndicator.report_id == CheckupReport.id)
            .where(
                CheckupReport.user_id == current_user.id,
                CheckupReport.id != report.id,
                CheckupIndicator.indicator_name == ind.indicator_name,
            )
            .order_by(CheckupReport.created_at.desc())
            .limit(3)
        )
        prev_indicators = prev_result.scalars().all()

        if not prev_indicators:
            alert = ReportAlert(
                user_id=current_user.id,
                report_id=report.id,
                indicator_name=ind.indicator_name,
                alert_type="new_abnormal",
                alert_message=f"指标「{ind.indicator_name}」首次出现异常，当前值: {ind.value} {ind.unit or ''}",
            )
            db.add(alert)
            new_alerts.append({"indicator_name": ind.indicator_name, "alert_type": "new_abnormal"})
            continue

        consecutive_abnormal = all(
            (pi.status.value if hasattr(pi.status, "value") else str(pi.status)) in ("abnormal", "critical")
            for pi in prev_indicators
        )
        if consecutive_abnormal and len(prev_indicators) >= 2:
            alert = ReportAlert(
                user_id=current_user.id,
                report_id=report.id,
                indicator_name=ind.indicator_name,
                alert_type="consecutive_abnormal",
                alert_message=f"指标「{ind.indicator_name}」连续{len(prev_indicators)+1}次异常，请关注",
            )
            db.add(alert)
            new_alerts.append({"indicator_name": ind.indicator_name, "alert_type": "consecutive_abnormal"})

    await db.flush()
    return {"report_id": report_id, "alerts_generated": len(new_alerts), "alerts": new_alerts}


@router.get("/report/alerts", response_model=AlertListResponse)
async def get_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_q = select(ReportAlert).where(ReportAlert.user_id == current_user.id)

    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base_q.order_by(ReportAlert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    alerts = result.scalars().all()

    items = [AlertResponse.model_validate(a) for a in alerts]
    return AlertListResponse(items=items, total=total, page=page, page_size=page_size)


@router.put("/report/alerts/{alert_id}/read")
async def mark_alert_read(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    alert = await db.get(ReportAlert, alert_id)
    if not alert or alert.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="预警不存在")
    alert.is_read = True
    await db.flush()
    return {"id": alert_id, "is_read": True}


# ──────────────── Share ────────────────


@router.post("/report/share", response_model=ShareCreateResponse)
async def create_share(
    report_id: int = Body(embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(CheckupReport, report_id)
    if not report or report.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    token = uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(days=7)

    report.share_token = token
    report.share_expires_at = expires_at
    await db.flush()

    return ShareCreateResponse(
        share_url=f"/api/report/share/{token}",
        share_token=token,
        expires_at=expires_at,
    )


@router.post("/report/{report_id}/share", response_model=ShareCreateResponse)
async def create_share_by_path(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(CheckupReport, report_id)
    if not report or report.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    if report.share_token and report.share_expires_at and report.share_expires_at > datetime.utcnow():
        return ShareCreateResponse(
            share_url=f"/api/report/share/{report.share_token}",
            share_token=report.share_token,
            expires_at=report.share_expires_at,
        )

    token = uuid.uuid4().hex
    expires_at = datetime.utcnow() + timedelta(days=7)

    report.share_token = token
    report.share_expires_at = expires_at
    await db.flush()

    return ShareCreateResponse(
        share_url=f"/api/report/share/{token}",
        share_token=token,
        expires_at=expires_at,
    )


@router.get("/report/share/{token}", response_model=ShareViewResponse)
async def view_share(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CheckupReport)
        .options(selectinload(CheckupReport.checkup_indicators))
        .where(CheckupReport.share_token == token)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="分享链接无效")

    if report.share_expires_at and report.share_expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="分享链接已过期")

    indicators = [
        IndicatorResponse(
            id=ind.id,
            report_id=ind.report_id,
            indicator_name=ind.indicator_name,
            value=ind.value,
            unit=ind.unit,
            reference_range=ind.reference_range,
            status=ind.status.value if hasattr(ind.status, "value") else str(ind.status),
            category=ind.category,
            advice=ind.advice,
            created_at=ind.created_at,
        )
        for ind in report.checkup_indicators
    ]

    return ShareViewResponse(
        report_date=report.report_date,
        report_type=report.report_type,
        ai_analysis=report.ai_analysis,
        ai_analysis_json=report.ai_analysis_json,
        abnormal_count=report.abnormal_count or 0,
        indicators=indicators,
        disclaimer=DISCLAIMER,
    )


# ──────────────── Admin OCR Config ────────────────

admin_router = APIRouter(prefix="/api/admin", tags=["管理后台-OCR配置"])


@admin_router.get("/ocr/config", response_model=OcrConfigResponse)
async def get_ocr_config(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_ocr_config(db)
    if not cfg:
        raise HTTPException(status_code=404, detail="OCR配置不存在")
    return OcrConfigResponse.model_validate(cfg)


@admin_router.put("/ocr/config", response_model=OcrConfigResponse)
async def update_ocr_config(
    body: OcrConfigUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_ocr_config(db)
    if not cfg:
        raise HTTPException(status_code=404, detail="OCR配置不存在")

    if body.enabled is not None:
        cfg.enabled = body.enabled
    if body.api_key is not None:
        cfg.api_key = body.api_key
    if body.secret_key is not None:
        cfg.secret_key_encrypted = body.secret_key
        cfg.access_token = None
        cfg.token_expires_at = None
    if body.ocr_type is not None:
        cfg.ocr_type = body.ocr_type
    await db.flush()

    return OcrConfigResponse.model_validate(cfg)


@admin_router.post("/ocr/test")
async def test_ocr_connection(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_ocr_config(db)
    if not cfg:
        raise HTTPException(status_code=404, detail="OCR配置不存在")
    if not cfg.api_key or not cfg.secret_key_encrypted:
        raise HTTPException(status_code=400, detail="请先配置API Key和Secret Key")

    try:
        token, expires_at = await ensure_access_token(
            cfg.api_key, cfg.secret_key_encrypted,
            cfg.access_token, cfg.token_expires_at,
        )
        cfg.access_token = token
        cfg.token_expires_at = expires_at
        await db.flush()
        return {"success": True, "message": "OCR连接测试成功"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}
