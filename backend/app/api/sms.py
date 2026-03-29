import random
import string
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import SmsConfig, SmsLog
from app.schemas.sms import (
    SmsConfigCreate,
    SmsConfigResponse,
    SmsConfigUpdate,
    SmsLogResponse,
    SmsTestRequest,
)
from app.services.sms_service import encrypt_secret_key, send_sms

router = APIRouter(prefix="/api/admin/sms", tags=["短信管理"])

admin_dep = require_role("admin")


def _mask_phone(phone: str) -> str:
    if phone and len(phone) >= 7:
        return phone[:3] + "****" + phone[7:]
    return phone


def _build_config_response(config: SmsConfig) -> SmsConfigResponse:
    return SmsConfigResponse(
        id=config.id,
        secret_id=config.secret_id,
        sdk_app_id=config.sdk_app_id,
        sign_name=config.sign_name,
        template_id=config.template_id,
        app_key=config.app_key,
        is_active=config.is_active,
        has_secret_key=bool(config.secret_key_encrypted),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("/config", response_model=SmsConfigResponse)
async def get_sms_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SmsConfig).where(SmsConfig.is_active == True).limit(1)  # noqa: E712
    )
    config = result.scalar_one_or_none()
    if not config:
        result = await db.execute(
            select(SmsConfig).order_by(SmsConfig.created_at.desc()).limit(1)
        )
        config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="暂无短信配置")
    return _build_config_response(config)


@router.put("/config", response_model=SmsConfigResponse)
async def update_sms_config(
    data: SmsConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SmsConfig).where(SmsConfig.is_active == True).limit(1)  # noqa: E712
    )
    config = result.scalar_one_or_none()

    if not config:
        result = await db.execute(
            select(SmsConfig).order_by(SmsConfig.created_at.desc()).limit(1)
        )
        config = result.scalar_one_or_none()

    if not config:
        config = SmsConfig(is_active=True)
        db.add(config)
        await db.flush()

    if data.secret_id is not None:
        config.secret_id = data.secret_id
    if data.secret_key is not None:
        config.secret_key_encrypted = encrypt_secret_key(data.secret_key)
    if data.sdk_app_id is not None:
        config.sdk_app_id = data.sdk_app_id
    if data.sign_name is not None:
        config.sign_name = data.sign_name
    if data.template_id is not None:
        config.template_id = data.template_id
    if data.app_key is not None:
        config.app_key = data.app_key

    config.is_active = True
    config.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(config)
    return _build_config_response(config)


@router.get("/logs")
async def get_sms_logs(
    phone: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(SmsLog)
    count_query = select(func.count(SmsLog.id))

    if phone:
        query = query.where(SmsLog.phone.contains(phone))
        count_query = count_query.where(SmsLog.phone.contains(phone))
    if status:
        query = query.where(SmsLog.status == status)
        count_query = count_query.where(SmsLog.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(SmsLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for log in result.scalars().all():
        resp = SmsLogResponse.model_validate(log)
        resp.phone = _mask_phone(resp.phone)
        items.append(resp)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/test")
async def test_sms(
    data: SmsTestRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    code = "".join(random.choices(string.digits, k=6))
    try:
        await send_sms(
            data.phone, code,
            is_test=True,
            operator_id=current_user.id,
            db=db,
        )
        return {"success": True, "message": "测试短信发送成功"}
    except RuntimeError as exc:
        return {"success": False, "message": str(exc)}
