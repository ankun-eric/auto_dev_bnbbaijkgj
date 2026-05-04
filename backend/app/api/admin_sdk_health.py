"""[2026-05-05 SDK 健康看板] 后台 SDK 健康检查 API。

接口（仅管理员）：
- GET  /api/admin/health/sdk          读取最新快照
- POST /api/admin/health/sdk/refresh  重新检测并返回最新快照

权限：require_role("admin")
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_role
from app.core.sdk_health import get_snapshot, refresh_snapshot

logger = logging.getLogger("app.sdk_health.api")

router = APIRouter(prefix="/api/admin/health", tags=["运维：SDK 健康"])
_admin_dep = require_role("admin")


@router.get("/sdk")
async def get_sdk_health(_: dict = Depends(_admin_dep)):
    """读取当前 SDK 健康快照。
    - 缺失任意核心依赖：返回 503（注：实际上核心缺失会导致容器启动失败，正常运行时应不会触发）
    - 仅缺失可选 SDK：返回 200，但 ok=false
    - 全部通过：返回 200，ok=true
    """
    snap = get_snapshot()
    if snap["summary"]["missing_core"] > 0:
        raise HTTPException(status_code=503, detail={"reason": "核心依赖缺失", "snapshot": snap})
    return snap


@router.post("/sdk/refresh")
async def refresh_sdk_health(_: dict = Depends(_admin_dep)):
    """重新检测 SDK 健康（运维「重新检测」按钮）。"""
    refresh_snapshot()
    snap = get_snapshot()
    logger.info(
        "[SDK-HEALTH] 管理员触发重新检测 ok=%s summary=%s",
        snap["ok"], snap["summary"],
    )
    return snap
