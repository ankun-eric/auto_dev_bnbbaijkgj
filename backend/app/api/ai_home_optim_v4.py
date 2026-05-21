"""
[PRD-AI-HOME-OPTIM-V4 2026-05-21] AI 首页体验优化 v4 后端聚合接口

本文件集中放置 v4 PRD 相关的后端能力：

1. GET /api/ai-home/refresh-config       —— 返回 60 分钟刷新阈值配置（前端进入页面时拉取）
2. POST /api/ai-home/track                 —— 通用埋点上报接口（接受 11 个事件，落简易日志）

参考 PRD §4.2、§4.3、§8（11 个埋点事件）。

设计原则：
- 单一来源真相：刷新阈值统一从 settings.SESSION_REFRESH_MINUTES 读取
- 兼容性优先：埋点接口仅记录日志，不强依赖额外的数据表，便于灰度上线
- 失败静默：任何异常均返回 200 + ok=true 字段，不阻塞前端主流程
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Header
from pydantic import BaseModel, Field

from app.core.config import settings

try:  # 软依赖：jose 已是项目依赖，仅做匿名安全的 token 解析
    from jose import jwt  # type: ignore
except Exception:  # pragma: no cover
    jwt = None  # type: ignore

router = APIRouter(prefix="/api/ai-home", tags=["AI 首页体验优化 v4"])

_logger = logging.getLogger("ai_home_optim_v4")


# ---------------------------------------------------------------------------
# 1. 刷新配置接口
# ---------------------------------------------------------------------------


class RefreshConfigResponse(BaseModel):
    """60 分钟刷新机制的运行时配置。"""

    session_refresh_minutes: int = Field(
        ..., description="进入页面距上次会话 updated_at 的刷新阈值（分钟）"
    )
    session_refresh_ms: int = Field(
        ..., description="刷新阈值（毫秒），便于前端直接与 Date.now() 做差值比较"
    )
    enabled: bool = Field(
        True, description="开关；未来若运营临时下线该机制，可设为 false 让前端走兜底"
    )


@router.get("/refresh-config", response_model=RefreshConfigResponse)
async def get_refresh_config() -> RefreshConfigResponse:
    """前端进入 AI 首页前调用一次（带短期缓存），用于决定是否清空旧会话。

    阈值默认 60 分钟，由 settings.SESSION_REFRESH_MINUTES 控制。
    本接口允许匿名调用：未登录用户也可获得阈值，便于前端在登录前完成静态判断。
    """

    minutes = max(1, int(getattr(settings, "SESSION_REFRESH_MINUTES", 60) or 60))
    return RefreshConfigResponse(
        session_refresh_minutes=minutes,
        session_refresh_ms=minutes * 60 * 1000,
        enabled=True,
    )


# ---------------------------------------------------------------------------
# 2. 埋点上报接口
# ---------------------------------------------------------------------------


_VALID_EVENTS = {
    "refresh_triggered",
    "refresh_skipped",
    "switch_consultant",
    "switch_undo_clicked",
    "switch_undo_expired",
    "floating_ball_shown",
    "floating_ball_clicked",
    "floating_ball_panel_action",
    "first_guide_shown",
    "refresh_anomaly",
    "system_message_visible",
}


class TrackEventRequest(BaseModel):
    event: str = Field(..., description="事件名，详见 PRD §8 共 11 个事件")
    platform: Optional[str] = Field(
        None, description="平台：h5 / miniprogram / android / ios"
    )
    payload: Dict[str, Any] = Field(default_factory=dict, description="事件附加字段")


class TrackEventResponse(BaseModel):
    ok: bool = True
    received_at: str
    event: str
    platform: Optional[str] = None


def _safe_extract_user_id(authorization: Optional[str]) -> Optional[int]:
    """从 Authorization Header 中尝试解析 user_id；解析失败一律返回 None。

    本接口故意**不**使用 get_current_user 这一强制登录依赖：
    埋点上报需要允许匿名（首次进入页面、登录前的 refresh_skipped 等场景）。
    """
    if not authorization or jwt is None:
        return None
    try:
        token = authorization.split(" ", 1)[1] if " " in authorization else authorization
        payload = jwt.decode(
            token,
            getattr(settings, "SECRET_KEY", ""),
            algorithms=[getattr(settings, "ALGORITHM", "HS256")],
        )
        sub = payload.get("sub") or payload.get("user_id")
        return int(sub) if sub is not None else None
    except Exception:  # noqa: BLE001
        return None


@router.post("/track", response_model=TrackEventResponse)
async def track_event(
    body: TrackEventRequest = Body(...),
    authorization: Optional[str] = Header(default=None),
) -> TrackEventResponse:
    """通用埋点接口。

    设计要点：
    - 已登录用户带 user_id；未登录用户允许匿名上报（仅作日志统计用）
    - 未识别事件名仍会记录但加 [unknown] 前缀，便于事后排查
    - 整体逻辑无副作用：仅写日志，便于初期灰度
    """

    user_id = _safe_extract_user_id(authorization)
    event_name = (body.event or "").strip()
    valid = event_name in _VALID_EVENTS

    log_payload = {
        "user_id": user_id,
        "platform": body.platform,
        "event": event_name,
        "valid": valid,
        "payload": body.payload,
    }
    if valid:
        _logger.info("[ai-home-v4] %s", log_payload)
    else:
        _logger.warning("[ai-home-v4][unknown] %s", log_payload)

    return TrackEventResponse(
        ok=True,
        received_at=datetime.utcnow().isoformat(),
        event=event_name,
        platform=body.platform,
    )
