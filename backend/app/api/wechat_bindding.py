import hashlib
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_identity
from app.models.models import (
    MerchantStore,
    MerchantStoreMembership,
    StaffWechatBinding,
    SystemConfig,
    User,
)
from app.schemas.merchant import WechatBindQrcodeResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["公众号绑定"])

merchant_dep = require_identity("merchant_owner", "merchant_staff")


async def _get_wechat_access_token(db: AsyncSession) -> str:
    keys = ["wechat_push_app_id", "wechat_push_app_secret"]
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(keys))
    )
    cfg = {c.config_key: c.config_value for c in result.scalars().all()}

    app_id = cfg.get("wechat_push_app_id")
    app_secret = cfg.get("wechat_push_app_secret")
    if not app_id or not app_secret:
        raise HTTPException(status_code=400, detail="微信公众号配置不完整")

    from app.services.sms_service import decrypt_secret_key
    try:
        app_secret = decrypt_secret_key(app_secret)
    except Exception:
        pass

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
        )
        data = resp.json()

    if "access_token" not in data:
        logger.error("获取微信 access_token 失败: %s", data)
        raise HTTPException(status_code=500, detail="获取微信 access_token 失败")

    return data["access_token"]


@router.post("/api/merchant/bindding/wechat/qrcode", response_model=WechatBindQrcodeResponse)
async def generate_wechat_bind_qrcode(
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    access_token = await _get_wechat_access_token(db)

    scene_str = f"bind_{current_user.id}_{store_id}"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.weixin.qq.com/cgi-bin/qrcode/create?access_token={access_token}",
            json={
                "expire_seconds": 600,
                "action_name": "QR_STR_SCENE",
                "action_info": {"scene": {"scene_str": scene_str}},
            },
        )
        data = resp.json()

    ticket = data.get("ticket", "")
    if not ticket:
        logger.error("生成带参二维码失败: %s", data)
        raise HTTPException(status_code=500, detail="生成二维码失败")

    qrcode_url = f"https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket={ticket}"
    return WechatBindQrcodeResponse(qrcode_url=qrcode_url, ticket=ticket)


@router.post("/api/webhook/wechat/bindding")
async def wechat_bindding_callback(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return PlainTextResponse("success")

    msg_type = root.findtext("MsgType", "")
    event = root.findtext("Event", "")
    openid = root.findtext("FromUserName", "")

    if msg_type == "event" and event in ("subscribe", "SCAN"):
        event_key = root.findtext("EventKey", "")
        if event == "subscribe" and event_key.startswith("qrscene_"):
            event_key = event_key[len("qrscene_"):]

        if event_key.startswith("bind_"):
            parts = event_key.split("_")
            if len(parts) >= 3:
                staff_id = int(parts[1])
                store_id = int(parts[2])

                existing = await db.execute(
                    select(StaffWechatBinding).where(
                        StaffWechatBinding.staff_id == staff_id,
                        StaffWechatBinding.store_id == store_id,
                        StaffWechatBinding.is_active == True,
                    )
                )
                if existing.scalar_one_or_none():
                    return PlainTextResponse("success")

                binding = StaffWechatBinding(
                    staff_id=staff_id,
                    store_id=store_id,
                    openid=openid,
                )
                db.add(binding)
                await db.commit()
                logger.info("微信绑定成功: staff_id=%d, store_id=%d, openid=%s", staff_id, store_id, openid)

    return PlainTextResponse("success")


@router.delete("/api/merchant/bindding/wechat")
async def unbind_wechat(
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StaffWechatBinding).where(
            StaffWechatBinding.staff_id == current_user.id,
            StaffWechatBinding.store_id == store_id,
            StaffWechatBinding.is_active == True,
        )
    )
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="未找到绑定记录")

    binding.is_active = False
    await db.flush()
    return {"message": "已解绑"}


@router.get("/api/merchant/bindding/wechat/status")
async def get_wechat_bind_status(
    store_id: int = Query(...),
    current_user: User = Depends(merchant_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StaffWechatBinding).where(
            StaffWechatBinding.staff_id == current_user.id,
            StaffWechatBinding.store_id == store_id,
            StaffWechatBinding.is_active == True,
        )
    )
    binding = result.scalar_one_or_none()
    return {
        "is_bound": binding is not None,
        "openid": binding.openid if binding else None,
        "bound_at": binding.bound_at.isoformat() if binding and binding.bound_at else None,
    }
