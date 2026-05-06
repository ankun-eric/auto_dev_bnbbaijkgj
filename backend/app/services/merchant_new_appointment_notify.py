"""[PRD-365 商家后台「预约看板」替换升级 v1.0] 新预约通知服务

订单进入「待核销」状态（即客户支付成功后）时，向门店下所有已绑定微信
的商家员工账号即时发送微信模板消息，消息内容与 PRD 2.2.9 规定的模板对齐：

  【新预约提醒】
  门店：{门店名}
  客户：{客户姓名}（{掩码手机号}）
  服务：{服务名称}
  时段：{预约时段}
  订单号：{订单号}
  请尽快做好接待准备。

设计要点：
- 复用现有微信公众号/服务号 access_token 通道（环境变量 WECHAT_MINI_APP_ID / SECRET）
- 收件人 = MerchantStoreMembership 中属于本订单门店、且 wechat_openid 非空的商家用户
- 任意单条推送失败不阻塞主流程；失败日志写入 logger，便于排查
- 不抛异常给主调用方（pay_unified_order / alipay_notify 等），全部 swallow
- 频率控制：每条新预约即时推送一次（不合并）
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    MerchantStore,
    MerchantStoreMembership,
    OrderItem,
    Product,
    UnifiedOrder,
    User,
)

logger = logging.getLogger(__name__)


def _mask_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    s = str(phone)
    if len(s) >= 11:
        return f"{s[:3]}****{s[-4:]}"
    if len(s) >= 7:
        return f"{s[:3]}****{s[-2:]}"
    return s


async def _get_wechat_access_token() -> Optional[str]:
    """获取微信公众号 access_token。

    优先环境变量 WECHAT_MP_APP_ID / WECHAT_MP_APP_SECRET（公众号），
    回退 WECHAT_MINI_APP_ID / WECHAT_MINI_APP_SECRET（小程序）。
    """
    appid = os.getenv("WECHAT_MP_APP_ID") or os.getenv("WECHAT_MINI_APP_ID")
    secret = os.getenv("WECHAT_MP_APP_SECRET") or os.getenv("WECHAT_MINI_APP_SECRET")
    if not appid or not secret:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.weixin.qq.com/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": appid,
                    "secret": secret,
                },
            )
            if r.status_code != 200:
                return None
            tok = r.json().get("access_token", "") if r.headers.get("content-type", "").startswith("application/json") else ""
            return tok or None
    except Exception as e:  # noqa: BLE001
        logger.warning("get wechat access_token failed: %s", e)
        return None


async def _send_template_message(
    *,
    access_token: str,
    openid: str,
    template_id: str,
    data: Dict[str, Any],
    url: str = "",
) -> bool:
    """调用微信公众号模板消息接口。"""
    payload: Dict[str, Any] = {
        "touser": openid,
        "template_id": template_id,
        "data": data,
    }
    if url:
        payload["url"] = url
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}",
                json=payload,
            )
            if r.status_code != 200:
                logger.warning("wechat template send HTTP %s for openid=%s", r.status_code, openid)
                return False
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            errcode = int(body.get("errcode", 0)) if isinstance(body.get("errcode", 0), (int, str)) else 0
            if errcode != 0:
                logger.warning(
                    "wechat template send errcode=%s errmsg=%s for openid=%s",
                    errcode, body.get("errmsg", ""), openid,
                )
                return False
            return True
    except Exception as e:  # noqa: BLE001
        logger.warning("wechat template send exception: %s for openid=%s", e, openid)
        return False


async def notify_merchant_new_appointment(
    db: AsyncSession,
    *,
    order: UnifiedOrder,
) -> Dict[str, Any]:
    """对订单 `order` 触发「新预约提醒」微信模板消息。

    返回结构：
      {
        "ok": bool,                      # 整体是否触发了至少一次推送（可统计）
        "skipped": bool,                 # 是否因为缺配置/收件人为空而完全跳过
        "store_id": int | None,
        "recipients_total": int,
        "recipients_sent": int,
        "recipients_failed": int,
        "detail": str,                   # 文字摘要
      }

    设计：
      - 仅遍历订单的第一个 OrderItem 取 store_id（订单同店，多 item 共用门店）
      - 缺少配置时返回 skipped=True，detail 描述具体原因，**不抛异常**
      - 任何收件人推送失败不阻断其它收件人推送
    """
    result: Dict[str, Any] = {
        "ok": False,
        "skipped": True,
        "store_id": None,
        "recipients_total": 0,
        "recipients_sent": 0,
        "recipients_failed": 0,
        "detail": "",
    }

    try:
        # 1. 解析订单门店
        items_rows = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id).limit(1)
        )
        first_item: Optional[OrderItem] = items_rows.scalars().first()
        if not first_item or not first_item.store_id:
            result["detail"] = "订单缺少 store_id，跳过新预约通知"
            return result
        store_id = int(first_item.store_id)
        result["store_id"] = store_id

        # 2. 解析门店名称
        store_row = await db.execute(select(MerchantStore).where(MerchantStore.id == store_id))
        store: Optional[MerchantStore] = store_row.scalars().first()
        store_name = (store.store_name if store else None) or "未命名门店"

        # 3. 解析商品名 + 客户名 + 客户手机
        prod_row = await db.execute(select(Product).where(Product.id == first_item.product_id))
        product = prod_row.scalars().first()
        product_name = (product.name if product else None) or "服务"

        cust_row = await db.execute(select(User).where(User.id == order.user_id))
        customer = cust_row.scalars().first()
        customer_name = (
            getattr(customer, "nickname", None)
            or getattr(customer, "real_name", None)
            or "顾客"
        )
        customer_phone_raw = getattr(customer, "phone", None) or ""
        customer_phone_mask = _mask_phone(customer_phone_raw)

        # 4. 预约时段文本
        appt_time = getattr(first_item, "appointment_time", None)
        if appt_time is not None:
            try:
                slot_text = appt_time.strftime("%Y-%m-%d %H:%M")
            except Exception:  # noqa: BLE001
                slot_text = str(appt_time)
        else:
            slot_text = "未指定时段"

        order_no = getattr(order, "order_no", "") or ""

        # 5. 找出门店下「已绑定微信」的商家员工
        membership_rows = await db.execute(
            select(MerchantStoreMembership).where(
                MerchantStoreMembership.store_id == store_id,
            )
        )
        memberships = membership_rows.scalars().all()
        if not memberships:
            result["detail"] = f"门店 {store_id} 下无关联员工"
            return result

        user_ids = [int(m.user_id) for m in memberships if m.user_id]
        if not user_ids:
            result["detail"] = f"门店 {store_id} 下无有效员工"
            return result

        emp_rows = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        all_emps: List[User] = list(emp_rows.scalars().all())

        # 微信绑定字段在 User 表中（兼容多种字段命名）
        recipients: List[Dict[str, str]] = []
        for u in all_emps:
            openid = (
                getattr(u, "wechat_openid", None)
                or getattr(u, "wx_openid", None)
                or getattr(u, "mp_openid", None)
                or ""
            )
            if openid:
                recipients.append({"openid": str(openid), "user_id": str(u.id)})

        result["recipients_total"] = len(recipients)
        if not recipients:
            result["detail"] = f"门店 {store_id} 下无已绑定微信的员工"
            return result

        # 6. 取微信模板 ID + access_token
        template_id = (
            os.getenv("WECHAT_NEW_APPOINTMENT_TEMPLATE_ID")
            or os.getenv("WECHAT_RESCHEDULE_TEMPLATE_ID")
            or ""
        )
        if not template_id:
            result["detail"] = "未配置 WECHAT_NEW_APPOINTMENT_TEMPLATE_ID，跳过推送"
            return result

        access_token = await _get_wechat_access_token()
        if not access_token:
            result["detail"] = "未能获取微信 access_token，跳过推送"
            return result

        # 7. 构造模板消息 data（key 名按公众号默认通用占位字段，实际项目应按模板自身配置）
        data = {
            "first":   {"value": "您有一笔新预约", "color": "#1677FF"},
            "keyword1": {"value": store_name},
            "keyword2": {"value": f"{customer_name}（{customer_phone_mask}）"},
            "keyword3": {"value": product_name},
            "keyword4": {"value": slot_text},
            "keyword5": {"value": order_no},
            "remark":   {"value": "请尽快做好接待准备", "color": "#52C41A"},
        }

        # 8. 并行/逐一推送，统计结果
        sent = 0
        failed = 0
        for r in recipients:
            ok = await _send_template_message(
                access_token=access_token,
                openid=r["openid"],
                template_id=template_id,
                data=data,
            )
            if ok:
                sent += 1
            else:
                failed += 1

        result["skipped"] = False
        result["recipients_sent"] = sent
        result["recipients_failed"] = failed
        result["ok"] = sent > 0
        result["detail"] = (
            f"门店 {store_name} 新预约模板消息：成功 {sent}/{len(recipients)}，失败 {failed}"
        )
        return result
    except Exception as e:  # noqa: BLE001
        logger.warning("notify_merchant_new_appointment unexpected error: %s", e)
        result["detail"] = f"内部异常：{e}"
        return result
