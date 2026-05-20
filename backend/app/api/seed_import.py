"""[PRD-AI-PAGE-OPTIM-V1 2026-05-21] 种子数据导入管理后台 API

提供以下接口（前缀 /api/admin）：
- GET  /seed-packs              列出所有种子包 + 当前状态
- GET  /seed-packs/{code}       获取单个种子包详情
- POST /seed-packs/{code}/install   一键导入（body: {conflict_mode: 'skip'|'overwrite'}）
- POST /seed-packs/{code}/uninstall 一键卸载

权限：仅 super_admin（或 admin）可访问。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.seed_packs import SEED_PACK_REGISTRY, get_pack, list_packs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["管理后台-种子数据导入"])
admin_dep = require_role("admin", "super_admin")


class InstallRequest(BaseModel):
    conflict_mode: str = Field(
        default="skip",
        description="冲突策略：'skip'（已存在则跳过）/ 'overwrite'（删除现有后重新插入）",
    )


def _pack_to_brief(pack) -> dict[str, Any]:
    return {
        "code": pack.code,
        "name": pack.name,
        "description": pack.description,
        "summary": pack.summary,
        "source": pack.source,
        "version": pack.version,
    }


def _pack_to_detail(pack) -> dict[str, Any]:
    d = _pack_to_brief(pack)
    d["detail"] = pack.detail or {}
    return d


@router.get("/seed-packs")
async def list_seed_packs(
    db: AsyncSession = Depends(get_db),
    _user=Depends(admin_dep),
):
    """列出全部种子包 + 当前数据库状态"""
    packs = []
    for p in list_packs():
        try:
            status = await p.detect(db)
        except Exception as e:  # noqa: BLE001
            logger.warning("detect %s failed: %s", p.code, e)
            status = "unknown"
        packs.append({**_pack_to_brief(p), "status": status})
    return {"items": packs, "total": len(packs)}


@router.get("/seed-packs/{code}")
async def get_seed_pack(
    code: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(admin_dep),
):
    pack = get_pack(code)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"种子包 {code} 不存在")
    try:
        status = await pack.detect(db)
    except Exception as e:  # noqa: BLE001
        logger.warning("detect %s failed: %s", code, e)
        status = "unknown"
    return {**_pack_to_detail(pack), "status": status}


@router.post("/seed-packs/{code}/install")
async def install_seed_pack(
    code: str,
    body: InstallRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(admin_dep),
):
    pack = get_pack(code)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"种子包 {code} 不存在")
    conflict_mode = (body.conflict_mode if body else "skip").lower()
    if conflict_mode not in ("skip", "overwrite"):
        raise HTTPException(status_code=400, detail="conflict_mode 必须为 skip 或 overwrite")
    try:
        result = await pack.install(db, conflict_mode)
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.exception("install %s failed", code)
        raise HTTPException(status_code=500, detail=f"导入失败：{e}")
    # 安装后重新探测状态
    try:
        status = await pack.detect(db)
    except Exception:  # noqa: BLE001
        status = "unknown"
    logger.info(
        "[seed_import] user=%s install pack=%s mode=%s result=%s",
        getattr(user, "id", None),
        code,
        conflict_mode,
        result,
    )
    return {"ok": True, "code": code, "status": status, "result": result}


@router.post("/seed-packs/{code}/uninstall")
async def uninstall_seed_pack(
    code: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(admin_dep),
):
    pack = get_pack(code)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"种子包 {code} 不存在")
    try:
        result = await pack.uninstall(db)
        await db.commit()
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        logger.exception("uninstall %s failed", code)
        raise HTTPException(status_code=500, detail=f"卸载失败：{e}")
    try:
        status = await pack.detect(db)
    except Exception:  # noqa: BLE001
        status = "unknown"
    logger.info(
        "[seed_import] user=%s uninstall pack=%s result=%s",
        getattr(user, "id", None),
        code,
        result,
    )
    return {"ok": True, "code": code, "status": status, "result": result}
