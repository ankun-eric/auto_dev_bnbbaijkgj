import logging
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    MerchantNotification,
    MerchantStoreMembership,
    StaffWechatBinding,
    SystemConfig,
    User,
)

logger = logging.getLogger(__name__)


async def _get_wechat_config(db: AsyncSession) -> dict:
    keys = [
        "wechat_push_enable",
        "wechat_push_app_id",
        "wechat_push_app_secret",
        "wechat_push_order_notify_template",
    ]
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(keys))
    )
    return {c.config_key: c.config_value for c in result.scalars().all()}


async def _get_access_token(app_id: str, app_secret: str) -> Optional[str]:
    from app.services.sms_service import decrypt_secret_key
    try:
        app_secret = decrypt_secret_key(app_secret)
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.weixin.qq.com/cgi-bin/token",
                params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
            )
            data = resp.json()
            return data.get("access_token")
    except Exception as e:
        logger.error("获取 access_token 失败: %s", e)
        return None


async def send_wechat_template_message(
    db: AsyncSession,
    openid: str,
    template_id: str,
    data: dict,
    url: str = "",
) -> bool:
    cfg = await _get_wechat_config(db)
    app_id = cfg.get("wechat_push_app_id")
    app_secret = cfg.get("wechat_push_app_secret")
    if not app_id or not app_secret:
        logger.warning("微信推送配置不完整，跳过")
        return False

    access_token = await _get_access_token(app_id, app_secret)
    if not access_token:
        return False

    payload = {
        "touser": openid,
        "template_id": template_id,
        "data": data,
    }
    if url:
        payload["url"] = url

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}",
                json=payload,
            )
            result = resp.json()
            if result.get("errcode", 0) != 0:
                logger.error("微信模板消息发送失败: %s", result)
                return False
            return True
    except Exception as e:
        logger.error("微信模板消息发送异常: %s", e)
        return False


async def notify_store_staff_new_order(
    db: AsyncSession,
    store_id: int,
    order_no: str,
    order_amount: float,
    product_name: str = "",
):
    cfg = await _get_wechat_config(db)
    if cfg.get("wechat_push_enable", "").lower() != "true":
        return

    template_id = cfg.get("wechat_push_order_notify_template")
    if not template_id:
        return

    result = await db.execute(
        select(StaffWechatBinding).where(
            StaffWechatBinding.store_id == store_id,
            StaffWechatBinding.is_active == True,
        )
    )
    bindings = result.scalars().all()

    for binding in bindings:
        template_data = {
            "first": {"value": "您有新的预约订单"},
            "keyword1": {"value": order_no},
            "keyword2": {"value": product_name or "服务订单"},
            "keyword3": {"value": f"¥{order_amount:.2f}"},
            "remark": {"value": "请尽快确认接单"},
        }
        await send_wechat_template_message(db, binding.openid, template_id, template_data)


async def create_merchant_notification(
    db: AsyncSession,
    store_id: int,
    title: str,
    content: str,
    notification_type: str = "order",
):
    result = await db.execute(
        select(MerchantStoreMembership.user_id).where(
            MerchantStoreMembership.store_id == store_id,
            MerchantStoreMembership.status == "active",
        )
    )
    user_ids = [row[0] for row in result.all()]

    for user_id in user_ids:
        db.add(MerchantNotification(
            user_id=user_id,
            store_id=store_id,
            title=title,
            content=content,
            notification_type=notification_type,
        ))
