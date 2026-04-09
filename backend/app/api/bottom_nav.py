from datetime import datetime
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import BottomNavConfig
from app.schemas.bottom_nav import (
    BottomNavCreate,
    BottomNavResponse,
    BottomNavSortItem,
    BottomNavUpdate,
)

router = APIRouter(prefix="/api", tags=["底部导航"])
admin_router = APIRouter(prefix="/api/admin", tags=["管理后台-底部导航"])

admin_dep = require_role("admin")

ALLOWED_ICON_KEYS = {"home", "chat", "service", "order", "record", "mall", "health", "report", "bell", "profile"}


# ════════════════════════════════════════
#  H5 端 API（无需认证）
# ════════════════════════════════════════


@router.get("/h5/bottom-nav")
async def get_bottom_nav(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BottomNavConfig)
        .where(BottomNavConfig.is_visible == True)
        .order_by(BottomNavConfig.sort_order.asc())
    )
    items = result.scalars().all()

    fixed_home = [i for i in items if i.is_fixed and i.sort_order == 0]
    fixed_tail = [i for i in items if i.is_fixed and i.sort_order == 99]
    middle = [i for i in items if not (i.is_fixed and i.sort_order in (0, 99))]

    ordered = fixed_home + middle + fixed_tail
    data = [BottomNavResponse.model_validate(n).model_dump(mode="json") for n in ordered]
    return JSONResponse(content={"code": 0, "data": data})


# ════════════════════════════════════════
#  管理端 API（需要 admin 权限）
# ════════════════════════════════════════


@admin_router.get("/bottom-nav")
async def admin_list_bottom_nav(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BottomNavConfig).order_by(BottomNavConfig.sort_order.asc())
    )
    items = [BottomNavResponse.model_validate(n) for n in result.scalars().all()]
    return {"items": items}


@admin_router.post("/bottom-nav")
async def admin_create_bottom_nav(
    data: BottomNavCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="名称不能为空")
    if len(data.name) > 6:
        raise HTTPException(status_code=400, detail="名称最多6个字符")
    if not data.path or not data.path.startswith("/"):
        raise HTTPException(status_code=400, detail="路径不能为空且必须以 / 开头")
    if data.icon_key not in ALLOWED_ICON_KEYS:
        raise HTTPException(status_code=400, detail=f"icon_key 必须在预设图标库范围内: {sorted(ALLOWED_ICON_KEYS)}")

    count_result = await db.execute(
        select(BottomNavConfig).where(BottomNavConfig.is_fixed == False)
    )
    configurable_count = len(count_result.scalars().all())
    if configurable_count >= 3:
        raise HTTPException(status_code=400, detail="可配置导航项数量不能超过3个")

    max_order_result = await db.execute(
        select(BottomNavConfig)
        .where(BottomNavConfig.is_fixed == False)
        .order_by(BottomNavConfig.sort_order.desc())
    )
    last = max_order_result.scalars().first()
    next_order = (last.sort_order + 1) if last else 1

    nav = BottomNavConfig(
        name=data.name,
        icon_key=data.icon_key,
        path=data.path,
        sort_order=next_order,
        is_visible=data.is_visible,
        is_fixed=False,
    )
    db.add(nav)
    await db.flush()
    await db.refresh(nav)
    return BottomNavResponse.model_validate(nav)


@admin_router.put("/bottom-nav/sort")
async def admin_sort_bottom_nav(
    items: List[BottomNavSortItem] = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for item in items:
        result = await db.execute(
            select(BottomNavConfig).where(BottomNavConfig.id == item.id)
        )
        nav = result.scalar_one_or_none()
        if nav and not nav.is_fixed:
            nav.sort_order = item.sort_order
    await db.flush()
    return {"message": "排序更新成功"}


@admin_router.put("/bottom-nav/{nav_id}")
async def admin_update_bottom_nav(
    nav_id: int,
    data: BottomNavUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BottomNavConfig).where(BottomNavConfig.id == nav_id)
    )
    nav = result.scalar_one_or_none()
    if not nav:
        raise HTTPException(status_code=404, detail="导航项不存在")
    if nav.is_fixed:
        raise HTTPException(status_code=400, detail="固定导航项不可编辑")

    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data:
        if not update_data["name"] or not update_data["name"].strip():
            raise HTTPException(status_code=400, detail="名称不能为空")
        if len(update_data["name"]) > 6:
            raise HTTPException(status_code=400, detail="名称最多6个字符")
    if "path" in update_data:
        if not update_data["path"] or not update_data["path"].startswith("/"):
            raise HTTPException(status_code=400, detail="路径不能为空且必须以 / 开头")
    if "icon_key" in update_data:
        if update_data["icon_key"] not in ALLOWED_ICON_KEYS:
            raise HTTPException(status_code=400, detail=f"icon_key 必须在预设图标库范围内: {sorted(ALLOWED_ICON_KEYS)}")

    for key, value in update_data.items():
        setattr(nav, key, value)
    nav.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(nav)
    return BottomNavResponse.model_validate(nav)


@admin_router.delete("/bottom-nav/{nav_id}")
async def admin_delete_bottom_nav(
    nav_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BottomNavConfig).where(BottomNavConfig.id == nav_id)
    )
    nav = result.scalar_one_or_none()
    if not nav:
        raise HTTPException(status_code=404, detail="导航项不存在")
    if nav.is_fixed:
        raise HTTPException(status_code=400, detail="固定导航项不可删除")
    await db.delete(nav)
    return {"message": "删除成功"}
