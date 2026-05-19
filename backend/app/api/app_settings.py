from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import AppSetting

router = APIRouter(tags=["应用设置"])

admin_dep = require_role("admin")

_CHAT_IDLE_TIMEOUT_KEY = "chat_idle_timeout_minutes"
_CHAT_IDLE_TIMEOUT_DEFAULT = 30
_CHAT_IDLE_TIMEOUT_OPTIONS = [30, 60]


class ChatIdleTimeoutUpdate(BaseModel):
    timeout_minutes: int


# [PRD-LEGACY-HOME-CLEANUP-V1.1 2026-05-19]
# 旧菜单式 /home 首页已下线，page-style 切换 UI 已物理删除。
# - PUT /api/admin/app-settings/page-style：已删除（admin 端无调用）
# - GET /api/app-settings/page-style：保留为常量接口，永久返回 ai_chat，
#   待《小程序 & Flutter App AI 首页改造 PRD》完成后随 v1.2 一并彻底清理。
@router.get("/api/app-settings/page-style")
async def get_page_style():
    return {"key": "page_style", "value": "ai_chat"}


# ──────────────── 空闲超时配置 ────────────────


@router.get("/api/app-settings/chat-idle-timeout")
async def get_chat_idle_timeout(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == _CHAT_IDLE_TIMEOUT_KEY)
    )
    setting = result.scalar_one_or_none()
    timeout = int(setting.value) if setting and setting.value else _CHAT_IDLE_TIMEOUT_DEFAULT
    return {"code": 200, "data": {"timeout_minutes": timeout, "options": _CHAT_IDLE_TIMEOUT_OPTIONS}}


@router.get("/api/admin/app-settings/chat-idle-timeout")
async def admin_get_chat_idle_timeout(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == _CHAT_IDLE_TIMEOUT_KEY)
    )
    setting = result.scalar_one_or_none()
    timeout = int(setting.value) if setting and setting.value else _CHAT_IDLE_TIMEOUT_DEFAULT
    return {"code": 200, "data": {"timeout_minutes": timeout, "options": _CHAT_IDLE_TIMEOUT_OPTIONS}}


@router.put("/api/admin/app-settings/chat-idle-timeout")
async def admin_update_chat_idle_timeout(
    data: ChatIdleTimeoutUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if data.timeout_minutes not in _CHAT_IDLE_TIMEOUT_OPTIONS:
        raise HTTPException(status_code=400, detail=f"无效的超时值，仅支持 {_CHAT_IDLE_TIMEOUT_OPTIONS}")

    result = await db.execute(
        select(AppSetting).where(AppSetting.key == _CHAT_IDLE_TIMEOUT_KEY)
    )
    setting = result.scalar_one_or_none()
    if not setting:
        setting = AppSetting(
            key=_CHAT_IDLE_TIMEOUT_KEY,
            value=str(data.timeout_minutes),
            description="AI对话空闲超时时间（分钟）",
        )
        db.add(setting)
    else:
        setting.value = str(data.timeout_minutes)

    await db.flush()
    await db.refresh(setting)
    return {"code": 200, "data": {"timeout_minutes": int(setting.value), "options": _CHAT_IDLE_TIMEOUT_OPTIONS}}
