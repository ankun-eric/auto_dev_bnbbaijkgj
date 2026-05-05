"""[PRD-04 改期通知三通道 v1.0] 改期通知三通道并行下发 + 企业微信告警。

设计目标
========
1. 客户端改期成功后，**并行下发三个通道**的通知：
   - 微信小程序订阅消息（subscribe_message.send）
   - APP push（封装为通用 push 接口，凭证从配置中心读）
   - 短信（复用 app.services.sms_service）
2. **任一通道失败不阻塞其他通道**（asyncio.gather + return_exceptions=True）
3. **凭证全部从配置中心读取**（环境变量或 NotificationConfig 表），不写死代码
4. **三通道全部失败**时：
   - 写入 Notification 表的 extra_data.notify_status="all_failed"
   - **触发企业微信群机器人 webhook 告警**（PRD-04 §F-04-6 / §2.8）
5. **单元测试友好**：所有外部 IO 都通过 `_send_*` 私有方法封装，方便 monkeypatch

通知文案模板（三通道统一）
==========================
【XX 健康】您预约的「{服务项目名}」已改期：原 {原时段}，现 {新时段}，门店：{门店名}。
如有疑问请联系门店：{门店电话}。

接入方式
========
在 unified_orders.set_order_appointment 改期路径中：

    from app.services.reschedule_notification import notify_order_rescheduled
    await notify_order_rescheduled(
        db,
        order=order,
        old_appointment_time=prev_appt_time,
        new_appointment_time=data.appointment_time,
    )
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ─────────── 时段格式化 ───────────


def _format_slot_text(dt: Optional[datetime]) -> str:
    """格式化预约时段：'05月06日 10:00-12:00'。

    使用「门店预约看板」的固定 9 段切片（每段 2 小时，从 06:00 起）来定位时段。
    凌晨脏数据时返回精确时间。
    """
    if dt is None:
        return "未指定"
    try:
        h = dt.hour
        if 6 <= h < 24:
            seg_start = (h // 2) * 2
            if seg_start < 6:
                seg_start = 6
            seg_end = seg_start + 2
            return f"{dt.month:02d}月{dt.day:02d}日 {seg_start:02d}:00-{seg_end:02d}:00"
        return dt.strftime("%m月%d日 %H:%M")
    except Exception:  # noqa: BLE001
        return str(dt)


def build_reschedule_message(
    *,
    product_name: str,
    old_appointment_time: Optional[datetime],
    new_appointment_time: Optional[datetime],
    store_name: str = "",
    store_phone: str = "",
    brand: str = "",
) -> str:
    """构造统一文案。"""
    brand_part = f"【{brand}】" if brand else ""
    old_text = _format_slot_text(old_appointment_time)
    new_text = _format_slot_text(new_appointment_time)
    store_part = f"，门店：{store_name}" if store_name else ""
    phone_part = f"如有疑问请联系门店：{store_phone}。" if store_phone else ""
    return (
        f"{brand_part}您预约的「{product_name}」已改期：原 {old_text}，"
        f"现 {new_text}{store_part}。{phone_part}".strip()
    )


# ─────────── 三通道下发器 ───────────


@dataclass
class ChannelResult:
    """单通道下发结果。"""

    name: str
    ok: bool
    detail: str = ""


@dataclass
class RescheduleNotifyResult:
    """整体下发结果。"""

    channels: list[ChannelResult] = field(default_factory=list)

    @property
    def any_ok(self) -> bool:
        return any(c.ok for c in self.channels)

    @property
    def all_failed(self) -> bool:
        return bool(self.channels) and all(not c.ok for c in self.channels)

    def to_dict(self) -> dict:
        d: dict = {
            "channels": [
                {"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.channels
            ],
            "any_ok": self.any_ok,
            "all_failed": self.all_failed,
        }
        # PRD-04 §F-04-6：三通道全失败时，挂载企业微信告警结果（其他场景不挂载）
        alert = getattr(self, "alert", None)
        if alert is not None:
            try:
                d["wechat_work_alert"] = {
                    "ok": bool(getattr(alert, "ok", False)),
                    "detail": str(getattr(alert, "detail", "")),
                }
            except Exception:  # noqa: BLE001
                pass
        return d


# ── 通道一：微信小程序订阅消息 ──


async def _send_wechat_subscribe(
    *,
    openid: Optional[str],
    template_id: Optional[str],
    data: dict,
) -> ChannelResult:
    """微信小程序「订阅消息」通道。

    凭证读取顺序：
      1) 显式传入参数
      2) 环境变量 WECHAT_RESCHEDULE_TEMPLATE_ID / WECHAT_MINI_APP_ID / WECHAT_MINI_APP_SECRET
    缺失任一凭证或 openid 时返回 ok=False, detail=配置缺失提示。
    """
    name = "wechat_subscribe"
    try:
        if not openid:
            return ChannelResult(name=name, ok=False, detail="用户未授权小程序，跳过")

        tpl = template_id or os.getenv("WECHAT_RESCHEDULE_TEMPLATE_ID", "")
        app_id = os.getenv("WECHAT_MINI_APP_ID", "")
        app_secret = os.getenv("WECHAT_MINI_APP_SECRET", "")
        if not tpl or not app_id or not app_secret:
            return ChannelResult(
                name=name,
                ok=False,
                detail="小程序订阅消息凭证未配置（WECHAT_MINI_APP_ID/SECRET/TEMPLATE）",
            )

        try:
            import httpx
        except ImportError:
            return ChannelResult(name=name, ok=False, detail="httpx 未安装")

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://api.weixin.qq.com/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": app_id,
                    "secret": app_secret,
                },
            )
            tok = r.json().get("access_token", "") if r.status_code == 200 else ""
            if not tok:
                return ChannelResult(name=name, ok=False, detail="微信 access_token 获取失败")

            payload = {
                "touser": openid,
                "template_id": tpl,
                "page": "pages/orders/index",
                "data": data,
                "miniprogram_state": "formal",
                "lang": "zh_CN",
            }
            r2 = await client.post(
                f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={tok}",
                json=payload,
            )
            body = r2.json() if r2.status_code == 200 else {}
            if body.get("errcode", -1) == 0:
                return ChannelResult(name=name, ok=True, detail="订阅消息已下发")
            return ChannelResult(
                name=name,
                ok=False,
                detail=f"微信返回 errcode={body.get('errcode')} {body.get('errmsg', '')}",
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("wechat subscribe send failed: %s", e)
        return ChannelResult(name=name, ok=False, detail=f"异常: {e}")


# ── 通道二：APP push（统一封装） ──


async def _send_app_push(
    *,
    user_id: int,
    title: str,
    body: str,
) -> ChannelResult:
    """APP push 通道。

    在该项目的 Flutter APP 中，本期未集成具体 push 服务商。
    本函数采用「凭证缺失即跳过 + 记录日志」的占位实现，确保接入面已就绪。
    后续接入极光/个推/FCM 等 SDK 时，仅需在此处填入实际请求逻辑。

    凭证读取顺序：环境变量 APP_PUSH_PROVIDER（jpush/getui/fcm）+ 对应 KEY/SECRET。
    """
    name = "app_push"
    try:
        provider = os.getenv("APP_PUSH_PROVIDER", "").strip().lower()
        if not provider:
            return ChannelResult(
                name=name,
                ok=False,
                detail="APP push 服务商未配置（APP_PUSH_PROVIDER），跳过",
            )

        if provider == "jpush":
            app_key = os.getenv("JPUSH_APP_KEY", "")
            master_secret = os.getenv("JPUSH_MASTER_SECRET", "")
            if not app_key or not master_secret:
                return ChannelResult(name=name, ok=False, detail="极光凭证缺失")
            try:
                import base64
                import httpx
            except ImportError:
                return ChannelResult(name=name, ok=False, detail="httpx 未安装")

            auth = base64.b64encode(f"{app_key}:{master_secret}".encode()).decode()
            payload = {
                "platform": "all",
                "audience": {"alias": [str(user_id)]},
                "notification": {"alert": body, "android": {"title": title}, "ios": {"title": title}},
            }
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.jpush.cn/v3/push",
                    json=payload,
                    headers={"Authorization": f"Basic {auth}"},
                )
                if r.status_code == 200:
                    return ChannelResult(name=name, ok=True, detail="JPush 已下发")
                return ChannelResult(
                    name=name, ok=False, detail=f"JPush HTTP {r.status_code}: {r.text[:120]}"
                )

        return ChannelResult(name=name, ok=False, detail=f"未支持的 provider: {provider}")
    except Exception as e:  # noqa: BLE001
        logger.warning("app push send failed: %s", e)
        return ChannelResult(name=name, ok=False, detail=f"异常: {e}")


# ── 通道三：短信 ──


async def _send_sms(
    *,
    phone: Optional[str],
    template_params: list[str],
    db: Optional[AsyncSession] = None,
) -> ChannelResult:
    """短信通道。复用现有 app.services.sms_service。

    template_id 从环境变量 RESCHEDULE_SMS_TEMPLATE_ID 读取；
    template_params 顺序按短信模板占位符约定填入：[商品名, 原时段, 新时段, 门店名]。
    缺失模板或凭证时返回 ok=False，不抛异常。
    """
    name = "sms"
    try:
        if not phone:
            return ChannelResult(name=name, ok=False, detail="用户无手机号，跳过")

        template_id = os.getenv("RESCHEDULE_SMS_TEMPLATE_ID", "").strip()
        if not template_id:
            return ChannelResult(
                name=name, ok=False, detail="改期短信模板 ID 未配置（RESCHEDULE_SMS_TEMPLATE_ID）"
            )

        from app.services.sms_service import send_sms

        # 第一次尝试 + 失败重试 1 次（PRD F-11：短信失败重试 1 次）
        last_err: str = ""
        for attempt in range(2):
            try:
                await send_sms(
                    phone=phone,
                    code="",
                    is_test=False,
                    db=db,
                    template_params=template_params,
                    template_id=template_id,
                )
                return ChannelResult(
                    name=name,
                    ok=True,
                    detail=("短信已下发" if attempt == 0 else "短信重试 1 次后下发"),
                )
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
                logger.warning("sms send attempt=%s failed: %s", attempt + 1, e)
                if attempt == 0:
                    await asyncio.sleep(0.5)

        return ChannelResult(name=name, ok=False, detail=f"短信发送失败（已重试 1 次）: {last_err}")
    except Exception as e:  # noqa: BLE001
        logger.warning("sms wrapper failed: %s", e)
        return ChannelResult(name=name, ok=False, detail=f"异常: {e}")


# ─────────── 企业微信告警（PRD-04 §F-04-6 / §2.8） ───────────


async def _send_wechat_work_alert(
    *,
    order_no: str,
    user_name: str,
    user_phone: str,
    old_text: str,
    new_text: str,
    store_name: str,
    failure_detail: str = "",
    webhook_url: Optional[str] = None,
) -> ChannelResult:
    """三通道全部失败时，发送企业微信群机器人告警。

    凭证读取顺序：
      1) 显式传入 webhook_url
      2) 环境变量 WECHAT_WORK_ALERT_WEBHOOK
    缺失则返回 ok=False, detail=未配置（不抛异常）。

    告警内容（PRD §2.8）：
      订单号 / 客户姓名 / 客户手机号 / 原时段 / 新时段 / 门店名
    """
    name = "wechat_work_alert"
    try:
        url = (webhook_url or os.getenv("WECHAT_WORK_ALERT_WEBHOOK", "")).strip()
        if not url:
            return ChannelResult(
                name=name,
                ok=False,
                detail="企业微信告警 webhook 未配置（WECHAT_WORK_ALERT_WEBHOOK），跳过",
            )

        try:
            import httpx
        except ImportError:
            return ChannelResult(name=name, ok=False, detail="httpx 未安装")

        # 隐藏手机号中间四位，避免在群聊里完全暴露
        phone_masked = user_phone or "无"
        if user_phone and len(user_phone) >= 7:
            phone_masked = f"{user_phone[:3]}****{user_phone[-4:]}"

        text_body = (
            "⚠️ 改期通知三通道全部失败，请人工电话联系客户兜底\n"
            f"订单号：{order_no or '未知'}\n"
            f"客户姓名：{user_name or '未知'}\n"
            f"客户手机号：{phone_masked}\n"
            f"原预约时段：{old_text}\n"
            f"新预约时段：{new_text}\n"
            f"门店：{store_name or '未知'}\n"
            f"失败明细：{failure_detail[:200] if failure_detail else '见日志'}"
        )

        payload = {
            "msgtype": "text",
            "text": {"content": text_body},
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            if r.status_code != 200:
                return ChannelResult(
                    name=name,
                    ok=False,
                    detail=f"企业微信告警 HTTP {r.status_code}: {r.text[:120]}",
                )
            try:
                body = r.json()
            except Exception:  # noqa: BLE001
                body = {}
            errcode = body.get("errcode", -1) if isinstance(body, dict) else -1
            if errcode == 0:
                return ChannelResult(name=name, ok=True, detail="企业微信告警已发送")
            return ChannelResult(
                name=name,
                ok=False,
                detail=f"企业微信告警 errcode={errcode} {body.get('errmsg', '') if isinstance(body, dict) else ''}",
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("wechat work alert failed: %s", e)
        return ChannelResult(name=name, ok=False, detail=f"异常: {e}")


# ─────────── 编排入口 ───────────


async def notify_order_rescheduled(
    db: AsyncSession,
    *,
    order,
    old_appointment_time: Optional[datetime],
    new_appointment_time: Optional[datetime],
) -> RescheduleNotifyResult:
    """[F-11] 改期成功后并行下发三通道通知。

    - order：UnifiedOrder ORM 实例（已 selectinload items + product，并能取到 user 与 store）
    - old_appointment_time / new_appointment_time：原 / 新预约时间
    """
    result = RescheduleNotifyResult()

    try:
        # 准备文案上下文 ──────────────────────────────────────────
        items = list(getattr(order, "items", []) or [])
        product_name = "您的预约服务"
        if items:
            first = items[0]
            product_name = (
                getattr(first, "product_name", None)
                or (getattr(getattr(first, "product", None), "name", None) if getattr(first, "product", None) else None)
                or "您的预约服务"
            )

        store = getattr(order, "store", None)
        store_name = getattr(store, "name", "") if store else ""
        store_phone = getattr(store, "contact_phone", "") if store else ""
        brand = os.getenv("NOTIFY_BRAND_NAME", "").strip()

        message_text = build_reschedule_message(
            product_name=product_name,
            old_appointment_time=old_appointment_time,
            new_appointment_time=new_appointment_time,
            store_name=store_name,
            store_phone=store_phone,
            brand=brand,
        )

        user = getattr(order, "user", None)
        user_id = int(getattr(order, "user_id", 0) or 0)
        openid = getattr(user, "wechat_openid", None) if user else None
        phone = getattr(user, "phone", None) if user else None

        old_text = _format_slot_text(old_appointment_time)
        new_text = _format_slot_text(new_appointment_time)

        wx_data = {
            "thing1": {"value": product_name[:20]},
            "time2": {"value": old_text[:20]},
            "time3": {"value": new_text[:20]},
            "thing4": {"value": (store_name or "门店")[:20]},
        }

        sms_params = [product_name[:30], old_text, new_text, store_name or "门店"]

        # 三通道并行下发 ──────────────────────────────────────────
        coros = [
            _send_wechat_subscribe(openid=openid, template_id=None, data=wx_data),
            _send_app_push(user_id=user_id, title="您的预约已改期", body=message_text),
            _send_sms(phone=phone, template_params=sms_params, db=db),
        ]

        gathered = await asyncio.gather(*coros, return_exceptions=True)

        for item in gathered:
            if isinstance(item, ChannelResult):
                result.channels.append(item)
            else:
                result.channels.append(
                    ChannelResult(name="unknown", ok=False, detail=f"异常: {item}")
                )

        # 全部失败时触发企业微信群机器人告警（PRD-04 §F-04-6 / §2.8） ──
        alert_dict: Optional[dict] = None
        if result.all_failed:
            logger.error(
                "[PRD-04] 改期通知三通道全部失败 order_id=%s order_no=%s details=%s",
                getattr(order, "id", None),
                getattr(order, "order_no", None),
                result.to_dict(),
            )
            try:
                user_name = (
                    getattr(user, "real_name", None)
                    or getattr(user, "nickname", None)
                    or getattr(user, "username", None)
                    or ""
                ) if user else ""
                failure_detail = "; ".join(
                    f"{c.name}={c.detail}" for c in result.channels if not c.ok
                )
                alert_res = await _send_wechat_work_alert(
                    order_no=getattr(order, "order_no", "") or "",
                    user_name=str(user_name),
                    user_phone=str(phone or ""),
                    old_text=old_text,
                    new_text=new_text,
                    store_name=store_name,
                    failure_detail=failure_detail,
                )
                # 告警结果挂到 result 上（不计入 channels），便于上层观测
                result.alert = alert_res  # type: ignore[attr-defined]
                alert_dict = {"ok": alert_res.ok, "detail": alert_res.detail}
                logger.warning(
                    "[PRD-04] 企业微信告警结果 order_id=%s ok=%s detail=%s",
                    getattr(order, "id", None),
                    alert_res.ok,
                    alert_res.detail,
                )
            except Exception as _e:  # noqa: BLE001
                logger.warning("企业微信告警调度异常（已忽略）：%s", _e)
        else:
            logger.info(
                "[PRD-04] 改期通知下发完毕 order_id=%s 结果=%s",
                getattr(order, "id", None),
                result.to_dict(),
            )

        # 写入站内 Notification 记录（红点 + 商家详情页通知状态来源） ────────
        try:
            from app.models.models import Notification, NotificationType

            content = message_text
            extra = {
                "order_no": getattr(order, "order_no", None),
                "old_appointment_time": (
                    old_appointment_time.isoformat() if old_appointment_time else None
                ),
                "new_appointment_time": (
                    new_appointment_time.isoformat() if new_appointment_time else None
                ),
                "notify_status": "all_failed" if result.all_failed else "ok",
                "channels": result.to_dict()["channels"],
            }
            if alert_dict is not None:
                extra["wechat_work_alert"] = alert_dict
            n = Notification(
                user_id=user_id,
                order_id=int(getattr(order, "id", 0) or 0),
                event_type="order_rescheduled",
                title="您的预约已改期",
                content=content,
                type=NotificationType.order,
                is_read=False,
                extra_data=extra,
            )
            db.add(n)
            await db.flush()
        except Exception as e:  # noqa: BLE001
            logger.warning("notification write failed for order_rescheduled: %s", e)

    except Exception as e:  # noqa: BLE001
        logger.exception("notify_order_rescheduled fatal: %s", e)

    return result
