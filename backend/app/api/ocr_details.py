import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import CheckupReportDetail, DrugIdentifyDetail
from app.schemas.ocr_details import (
    CheckupReportDetailListResponse,
    CheckupReportDetailResponse,
    CheckupReportStatisticsResponse,
    DrugIdentifyDetailListResponse,
    DrugIdentifyDetailResponse,
    DrugIdentifyStatisticsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["OCR明细管理"])


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
