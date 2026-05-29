"""[BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29] 前端兜底响应监控接收端

用途：H5 前端在 axios 全局响应拦截器中识别到「网关兜底响应」（如 200 OK 但
响应体为 "gateway ok" 之类的纯文本）时，通过 navigator.sendBeacon 向本端点
异步上报一条事件，便于服务端记录 WARN 级日志，让"静默失败"能被主动发现。

设计要点：
- 无鉴权（任何客户端均可上报，避免上报本身被 401 拦截）
- 仅做 INFO/WARN 级日志记录，不入库、不阻塞任何业务流程
- 接口幂等且对响应体内容极宽松，避免成为新的故障点
- 限制 body 长度，避免恶意大包打爆日志
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Request

logger = logging.getLogger("frontend_log")

router = APIRouter(prefix="/api", tags=["frontend-log"])


@router.post("/_frontend_log")
async def receive_frontend_log(request: Request) -> Dict[str, Any]:
    """接收前端事件上报（主要用于网关兜底响应告警）。"""
    try:
        raw = await request.body()
        if not raw:
            return {"ok": True}
        # 限制 4KB，避免恶意大包
        if len(raw) > 4096:
            raw = raw[:4096]
        try:
            payload = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            payload = {"raw": raw.decode("utf-8", errors="replace")}
        ev_type = str(payload.get("type") or "unknown")
        if ev_type == "gateway_fallback":
            logger.warning(
                "[gateway-fallback] url=%s method=%s status=%s ct=%s body=%s "
                "page=%s user=%s ts=%s",
                payload.get("full_url") or payload.get("url"),
                payload.get("method"),
                payload.get("status"),
                payload.get("content_type"),
                str(payload.get("body_excerpt"))[:200],
                payload.get("page_path"),
                payload.get("user_id"),
                payload.get("ts"),
            )
        else:
            logger.info("[frontend-log] %s", payload)
    except Exception as exc:  # pragma: no cover - 日志接口本身严禁向调用方抛错
        logger.warning("[frontend-log] receiver failed: %s", exc)
    return {"ok": True}
