import json
import random
import string
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import SmsConfig, SmsLog, SmsTemplate
from app.schemas.sms import (
    AliyunConfigResponse,
    SmsConfigCreate,
    SmsConfigResponse,
    SmsConfigUpdate,
    SmsLogResponse,
    SmsMultiConfigResponse,
    SmsProviderConfigUpdate,
    SmsTemplateCreate,
    SmsTemplateResponse,
    SmsTemplateUpdate,
    SmsTestRequest,
    SmsTestResponse,
    TencentConfigResponse,
)
from app.services.sms_service import encrypt_secret_key, send_sms

router = APIRouter(prefix="/api/admin/sms", tags=["短信管理"])

admin_dep = require_role("admin")


def _mask_phone(phone: str) -> str:
    if phone and len(phone) >= 7:
        return phone[:3] + "****" + phone[7:]
    return phone


def _build_tencent_response(config: Optional[SmsConfig]) -> TencentConfigResponse:
    if not config:
        return TencentConfigResponse()
    return TencentConfigResponse(
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


def _build_aliyun_response(config: Optional[SmsConfig]) -> AliyunConfigResponse:
    if not config:
        return AliyunConfigResponse()
    return AliyunConfigResponse(
        id=config.id,
        access_key_id=config.access_key_id,
        sign_name=config.sign_name,
        template_id=config.template_id,
        is_active=config.is_active,
        has_access_key_secret=bool(config.access_key_secret_encrypted),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


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


@router.get("/config", response_model=SmsMultiConfigResponse)
async def get_sms_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SmsConfig).where(SmsConfig.provider == "tencent").limit(1)
    )
    tencent_config = result.scalar_one_or_none()

    result = await db.execute(
        select(SmsConfig).where(SmsConfig.provider == "aliyun").limit(1)
    )
    aliyun_config = result.scalar_one_or_none()

    return SmsMultiConfigResponse(
        tencent=_build_tencent_response(tencent_config),
        aliyun=_build_aliyun_response(aliyun_config),
    )


@router.put("/config")
async def update_sms_config(
    data: SmsProviderConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    provider = data.provider
    if provider not in ("tencent", "aliyun"):
        raise HTTPException(status_code=400, detail="provider 必须为 tencent 或 aliyun")

    result = await db.execute(
        select(SmsConfig).where(SmsConfig.provider == provider).limit(1)
    )
    config = result.scalar_one_or_none()

    if not config:
        config = SmsConfig(provider=provider, is_active=False)
        db.add(config)
        await db.flush()

    if provider == "tencent":
        if data.secret_id is not None:
            config.secret_id = data.secret_id
        if data.secret_key is not None:
            config.secret_key_encrypted = encrypt_secret_key(data.secret_key)
        if data.sdk_app_id is not None:
            config.sdk_app_id = data.sdk_app_id
        if data.app_key is not None:
            config.app_key = data.app_key
    elif provider == "aliyun":
        if data.access_key_id is not None:
            config.access_key_id = data.access_key_id
        if data.access_key_secret is not None:
            config.access_key_secret_encrypted = encrypt_secret_key(data.access_key_secret)

    if data.sign_name is not None:
        config.sign_name = data.sign_name
    if data.template_id is not None:
        config.template_id = data.template_id

    if data.is_active is not None:
        config.is_active = data.is_active
        if data.is_active:
            other_provider = "aliyun" if provider == "tencent" else "tencent"
            result2 = await db.execute(
                select(SmsConfig).where(SmsConfig.provider == other_provider).limit(1)
            )
            other_config = result2.scalar_one_or_none()
            if other_config:
                other_config.is_active = False

    config.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(config)

    if provider == "tencent":
        return _build_tencent_response(config)
    return _build_aliyun_response(config)


# ──────── Templates CRUD ────────

@router.get("/templates")
async def get_sms_templates(
    provider: Optional[str] = None,
    scene: Optional[str] = None,
    name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(SmsTemplate)
    count_query = select(func.count(SmsTemplate.id))

    if provider:
        query = query.where(SmsTemplate.provider == provider)
        count_query = count_query.where(SmsTemplate.provider == provider)
    if scene:
        query = query.where(SmsTemplate.scene == scene)
        count_query = count_query.where(SmsTemplate.scene == scene)
    if name:
        query = query.where(SmsTemplate.name.contains(name))
        count_query = count_query.where(SmsTemplate.name.contains(name))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(SmsTemplate.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [SmsTemplateResponse.model_validate(t) for t in result.scalars().all()]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/templates", response_model=SmsTemplateResponse)
async def create_sms_template(
    data: SmsTemplateCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    variables_str = json.dumps(data.variables, ensure_ascii=False) if data.variables is not None else None
    tpl = SmsTemplate(
        name=data.name,
        provider=data.provider,
        template_id=data.template_id,
        content=data.content,
        sign_name=data.sign_name,
        scene=data.scene,
        variables=variables_str,
        status=data.status if data.status is not None else True,
    )
    db.add(tpl)
    await db.flush()
    await db.refresh(tpl)
    return SmsTemplateResponse.model_validate(tpl)


@router.put("/templates/{template_id}", response_model=SmsTemplateResponse)
async def update_sms_template(
    template_id: int,
    data: SmsTemplateUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SmsTemplate).where(SmsTemplate.id == template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")

    for field in ("name", "provider", "template_id", "content", "sign_name", "scene", "status"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(tpl, field, val)
    if data.variables is not None:
        tpl.variables = json.dumps(data.variables, ensure_ascii=False)

    tpl.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(tpl)
    return SmsTemplateResponse.model_validate(tpl)


@router.delete("/templates/{template_id}")
async def delete_sms_template(
    template_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SmsTemplate).where(SmsTemplate.id == template_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    await db.delete(tpl)
    return {"message": "模板已删除"}


# ──────── Logs ────────

@router.get("/logs")
async def get_sms_logs(
    phone: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
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
    if provider:
        query = query.where(SmsLog.provider == provider)
        count_query = count_query.where(SmsLog.provider == provider)

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


# ──────── Test ────────

@router.post("/test", response_model=SmsTestResponse)
async def test_sms(
    data: SmsTestRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    code = "".join(random.choices(string.digits, k=6))

    if data.template_params:
        params_used = data.template_params
    else:
        params_used = [code]

    preview_content: Optional[str] = None
    result = await db.execute(
        select(SmsTemplate).where(SmsTemplate.template_id == data.template_id).limit(1)
    )
    tpl = result.scalar_one_or_none()
    if tpl and tpl.content:
        preview_content = tpl.content
        for i, val in enumerate(params_used):
            preview_content = preview_content.replace(f"{{{i + 1}}}", val)

    try:
        await send_sms(
            data.phone, code,
            is_test=True,
            operator_id=current_user.id,
            provider=data.provider,
            db=db,
            template_params=data.template_params,
            template_id=data.template_id,
        )
        return SmsTestResponse(
            success=True,
            message="测试短信发送成功",
            params_used=params_used,
            preview_content=preview_content,
        )
    except RuntimeError as exc:
        return SmsTestResponse(
            success=False,
            message=str(exc),
            params_used=params_used,
            preview_content=preview_content,
        )
