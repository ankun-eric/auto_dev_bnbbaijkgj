from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import TCMConfig, User
from app.schemas.tcm_config import TCMConfigResponse, TCMConfigUpdate

router = APIRouter(prefix="/api/tcm", tags=["中医养生配置"])
admin_router = APIRouter(prefix="/api/admin/tcm", tags=["管理后台-中医养生配置"])


async def _get_or_create_config(db: AsyncSession) -> TCMConfig:
    result = await db.execute(select(TCMConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = TCMConfig(
            tongue_diagnosis_enabled=False,
            face_diagnosis_enabled=False,
            constitution_test_enabled=True,
        )
        db.add(config)
        await db.flush()
        await db.refresh(config)
    return config


@router.get("/config", response_model=TCMConfigResponse)
async def get_tcm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    config = await _get_or_create_config(db)
    return TCMConfigResponse.model_validate(config)


@admin_router.get("/config", response_model=TCMConfigResponse)
async def admin_get_tcm_config(
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    config = await _get_or_create_config(db)
    return TCMConfigResponse.model_validate(config)


@admin_router.put("/config", response_model=TCMConfigResponse)
async def admin_update_tcm_config(
    data: TCMConfigUpdate,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    config = await _get_or_create_config(db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    await db.flush()
    await db.refresh(config)
    return TCMConfigResponse.model_validate(config)
