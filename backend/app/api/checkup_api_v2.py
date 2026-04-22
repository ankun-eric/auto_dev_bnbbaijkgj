"""[2026-04-23] 报告解读 / 对比 对话化 API v2 - 按"接口改造清单"规范化的 Restful 入口。

本文件不重复实现业务逻辑，全部复用 `app.api.report_interpret` 中已有的实现函数。
它只做路径规范化，让外部调用方能按需求清单使用标准 `/api/checkup/*` 路径。

新增路径：
- POST /api/checkup/compare/create-session        创建报告对比会话，校验同咨询人
- GET  /api/checkup/reports/{id}                  极简详情页数据
- PUT  /api/checkup/reports/{id}                  更新报告标题
- POST /api/checkup/reports/{id}/ensure-session   老数据懒加载创建 AI 解读会话（幂等）
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import CheckupReport, FamilyMember, User
from app.api import report_interpret as _ri

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/checkup", tags=["体检报告-v2"])


# ──────────────── Schema ────────────────


class CompareCreateSessionRequest(BaseModel):
    member_id: int
    report_ids: list[int] = Field(..., min_items=2, max_items=2)


class ReportTitleUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)


# ──────────────── 路由 ────────────────


@router.post("/compare/create-session")
async def compare_create_session(
    body: CompareCreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建报告对比会话（Restful 规范化路径）。

    校验两份报告必须属于同一咨询人。内部完全复用 `/api/report/compare/start`
    的实现逻辑。
    """
    return await _ri.compare_start(
        body=_ri.CompareStartRequest(
            member_id=body.member_id,
            report_ids=body.report_ids,
        ),
        current_user=current_user,
        db=db,
    )


@router.get("/reports/{report_id}", response_model=_ri.ReportDetailV2)
async def get_report(
    report_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """极简详情页数据（Restful 规范化路径），复用 interpret_detail。"""
    return await _ri.interpret_detail(
        report_id=report_id,
        current_user=current_user,
        db=db,
    )


@router.put("/reports/{report_id}")
async def update_report_title(
    report_id: int = Path(...),
    body: ReportTitleUpdateRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新报告标题（Restful 规范化路径）。"""
    return await _ri.interpret_update_title(
        report_id=report_id,
        body=_ri.ReportTitleUpdateRequest(title=body.title),
        current_user=current_user,
        db=db,
    )


@router.post("/reports/{report_id}/ensure-session")
async def ensure_session(
    report_id: int = Path(...),
    member_id: Optional[int] = Body(default=None, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """老数据懒加载创建 AI 解读会话（幂等）。

    - 若报告已绑定会话，直接返回该 session_id
    - 若未绑定，按 `/api/report/interpret/start` 的逻辑新建会话并绑定
    - 完全幂等：多次调用同一 report_id 返回相同 session_id
    """
    rep = await db.get(CheckupReport, report_id)
    if not rep or rep.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="报告不存在")

    # 已绑定 → 直接返回
    existing_sid = getattr(rep, "interpret_session_id", None)
    if existing_sid:
        return {
            "session_id": existing_sid,
            "redirect_url": f"/checkup/chat/{existing_sid}?auto_start=1&type=report_interpret",
            "report_id": rep.id,
            "created": False,
        }

    # 走 interpret_start 新建
    effective_member_id = member_id or rep.family_member_id
    if effective_member_id:
        fm = await db.get(FamilyMember, effective_member_id)
        if not fm or fm.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="咨询人不存在或无权限")

    resp = await _ri.interpret_start(
        body=_ri.InterpretStartRequest(
            report_id=rep.id,
            member_id=effective_member_id,
        ),
        current_user=current_user,
        db=db,
    )
    return {
        "session_id": resp.session_id,
        "redirect_url": resp.redirect_url,
        "report_id": rep.id,
        "created": True,
    }
