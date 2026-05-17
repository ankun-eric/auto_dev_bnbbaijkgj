"""[PRD-MED-PLAN-ADD-OPTIM-V1 2026-05-17] 添加用药计划页面优化 - 后端支持接口

新增 1 个接口：
- GET /api/medication-library/suggest?q=...&limit=6
  药品名称联想下拉。复用 medication_library 表，匹配 name / generic_name 任一前缀或包含。
  入参 q 需要 >=2 个字符，<2 字符直接返回空列表。默认/最大返回 6 条。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import MedicationLibrary, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/medication-library", tags=["medication-add-optim-v1"])


@router.get("/suggest")
async def suggest_medications(
    q: str = Query("", description="联想关键词，至少 2 个字符开始联想"),
    limit: int = Query(6, ge=1, le=20, description="返回条数，默认 6 条，最大 20"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """[PRD-MED-PLAN-ADD-OPTIM-V1] 药品名称联想

    规则：
    - q < 2 字符 → 返回空列表（前端不渲染下拉）
    - q >= 2 字符 → 在 medication_library 中按 name / generic_name 模糊匹配
    - 最多返回 limit 条（默认 6）
    - 优先级：name 前缀 > generic_name 前缀 > name 包含 > generic_name 包含
    """
    q_norm = (q or "").strip()
    if len(q_norm) < 2:
        return {"items": [], "total": 0, "q": q_norm}

    like_prefix = f"{q_norm}%"
    like_contain = f"%{q_norm}%"
    max_n = max(1, min(int(limit or 6), 20))

    seen_ids: set[int] = set()
    items: List[Dict[str, Any]] = []

    async def _collect(stmt) -> None:
        if len(items) >= max_n:
            return
        rows = (await db.execute(stmt.limit(max_n * 2))).scalars().all()
        for r in rows:
            if r.id in seen_ids:
                continue
            seen_ids.add(r.id)
            items.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "generic_name": r.generic_name,
                    "spec": r.spec,
                    "manufacturer": r.manufacturer,
                }
            )
            if len(items) >= max_n:
                return

    base_where = (MedicationLibrary.is_active == True,)  # noqa: E712

    await _collect(
        select(MedicationLibrary)
        .where(*base_where, MedicationLibrary.name.like(like_prefix))
        .order_by(MedicationLibrary.name.asc())
    )
    if len(items) < max_n:
        await _collect(
            select(MedicationLibrary)
            .where(*base_where, MedicationLibrary.generic_name.like(like_prefix))
            .order_by(MedicationLibrary.generic_name.asc())
        )
    if len(items) < max_n:
        await _collect(
            select(MedicationLibrary)
            .where(
                *base_where,
                or_(
                    MedicationLibrary.name.like(like_contain),
                    MedicationLibrary.generic_name.like(like_contain),
                ),
            )
            .order_by(MedicationLibrary.name.asc())
        )

    return {"items": items[:max_n], "total": len(items), "q": q_norm}
