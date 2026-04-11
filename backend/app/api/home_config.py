from datetime import datetime
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import HomeBanner, HomeMenuItem, SystemConfig
from app.schemas.home_config import (
    HomeBannerCreate,
    HomeBannerResponse,
    HomeBannerUpdate,
    HomeConfigResponse,
    HomeConfigUpdate,
    HomeMenuItemCreate,
    HomeMenuItemResponse,
    HomeMenuItemUpdate,
    SortItem,
)

router = APIRouter(prefix="/api", tags=["首页配置"])
admin_router = APIRouter(prefix="/api/admin", tags=["管理后台-首页配置"])

admin_dep = require_role("admin")

_HOME_CONFIG_KEYS = {
    "home_search_visible": "true",
    "home_search_placeholder": "搜索健康知识、服务、商品",
    "home_grid_columns": "3",
    "home_font_switch_enabled": "true",
    "home_font_default_level": "standard",
    "home_font_standard_size": "14",
    "home_font_large_size": "18",
    "home_font_xlarge_size": "22",
}


async def _get_home_config_dict(db: AsyncSession) -> dict:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(list(_HOME_CONFIG_KEYS.keys())))
    )
    configs = {c.config_key: c.config_value for c in result.scalars().all()}
    merged = {k: configs.get(k, v) for k, v in _HOME_CONFIG_KEYS.items()}
    return merged


def _parse_bool(val: str) -> bool:
    return val.lower() in ("true", "1", "yes")


def _build_config_response(raw: dict) -> HomeConfigResponse:
    return HomeConfigResponse(
        search_visible=_parse_bool(raw["home_search_visible"]),
        search_placeholder=raw["home_search_placeholder"],
        grid_columns=int(raw["home_grid_columns"]),
        font_switch_enabled=_parse_bool(raw["home_font_switch_enabled"]),
        font_default_level=raw["home_font_default_level"],
        font_standard_size=int(raw["home_font_standard_size"]),
        font_large_size=int(raw["home_font_large_size"]),
        font_xlarge_size=int(raw["home_font_xlarge_size"]),
    )


# ════════════════════════════════════════
#  用户端 API（无需登录）
# ════════════════════════════════════════


@router.get("/home-config")
async def get_home_config(db: AsyncSession = Depends(get_db)):
    raw = await _get_home_config_dict(db)
    return _build_config_response(raw)


@router.get("/home-menus")
async def get_visible_menus(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HomeMenuItem)
        .where(HomeMenuItem.is_visible == True)
        .order_by(HomeMenuItem.sort_order.asc())
    )
    items = [HomeMenuItemResponse.model_validate(m) for m in result.scalars().all()]
    return {"items": items}


@router.get("/home-banners")
async def get_visible_banners(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HomeBanner)
        .where(HomeBanner.is_visible == True)
        .order_by(HomeBanner.sort_order.asc())
    )
    items = [HomeBannerResponse.model_validate(b) for b in result.scalars().all()]
    return {"items": items}


# ════════════════════════════════════════
#  管理端 API（需要 admin 权限）
# ════════════════════════════════════════


# ── 首页基础配置 ──

@admin_router.get("/home-config")
async def admin_get_home_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    raw = await _get_home_config_dict(db)
    return _build_config_response(raw)


@admin_router.put("/home-config")
async def admin_update_home_config(
    data: HomeConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    field_key_map = {
        "search_visible": "home_search_visible",
        "search_placeholder": "home_search_placeholder",
        "grid_columns": "home_grid_columns",
        "font_switch_enabled": "home_font_switch_enabled",
        "font_default_level": "home_font_default_level",
        "font_standard_size": "home_font_standard_size",
        "font_large_size": "home_font_large_size",
        "font_xlarge_size": "home_font_xlarge_size",
    }
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        config_key = field_key_map[field]
        str_value = str(value).lower() if isinstance(value, bool) else str(value)
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_key == config_key)
        )
        config = result.scalar_one_or_none()
        if config:
            config.config_value = str_value
            config.updated_at = datetime.utcnow()
        else:
            db.add(SystemConfig(
                config_key=config_key,
                config_value=str_value,
                config_type="home",
                description=config_key,
            ))
    return {"message": "首页配置更新成功"}


# ── 菜单管理 ──

@admin_router.get("/home-menus")
async def admin_list_menus(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HomeMenuItem).order_by(HomeMenuItem.sort_order.asc())
    )
    items = [HomeMenuItemResponse.model_validate(m) for m in result.scalars().all()]
    return {"items": items}


@admin_router.post("/home-menus")
async def admin_create_menu(
    data: HomeMenuItemCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    menu = HomeMenuItem(**data.model_dump())
    db.add(menu)
    await db.flush()
    await db.refresh(menu)
    return HomeMenuItemResponse.model_validate(menu)


@admin_router.put("/home-menus/sort")
async def admin_sort_menus(
    items: List[SortItem] = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for item in items:
        result = await db.execute(
            select(HomeMenuItem).where(HomeMenuItem.id == item.id)
        )
        menu = result.scalar_one_or_none()
        if menu:
            menu.sort_order = item.sort_order
    await db.flush()
    return {"message": "排序更新成功"}


@admin_router.put("/home-menus/{menu_id}")
async def admin_update_menu(
    menu_id: int,
    data: HomeMenuItemUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HomeMenuItem).where(HomeMenuItem.id == menu_id)
    )
    menu = result.scalar_one_or_none()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单项不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(menu, key, value)
    menu.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(menu)
    return HomeMenuItemResponse.model_validate(menu)


@admin_router.delete("/home-menus/{menu_id}")
async def admin_delete_menu(
    menu_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HomeMenuItem).where(HomeMenuItem.id == menu_id)
    )
    menu = result.scalar_one_or_none()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单项不存在")
    await db.delete(menu)
    return {"message": "删除成功"}


# ── Banner 管理 ──

@admin_router.get("/home-banners")
async def admin_list_banners(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HomeBanner).order_by(HomeBanner.sort_order.asc())
    )
    items = [HomeBannerResponse.model_validate(b) for b in result.scalars().all()]
    return {"items": items}


@admin_router.post("/home-banners")
async def admin_create_banner(
    data: HomeBannerCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    banner = HomeBanner(**data.model_dump())
    db.add(banner)
    await db.flush()
    await db.refresh(banner)
    return HomeBannerResponse.model_validate(banner)


@admin_router.put("/home-banners/sort")
async def admin_sort_banners(
    items: List[SortItem] = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for item in items:
        result = await db.execute(
            select(HomeBanner).where(HomeBanner.id == item.id)
        )
        banner = result.scalar_one_or_none()
        if banner:
            banner.sort_order = item.sort_order
    await db.flush()
    return {"message": "排序更新成功"}


@admin_router.put("/home-banners/{banner_id}")
async def admin_update_banner(
    banner_id: int,
    data: HomeBannerUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HomeBanner).where(HomeBanner.id == banner_id)
    )
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(banner, key, value)
    banner.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(banner)
    return HomeBannerResponse.model_validate(banner)


@admin_router.delete("/home-banners/{banner_id}")
async def admin_delete_banner(
    banner_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HomeBanner).where(HomeBanner.id == banner_id)
    )
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner不存在")
    await db.delete(banner)
    return {"message": "删除成功"}
