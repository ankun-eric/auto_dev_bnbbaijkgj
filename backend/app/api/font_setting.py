from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User
from app.schemas.font_setting import FontSettingResponse, FontSettingUpdate

router = APIRouter(prefix="/api/user", tags=["字体设置"])


@router.get("/font-setting", response_model=FontSettingResponse)
async def get_font_setting(current_user: User = Depends(get_current_user)):
    return FontSettingResponse(font_size_level=current_user.chat_font_size or "standard")


@router.put("/font-setting", response_model=FontSettingResponse)
async def update_font_setting(
    data: FontSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.chat_font_size = data.font_size_level
    await db.flush()
    await db.refresh(current_user)
    return FontSettingResponse(font_size_level=current_user.chat_font_size)
