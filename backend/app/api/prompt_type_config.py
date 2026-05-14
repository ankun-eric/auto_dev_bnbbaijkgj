"""[PRD-PROMPT-CONFIG-V1 2026-05-14] Prompt 类型配置管理 API。

本期前端仅消费 GET 接口（用于"显示已下线"高级模式）；POST/PUT/DELETE 预留下一期。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import PromptTypeConfig, User

router = APIRouter(prefix="/api/admin/prompt-type-config", tags=["Prompt类型配置"])

admin_dep = require_role("admin")


class PromptTypeConfigItem(BaseModel):
    id: int
    type_key: str
    display_name: str
    business_group: str
    description: Optional[str] = None
    allowed_button_types: list = []
    preview_input_default: Optional[str] = None
    is_online: bool
    sort_order: int = 0
    created_by: str = "system"

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[PromptTypeConfigItem])
async def list_prompt_type_configs(
    business_group: Optional[str] = Query(None),
    include_offline: int = Query(1, description="1=含已下线，0=仅在线"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_dep),
):
    stmt = select(PromptTypeConfig).order_by(
        PromptTypeConfig.business_group.asc(),
        PromptTypeConfig.sort_order.asc(),
        PromptTypeConfig.id.asc(),
    )
    if business_group:
        stmt = stmt.where(PromptTypeConfig.business_group == business_group)
    if not include_offline:
        stmt = stmt.where(PromptTypeConfig.is_online == True)  # noqa: E712
    res = await db.execute(stmt)
    return [PromptTypeConfigItem.model_validate(r) for r in res.scalars().all()]


@router.get("/{config_id}", response_model=PromptTypeConfigItem)
async def get_prompt_type_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_dep),
):
    cfg = await db.get(PromptTypeConfig, config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    return PromptTypeConfigItem.model_validate(cfg)
