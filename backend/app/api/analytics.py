"""
[PRD-423 T-08 2026-05-08] AI 对话页埋点接收接口

设计原则：
- 仅做最小可用接收，不做复杂落库（避免引入新表迁移风险）
- 失败容忍：任何字段缺失/类型不对都返回 200 ok，避免影响前端主流程
- 日志记录：所有事件以 INFO 级别落入应用日志，便于运营/数据团队 ETL
- 后续若需要严格分析，可平滑切换到独立的 analytics_events 表
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

logger = logging.getLogger("app.analytics")


# PRD v1.1 §6 已声明的事件枚举（白名单），不在白名单内的事件依旧接收但单独打标
KNOWN_EVENTS = {
    "ai_chat_page_view",
    "ai_chat_target_switch",
    "ai_chat_archive_history",
    "ai_chat_profile_row_show",
    "ai_chat_profile_card_expand",
    "ai_chat_profile_card_collapse",
    "ai_chat_scroll_to_bottom_click",
    "ai_chat_punchcard_drag",
    "ai_chat_no_self_profile_tip_click",
    "ai_chat_send",
}


@router.post("/track")
async def track_event(request: Request) -> Dict[str, Any]:
    """
    上报单条埋点事件。
    Body: { "event": "ai_chat_send", "params": {...}, "ts": 1700000000000 }
    返回：{ "ok": true } —— 即使解析失败也返回 ok=true，避免前端无谓重试。
    """
    raw: Optional[bytes] = None
    payload: Dict[str, Any] = {}
    try:
        raw = await request.body()
        if raw:
            payload = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                payload = {}
    except Exception:
        payload = {}

    event = str(payload.get("event") or "").strip()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    ts = payload.get("ts")
    if not isinstance(ts, (int, float)) or ts <= 0:
        ts = int(time.time() * 1000)

    if not event:
        # 无 event key —— 静默 ok
        return {"ok": True, "skipped": "no_event"}

    is_known = event in KNOWN_EVENTS

    # 取请求侧元信息（不强制拿用户态，避免登录态依赖让埋点变重）
    client_ua = request.headers.get("user-agent", "") or ""
    client_ref = request.headers.get("referer", "") or ""
    client_ip = (
        request.headers.get("x-forwarded-for")
        or (request.client.host if request.client else "")
        or ""
    )
    if "," in client_ip:
        client_ip = client_ip.split(",", 1)[0].strip()

    # 写入应用日志：JSON 单行，便于后续 grep / ETL
    record = {
        "type": "ai_chat_track",
        "event": event,
        "is_known": is_known,
        "params": params,
        "ts": int(ts),
        "ua": client_ua[:200],
        "ref": client_ref[:200],
        "ip": client_ip[:64],
    }
    try:
        logger.info("track %s", json.dumps(record, ensure_ascii=False, default=str))
    except Exception:
        # 兜底：日志失败不能影响业务流
        pass

    return {"ok": True, "event": event, "is_known": is_known}


@router.post("/track/batch")
async def track_batch(request: Request) -> Dict[str, Any]:
    """
    批量上报（前端队列恢复时使用）。
    Body: { "items": [ { "event": "...", "params": {...}, "ts": ... }, ... ] }
    """
    accepted = 0
    try:
        raw = await request.body()
        if raw:
            payload = json.loads(raw.decode("utf-8") or "{}") or {}
            items = payload.get("items") if isinstance(payload, dict) else None
            if isinstance(items, list):
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    event = str(it.get("event") or "").strip()
                    if not event:
                        continue
                    params = it.get("params") if isinstance(it.get("params"), dict) else {}
                    ts = it.get("ts")
                    if not isinstance(ts, (int, float)) or ts <= 0:
                        ts = int(time.time() * 1000)
                    record = {
                        "type": "ai_chat_track",
                        "event": event,
                        "is_known": event in KNOWN_EVENTS,
                        "params": params,
                        "ts": int(ts),
                    }
                    try:
                        logger.info("track %s", json.dumps(record, ensure_ascii=False, default=str))
                    except Exception:
                        pass
                    accepted += 1
    except Exception:
        pass
    return {"ok": True, "accepted": accepted}
