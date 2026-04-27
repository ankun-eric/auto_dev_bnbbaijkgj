from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import VideoConsultConfig
from app.schemas.video_consult import VideoConsultConfigResponse, VideoConsultConfigUpdate

router = APIRouter(prefix="/api/admin/video-consult-config", tags=["视频客服配置"])

admin_dep = require_role("admin")


@router.get("", response_model=VideoConsultConfigResponse)
async def get_video_consult_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VideoConsultConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = VideoConsultConfig()
        db.add(config)
        await db.flush()
        await db.refresh(config)
    return VideoConsultConfigResponse.model_validate(config)


@router.put("", response_model=VideoConsultConfigResponse)
async def update_video_consult_config(
    data: VideoConsultConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VideoConsultConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = VideoConsultConfig()
        db.add(config)
        await db.flush()
        await db.refresh(config)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.flush()
    await db.refresh(config)
    return VideoConsultConfigResponse.model_validate(config)
