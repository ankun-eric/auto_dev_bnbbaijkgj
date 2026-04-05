from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import SystemConfig
from app.schemas.wechat_push import WechatPushConfigResponse, WechatPushConfigUpdate
from app.services.sms_service import encrypt_secret_key

router = APIRouter(prefix="/api/admin/wechat-push", tags=["微信推送管理"])

admin_dep = require_role("admin")

_KEYS = [
    "wechat_push_enable",
    "wechat_push_app_id",
    "wechat_push_app_secret",
    "wechat_push_order_notify_template",
    "wechat_push_service_notify_template",
]


async def _get_config_map(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(_KEYS))
    )
    return {c.config_key: c.config_value for c in result.scalars().all()}


async def _set_config(db: AsyncSession, key: str, value: str, config_type: str = "wechat_push"):
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    config = result.scalar_one_or_none()
    if config:
        config.config_value = value
        config.updated_at = datetime.utcnow()
    else:
        db.add(SystemConfig(config_key=key, config_value=value, config_type=config_type, description=key))


@router.get("/config", response_model=WechatPushConfigResponse)
async def get_wechat_push_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    m = await _get_config_map(db)
    return WechatPushConfigResponse(
        enable_wechat_push=m.get("wechat_push_enable", "").lower() == "true",
        wechat_app_id=m.get("wechat_push_app_id"),
        has_wechat_app_secret=bool(m.get("wechat_push_app_secret")),
        order_notify_template=m.get("wechat_push_order_notify_template"),
        service_notify_template=m.get("wechat_push_service_notify_template"),
    )


@router.put("/config", response_model=WechatPushConfigResponse)
async def update_wechat_push_config(
    data: WechatPushConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if data.enable_wechat_push is not None:
        await _set_config(db, "wechat_push_enable", str(data.enable_wechat_push))
    if data.wechat_app_id is not None:
        await _set_config(db, "wechat_push_app_id", data.wechat_app_id)
    if data.wechat_app_secret is not None:
        encrypted = encrypt_secret_key(data.wechat_app_secret)
        await _set_config(db, "wechat_push_app_secret", encrypted)
    if data.order_notify_template is not None:
        await _set_config(db, "wechat_push_order_notify_template", data.order_notify_template)
    if data.service_notify_template is not None:
        await _set_config(db, "wechat_push_service_notify_template", data.service_notify_template)

    m = await _get_config_map(db)
    return WechatPushConfigResponse(
        enable_wechat_push=m.get("wechat_push_enable", "").lower() == "true",
        wechat_app_id=m.get("wechat_push_app_id"),
        has_wechat_app_secret=bool(m.get("wechat_push_app_secret")),
        order_notify_template=m.get("wechat_push_order_notify_template"),
        service_notify_template=m.get("wechat_push_service_notify_template"),
    )
