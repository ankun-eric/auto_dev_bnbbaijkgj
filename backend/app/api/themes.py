"""PRD-447 v2 · 后台主题可配置模块

4 个 API：
- GET    /api/admin/themes              主题列表（分页）
- GET    /api/admin/themes/{id}         主题详情（含完整 token JSON）
- PUT    /api/admin/themes/{id}         编辑（草稿态）
- POST   /api/admin/themes/{id}/activate 启用（事务：把当前启用的置为禁用）

H5 注入：
- GET    /api/h5/active-theme           当前启用主题的 token JSON（H5 启动时拉取）

设计：
- 启动时内存初始化默认主题（id=1，方案 A 全量 token，已启用）
- 改动落到内存（与 login_ui_config 同风格），生产环境后续可平滑接入持久化
- 失败降级：H5 注入接口任何异常都返回工程内置默认 token，保证不影响渲染
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["后台主题（PRD-447）"])


# ============================================================
# 默认方案 A 主题（与 h5-web/src/app/globals.css 中追加的 token 严格对齐）
# ============================================================
_DEFAULT_THEME_TOKENS: Dict[str, Any] = {
    "atomic": {
        "color_brand": {
            "50": "#f0f9ff", "100": "#e0f2fe", "200": "#bae6fd",
            "300": "#7dd3fc", "400": "#38bdf8", "500": "#0ea5e9",
            "600": "#0284c7", "700": "#0369a1", "800": "#075985",
            "900": "#0c4a6e", "950": "#082f49",
        },
        "color_neutral": {
            "50": "#fafafa", "100": "#f5f5f5", "200": "#e5e5e5",
            "300": "#d4d4d4", "400": "#a3a3a3", "500": "#737373",
            "600": "#525252", "700": "#404040", "800": "#262626",
            "900": "#171717",
        },
        "gradients": {
            "topbar":    "linear-gradient(180deg, #bae6fd 0%, #7dd3fc 100%)",
            "fn_cell":   "linear-gradient(135deg, #bae6fd 0%, #7dd3fc 100%)",
            "primary":   "linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)",
            "hero_dark": "linear-gradient(135deg, #0c4a6e 0%, #075985 100%)",
            "user_card": "linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%)",
        },
        "font_size": {
            "xs": "0.6875rem", "sm": "0.75rem", "base": "0.875rem",
            "md": "1rem", "lg": "1.125rem", "xl": "1.25rem",
            "2xl": "1.5rem", "3xl": "1.875rem",
        },
        "space": {
            "1": "0.25rem", "2": "0.5rem", "3": "0.75rem", "4": "1rem",
            "5": "1.25rem", "6": "1.5rem", "8": "2rem", "10": "2.5rem", "12": "3rem",
        },
        "radius": {
            "sm": "4px", "md": "8px", "lg": "12px", "xl": "16px",
            "2xl": "20px", "full": "9999px",
        },
        "shadow": {
            "card":   "0 2px 8px 0 rgba(14, 165, 233, 0.08)",
            "bubble": "0 1px 4px 0 rgba(2, 132, 199, 0.10)",
            "float":  "0 4px 12px 0 rgba(56, 189, 248, 0.20)",
            "modal":  "0 8px 24px 0 rgba(12, 74, 110, 0.16)",
        },
        "motion": {
            "ease_standard":   "cubic-bezier(0.4, 0.0, 0.2, 1)",
            "ease_decelerate": "cubic-bezier(0.0, 0.0, 0.2, 1)",
            "duration_fast":   "150ms",
            "duration_base":   "250ms",
            "duration_slow":   "400ms",
        },
    },
    "theme": {
        "color_primary":        "var(--color-brand-400)",
        "color_primary_hover":  "var(--color-brand-500)",
        "color_primary_active": "var(--color-brand-600)",
        "color_primary_bg":     "var(--color-brand-50)",
        "color_primary_border": "var(--color-brand-200)",
        "color_text_strong":    "var(--color-neutral-900)",
        "color_text_base":      "var(--color-neutral-700)",
        "color_text_weak":      "var(--color-neutral-500)",
        "color_text_disabled":  "var(--color-neutral-300)",
        "color_text_inverse":   "#ffffff",
        "color_bg_page":        "#ffffff",
        "color_bg_card":        "#ffffff",
        "color_bg_subtle":      "var(--color-neutral-50)",
        "color_bg_overlay":     "rgba(12, 74, 110, 0.40)",
    },
    "semantic": {
        "color_topbar_bg":         "var(--gradient-topbar-a)",
        "color_fn_cell_bg":        "var(--gradient-fn-cell)",
        "color_btn_primary_bg":    "var(--gradient-primary)",
        "color_bubble_user_bg":    "var(--gradient-user-card-a)",
        "color_bubble_ai_bg":      "var(--color-bg-card)",
        "color_card_medical_line": "var(--color-brand-400)",
        "color_chip_family_bg":    "var(--color-brand-100)",
        "color_radar_fill":        "rgba(56, 189, 248, 0.30)",
        "color_radar_stroke":      "var(--color-brand-500)",
    },
}


def _now_ts() -> int:
    return int(time.time() * 1000)


# 内存级主题仓库（生产可平滑迁移到 DB）
_themes_store: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "name": "方案 A · 默认主题（晴空淡天蓝）",
        "status": "active",  # active / draft / disabled
        "version": 1,
        "tokens": _DEFAULT_THEME_TOKENS,
        "updated_at": _now_ts(),
    },
}
_active_theme_id: int = 1
_next_id: int = 2


# ============================================================
# Pydantic Schemas
# ============================================================
class ThemeListItem(BaseModel):
    id: int
    name: str
    status: str
    version: int
    updated_at: int


class ThemeListResponse(BaseModel):
    items: List[ThemeListItem]
    total: int
    page: int
    size: int


class ThemeDetail(BaseModel):
    id: int
    name: str
    status: str
    version: int
    tokens: Dict[str, Any]
    updated_at: int


class ThemeUpdatePayload(BaseModel):
    name: Optional[str] = None
    tokens: Optional[Dict[str, Any]] = None


class ThemeActivateResponse(BaseModel):
    id: int
    status: str
    version: int


class ActiveThemeResponse(BaseModel):
    id: int
    name: str
    version: int
    tokens: Dict[str, Any]


# ============================================================
# 4 个 admin API
# ============================================================
@router.get("/api/admin/themes", response_model=ThemeListResponse)
async def list_themes(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    items_all = sorted(_themes_store.values(), key=lambda t: -t["updated_at"])
    total = len(items_all)
    start = (page - 1) * size
    page_items = items_all[start:start + size]
    return ThemeListResponse(
        items=[ThemeListItem(
            id=t["id"], name=t["name"], status=t["status"],
            version=t["version"], updated_at=t["updated_at"],
        ) for t in page_items],
        total=total, page=page, size=size,
    )


@router.get("/api/admin/themes/{theme_id}", response_model=ThemeDetail)
async def get_theme(theme_id: int):
    t = _themes_store.get(theme_id)
    if not t:
        raise HTTPException(status_code=404, detail="theme not found")
    return ThemeDetail(**t)


@router.put("/api/admin/themes/{theme_id}", response_model=ThemeDetail)
async def update_theme(theme_id: int, payload: ThemeUpdatePayload):
    t = _themes_store.get(theme_id)
    if not t:
        raise HTTPException(status_code=404, detail="theme not found")
    if payload.name is not None:
        t["name"] = payload.name
    if payload.tokens is not None:
        # 浅校验：必须含三层
        for k in ("atomic", "theme", "semantic"):
            if k not in payload.tokens:
                raise HTTPException(status_code=400, detail=f"tokens 缺少 {k} 层")
        t["tokens"] = payload.tokens
    # 编辑后落到草稿，启用要走 activate 接口
    if t["status"] == "active":
        t["status"] = "draft"
    t["version"] += 1
    t["updated_at"] = _now_ts()
    return ThemeDetail(**t)


@router.post("/api/admin/themes/{theme_id}/activate", response_model=ThemeActivateResponse)
async def activate_theme(theme_id: int):
    """启用某主题：事务式把其它启用主题置为禁用。"""
    global _active_theme_id
    target = _themes_store.get(theme_id)
    if not target:
        raise HTTPException(status_code=404, detail="theme not found")
    for tid, t in _themes_store.items():
        if tid != theme_id and t["status"] == "active":
            t["status"] = "disabled"
    target["status"] = "active"
    target["version"] += 1
    target["updated_at"] = _now_ts()
    _active_theme_id = theme_id
    return ThemeActivateResponse(id=theme_id, status="active", version=target["version"])


# ============================================================
# H5 注入接口（无鉴权，启动时拉）
# ============================================================
@router.get("/api/h5/active-theme", response_model=ActiveThemeResponse)
async def get_active_theme_for_h5():
    """H5 启动时拉取，失败降级请使用前端工程内置默认 token。"""
    t = _themes_store.get(_active_theme_id) or _themes_store[1]
    return ActiveThemeResponse(
        id=t["id"], name=t["name"], version=t["version"], tokens=t["tokens"],
    )
