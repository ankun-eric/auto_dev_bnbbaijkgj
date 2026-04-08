import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    AllergyRecord,
    ChatMessage,
    CheckupReportDetail,
    DrugIdentifyDetail,
    HealthProfile,
    MedicalHistory,
    MedicationRecord,
    PromptTemplate,
)
from app.schemas.ocr_details import (
    CheckupReportDetailListResponse,
    CheckupReportDetailResponse,
    CheckupReportStatisticsResponse,
    ConversationMessageItem,
    ConversationResponse,
    DrugIdentifyDetailListResponse,
    DrugIdentifyDetailResponse,
    DrugIdentifyHistoryItem,
    DrugIdentifyHistoryResponse,
    DrugIdentifyStatisticsResponse,
)
from app.services.ai_service import call_ai_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["OCR明细管理"])
user_router = APIRouter(prefix="/api/drug-identify", tags=["拍照识药"])


def _mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-4:]


# ──────────────── 体检报告明细 ────────────────


@router.get("/checkup-details/statistics", response_model=CheckupReportStatisticsResponse)
async def checkup_statistics(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    total_result = await db.execute(select(func.count(CheckupReportDetail.id)))
    total = total_result.scalar() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(CheckupReportDetail.id)).where(
            CheckupReportDetail.created_at >= today_start
        )
    )
    today_count = today_result.scalar() or 0

    abnormal_result = await db.execute(
        select(func.count(CheckupReportDetail.id)).where(
            CheckupReportDetail.status == "abnormal"
        )
    )
    abnormal_count = abnormal_result.scalar() or 0

    month_start = today_start.replace(day=1)
    month_result = await db.execute(
        select(func.count(CheckupReportDetail.id)).where(
            CheckupReportDetail.created_at >= month_start
        )
    )
    month_count = month_result.scalar() or 0

    return CheckupReportStatisticsResponse(
        total=total,
        today_count=today_count,
        abnormal_count=abnormal_count,
        month_count=month_count,
    )


@router.get("/checkup-details", response_model=CheckupReportDetailListResponse)
async def list_checkup_details(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    report_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    query = select(CheckupReportDetail)
    count_query = select(func.count(CheckupReportDetail.id))

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.where(CheckupReportDetail.created_at >= sd)
            count_query = count_query.where(CheckupReportDetail.created_at >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.where(CheckupReportDetail.created_at < ed)
            count_query = count_query.where(CheckupReportDetail.created_at < ed)
        except ValueError:
            pass
    if keyword:
        kw = f"%{keyword}%"
        condition = (
            CheckupReportDetail.user_phone.like(kw)
            | CheckupReportDetail.user_nickname.like(kw)
        )
        query = query.where(condition)
        count_query = count_query.where(condition)
    if report_type:
        query = query.where(CheckupReportDetail.report_type == report_type)
        count_query = count_query.where(CheckupReportDetail.report_type == report_type)
    if status:
        query = query.where(CheckupReportDetail.status == status)
        count_query = count_query.where(CheckupReportDetail.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(CheckupReportDetail.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)

    items = []
    for row in result.scalars().all():
        item = CheckupReportDetailResponse.model_validate(row)
        item.user_phone = _mask_phone(row.user_phone)
        items.append(item)

    return CheckupReportDetailListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/checkup-details/{detail_id}", response_model=CheckupReportDetailResponse)
async def get_checkup_detail(
    detail_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(CheckupReportDetail).where(CheckupReportDetail.id == detail_id)
    )
    detail = result.scalar_one_or_none()
    if not detail:
        raise HTTPException(status_code=404, detail="记录不存在")
    return CheckupReportDetailResponse.model_validate(detail)


# ──────────────── 拍照识药明细 ────────────────


@router.get("/drug-details/statistics", response_model=DrugIdentifyStatisticsResponse)
async def drug_statistics(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    total_result = await db.execute(select(func.count(DrugIdentifyDetail.id)))
    total = total_result.scalar() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(DrugIdentifyDetail.id)).where(
            DrugIdentifyDetail.created_at >= today_start
        )
    )
    today_count = today_result.scalar() or 0

    types_result = await db.execute(
        select(func.count(func.distinct(DrugIdentifyDetail.drug_name))).where(
            DrugIdentifyDetail.drug_name.isnot(None)
        )
    )
    drug_types_count = types_result.scalar() or 0

    month_start = today_start.replace(day=1)
    month_result = await db.execute(
        select(func.count(DrugIdentifyDetail.id)).where(
            DrugIdentifyDetail.created_at >= month_start
        )
    )
    month_count = month_result.scalar() or 0

    return DrugIdentifyStatisticsResponse(
        total=total,
        today_count=today_count,
        drug_types_count=drug_types_count,
        month_count=month_count,
    )


@router.get("/drug-details", response_model=DrugIdentifyDetailListResponse)
async def list_drug_details(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    drug_name: Optional[str] = None,
    drug_category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    query = select(DrugIdentifyDetail)
    count_query = select(func.count(DrugIdentifyDetail.id))

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.where(DrugIdentifyDetail.created_at >= sd)
            count_query = count_query.where(DrugIdentifyDetail.created_at >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.where(DrugIdentifyDetail.created_at < ed)
            count_query = count_query.where(DrugIdentifyDetail.created_at < ed)
        except ValueError:
            pass
    if keyword:
        kw = f"%{keyword}%"
        condition = (
            DrugIdentifyDetail.user_phone.like(kw)
            | DrugIdentifyDetail.user_nickname.like(kw)
        )
        query = query.where(condition)
        count_query = count_query.where(condition)
    if drug_name:
        query = query.where(DrugIdentifyDetail.drug_name.like(f"%{drug_name}%"))
        count_query = count_query.where(DrugIdentifyDetail.drug_name.like(f"%{drug_name}%"))
    if drug_category:
        query = query.where(DrugIdentifyDetail.drug_category == drug_category)
        count_query = count_query.where(DrugIdentifyDetail.drug_category == drug_category)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(DrugIdentifyDetail.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)

    items = []
    for row in result.scalars().all():
        item = DrugIdentifyDetailResponse.model_validate(row)
        item.user_phone = _mask_phone(row.user_phone)
        items.append(item)

    return DrugIdentifyDetailListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/drug-details/{detail_id}", response_model=DrugIdentifyDetailResponse)
async def get_drug_detail(
    detail_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(DrugIdentifyDetail).where(DrugIdentifyDetail.id == detail_id)
    )
    detail = result.scalar_one_or_none()
    if not detail:
        raise HTTPException(status_code=404, detail="记录不存在")
    return DrugIdentifyDetailResponse.model_validate(detail)


@router.get("/drug-details/{detail_id}/conversation", response_model=ConversationResponse)
async def get_drug_detail_conversation(
    detail_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(DrugIdentifyDetail).where(DrugIdentifyDetail.id == detail_id)
    )
    detail = result.scalar_one_or_none()
    if not detail:
        raise HTTPException(status_code=404, detail="记录不存在")

    if not detail.session_id:
        return ConversationResponse(messages=[])

    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == detail.session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = [
        ConversationMessageItem(
            role=msg.role.value if hasattr(msg.role, "value") else str(msg.role),
            content=msg.content,
            image_urls=msg.image_urls,
            created_at=msg.created_at,
        )
        for msg in msg_result.scalars().all()
    ]
    return ConversationResponse(messages=messages)


# ──────────────── 用户端：识别历史 ────────────────


@user_router.get("/history", response_model=DrugIdentifyHistoryResponse)
async def drug_identify_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    count_query = select(func.count(DrugIdentifyDetail.id)).where(
        DrugIdentifyDetail.user_id == current_user.id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = (
        select(DrugIdentifyDetail)
        .where(DrugIdentifyDetail.user_id == current_user.id)
        .order_by(DrugIdentifyDetail.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)

    items = [
        DrugIdentifyHistoryItem(
            id=row.id,
            image_url=row.original_image_url,
            drug_name=row.drug_name,
            status=row.status,
            created_at=row.created_at,
            session_id=row.session_id,
        )
        for row in result.scalars().all()
    ]

    return DrugIdentifyHistoryResponse(items=items, total=total)


# ──────────────── 个性化药物建议 ────────────────


class PersonalSuggestionResponse(BaseModel):
    record_id: int
    ai_result: Any
    has_health_profile: bool


@user_router.get("/{record_id}/personal-suggestion", response_model=PersonalSuggestionResponse)
async def get_personal_drug_suggestion(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    record_result = await db.execute(
        select(DrugIdentifyDetail).where(
            DrugIdentifyDetail.id == record_id,
            DrugIdentifyDetail.user_id == current_user.id,
        )
    )
    record = record_result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    hp_result = await db.execute(
        select(HealthProfile).where(HealthProfile.user_id == current_user.id)
    )
    hp = hp_result.scalar_one_or_none()

    allergy_result = await db.execute(
        select(AllergyRecord).where(AllergyRecord.user_id == current_user.id)
    )
    allergies = allergy_result.scalars().all()

    history_result = await db.execute(
        select(MedicalHistory).where(MedicalHistory.user_id == current_user.id)
    )
    histories = history_result.scalars().all()

    med_result = await db.execute(
        select(MedicationRecord).where(
            MedicationRecord.user_id == current_user.id,
            MedicationRecord.status == "active",
        )
    )
    medications = med_result.scalars().all()

    profile_parts = []
    has_health_profile = False
    if hp:
        has_health_profile = True
        if hp.gender:
            profile_parts.append(f"性别: {hp.gender}")
        if hp.birthday:
            profile_parts.append(f"生日: {hp.birthday}")
        if hp.height:
            profile_parts.append(f"身高: {hp.height}cm")
        if hp.weight:
            profile_parts.append(f"体重: {hp.weight}kg")
        if hp.blood_type:
            profile_parts.append(f"血型: {hp.blood_type}")
        if hp.smoking:
            profile_parts.append(f"吸烟: {hp.smoking}")
        if hp.drinking:
            profile_parts.append(f"饮酒: {hp.drinking}")

    if allergies:
        has_health_profile = True
        allergy_str = ", ".join(f"{a.allergy_name}({a.allergy_type})" for a in allergies)
        profile_parts.append(f"过敏史: {allergy_str}")

    if histories:
        has_health_profile = True
        history_str = ", ".join(h.disease_name for h in histories)
        profile_parts.append(f"既往病史: {history_str}")

    if medications:
        has_health_profile = True
        med_str = ", ".join(m.medicine_name for m in medications)
        profile_parts.append(f"当前用药: {med_str}")

    health_profile_text = "\n".join(profile_parts) if profile_parts else "用户未填写健康档案"

    tpl_result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.prompt_type == "drug_personal",
            PromptTemplate.is_active == True,  # noqa: E712
        )
    )
    tpl = tpl_result.scalar_one_or_none()

    if tpl:
        system_prompt = tpl.content.replace("{health_profile}", health_profile_text)
    else:
        system_prompt = (
            f"你是一位专业药剂师AI，请根据提供的药物信息及用户健康档案，给出个性化用药建议。\n"
            f"用户健康档案信息：\n{health_profile_text}\n"
            "请严格按照JSON格式输出，不要输出其他内容。"
        )

    ocr_text = record.ocr_raw_text or ""
    ai_result_existing = record.ai_structured_result
    if ai_result_existing:
        user_content = f"以下是已识别的药物信息（JSON格式）:\n{json.dumps(ai_result_existing, ensure_ascii=False)}"
    else:
        user_content = f"以下是OCR识别的文字内容:\n{ocr_text}"

    messages = [{"role": "user", "content": user_content}]

    try:
        raw = await call_ai_model(messages, system_prompt, db)
        if isinstance(raw, dict):
            ai_result = raw
        else:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            try:
                ai_result = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                ai_result = {"raw_result": raw}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI调用失败: {str(e)}")

    return PersonalSuggestionResponse(
        record_id=record_id,
        ai_result=ai_result,
        has_health_profile=has_health_profile,
    )
