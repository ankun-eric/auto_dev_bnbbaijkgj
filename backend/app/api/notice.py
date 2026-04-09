from datetime import datetime
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import HomeNotice
from app.schemas.notice import (
    NoticeCreate,
    NoticePatchStatus,
    NoticeResponse,
    NoticeSortItem,
    NoticeUpdate,
)

router = APIRouter(prefix="/api", tags=["公告栏"])
admin_router = APIRouter(prefix="/api/admin", tags=["管理后台-公告栏"])

admin_dep = require_role("admin")


# ════════════════════════════════════════
#  用户端 API（无需认证）
# ════════════════════════════════════════


@router.get("/notices/active")
async def get_active_notices(db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    result = await db.execute(
        select(HomeNotice)
        .where(
            HomeNotice.is_enabled == True,
            HomeNotice.start_time <= now,
            HomeNotice.end_time >= now,
        )
        .order_by(HomeNotice.sort_order.asc())
    )
    items = [NoticeResponse.model_validate(n) for n in result.scalars().all()]
    return JSONResponse(
        content={"items": [item.model_dump(mode="json") for item in items]},
        headers={"Cache-Control": "public, max-age=1800"},
    )


# ════════════════════════════════════════
#  管理端 API（需要 admin 权限）
# ════════════════════════════════════════


@admin_router.get("/notices")
async def admin_list_notices(
    page: int = 1,
    page_size: int = 20,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    total_result = await db.execute(select(func.count()).select_from(HomeNotice))
    total = total_result.scalar_one()
    result = await db.execute(
        select(HomeNotice)
        .order_by(HomeNotice.sort_order.asc(), HomeNotice.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = [NoticeResponse.model_validate(n) for n in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.post("/notices")
async def admin_create_notice(
    data: NoticeCreate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    notice = HomeNotice(**data.model_dump())
    db.add(notice)
    await db.flush()
    await db.refresh(notice)
    return NoticeResponse.model_validate(notice)


@admin_router.put("/notices/sort")
async def admin_sort_notices(
    items: List[NoticeSortItem] = Body(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    for item in items:
        result = await db.execute(select(HomeNotice).where(HomeNotice.id == item.id))
        notice = result.scalar_one_or_none()
        if notice:
            notice.sort_order = item.sort_order
    await db.flush()
    return {"message": "排序更新成功"}


@admin_router.put("/notices/{notice_id}")
async def admin_update_notice(
    notice_id: int,
    data: NoticeUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HomeNotice).where(HomeNotice.id == notice_id))
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(status_code=404, detail="公告不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(notice, key, value)
    notice.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(notice)
    return NoticeResponse.model_validate(notice)


@admin_router.delete("/notices/{notice_id}")
async def admin_delete_notice(
    notice_id: int,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HomeNotice).where(HomeNotice.id == notice_id))
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(status_code=404, detail="公告不存在")
    await db.delete(notice)
    return {"message": "删除成功"}


@admin_router.patch("/notices/{notice_id}/status")
async def admin_patch_notice_status(
    notice_id: int,
    data: NoticePatchStatus,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HomeNotice).where(HomeNotice.id == notice_id))
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(status_code=404, detail="公告不存在")
    notice.is_enabled = data.is_enabled
    notice.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(notice)
    return NoticeResponse.model_validate(notice)
