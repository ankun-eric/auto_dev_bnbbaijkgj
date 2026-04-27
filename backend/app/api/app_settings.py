from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import AppSetting
from app.schemas.app_settings import AppSettingResponse, AppSettingUpdate

router = APIRouter(tags=["应用设置"])

admin_dep = require_role("admin")


@router.get("/api/app-settings/page-style")
async def get_page_style(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "page_style")
    )
    setting = result.scalar_one_or_none()
    if not setting:
        return {"key": "page_style", "value": "ai_chat"}
    return AppSettingResponse.model_validate(setting)


@router.put("/api/admin/app-settings/page-style", response_model=AppSettingResponse)
async def update_page_style(
    data: AppSettingUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if data.value not in ("ai_chat", "menu"):
        raise HTTPException(status_code=400, detail="无效的页面风格值，仅支持 ai_chat 或 menu")

    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "page_style")
    )
    setting = result.scalar_one_or_none()
    if not setting:
        setting = AppSetting(
            key="page_style",
            value=data.value,
            description="用户端首页风格：ai_chat=AI对话页 / menu=菜单页",
        )
        db.add(setting)
    else:
        setting.value = data.value

    await db.flush()
    await db.refresh(setting)
    return AppSettingResponse.model_validate(setting)
