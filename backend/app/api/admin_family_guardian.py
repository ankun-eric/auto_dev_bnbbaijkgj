"""[PRD-FAMILY-GUARDIAN-V1] 管理后台 - 文案模板 / 阈值配置 / 推送记录 CRUD 与导出。"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    AbnormalThreshold,
    AlertMessageTemplate,
    FamilyAlertLog,
    FamilyMember,
    User,
    UserRole,
)

router = APIRouter(tags=["管理后台-家庭体检异常守护推送"])


def _ensure_admin(user: User):
    role = getattr(user, "role", None)
    role_v = getattr(role, "value", role)
    if role_v not in ("admin",) and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="仅管理员可访问")


# ───── 文案模板 ─────


class TemplatePayload(BaseModel):
    code: str
    channel: str
    scene: str
    title: str
    content: str
    is_active: bool = True


@router.get("/api/admin/alert-templates")
async def admin_list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_admin(current_user)
    total_q = await db.execute(select(func.count(AlertMessageTemplate.id)))
    total = total_q.scalar() or 0
    rows = await db.execute(
        select(AlertMessageTemplate)
        .order_by(AlertMessageTemplate.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        {
            "id": t.id,
            "code": t.code,
            "channel": t.channel,
            "scene": t.scene,
            "title": t.title,
            "content": t.content,
            "is_active": bool(t.is_active),
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in rows.scalars()
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/api/admin/alert-templates")
async def admin_create_template(
    payload: TemplatePayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_admin(current_user)
    exists = (
        await db.execute(select(AlertMessageTemplate).where(AlertMessageTemplate.code == payload.code))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="模板编码已存在")
    t = AlertMessageTemplate(**payload.model_dump())
    db.add(t)
    await db.flush()
    return {"id": t.id}


@router.put("/api/admin/alert-templates/{tid}")
async def admin_update_template(
    tid: int,
    payload: TemplatePayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_admin(current_user)
    t = (
        await db.execute(select(AlertMessageTemplate).where(AlertMessageTemplate.id == tid))
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    for k, v in payload.model_dump().items():
        setattr(t, k, v)
    t.updated_at = datetime.now()
    await db.flush()
    return {"message": "ok"}


@router.delete("/api/admin/alert-templates/{tid}")
async def admin_delete_template(
    tid: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_admin(current_user)
    t = (
        await db.execute(select(AlertMessageTemplate).where(AlertMessageTemplate.id == tid))
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    await db.delete(t)
    await db.flush()
    return {"message": "ok"}


# ───── 阈值配置 ─────


class ThresholdPayload(BaseModel):
    metric_code: str
    metric_name: str
    severity: str = "warning"
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    unit: Optional[str] = None
    gender: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    is_active: bool = True


@router.get("/api/admin/abnormal-thresholds")
async def admin_list_thresholds(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    keyword: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_admin(current_user)
    q = select(AbnormalThreshold)
    cq = select(func.count(AbnormalThreshold.id))
    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            (AbnormalThreshold.metric_code.like(like))
            | (AbnormalThreshold.metric_name.like(like))
        )
        cq = cq.where(
            (AbnormalThreshold.metric_code.like(like))
            | (AbnormalThreshold.metric_name.like(like))
        )
    total = (await db.execute(cq)).scalar() or 0
    rows = await db.execute(
        q.order_by(AbnormalThreshold.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        {
            "id": x.id,
            "metric_code": x.metric_code,
            "metric_name": x.metric_name,
            "severity": x.severity,
            "lower_bound": float(x.lower_bound) if x.lower_bound is not None else None,
            "upper_bound": float(x.upper_bound) if x.upper_bound is not None else None,
            "unit": x.unit,
            "is_active": bool(x.is_active),
        }
        for x in rows.scalars()
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/api/admin/abnormal-thresholds")
async def admin_create_threshold(
    payload: ThresholdPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_admin(current_user)
    t = AbnormalThreshold(**payload.model_dump())
    db.add(t)
    await db.flush()
    return {"id": t.id}


@router.put("/api/admin/abnormal-thresholds/{tid}")
async def admin_update_threshold(
    tid: int,
    payload: ThresholdPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_admin(current_user)
    t = (
        await db.execute(select(AbnormalThreshold).where(AbnormalThreshold.id == tid))
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="阈值不存在")
    for k, v in payload.model_dump().items():
        setattr(t, k, v)
    t.updated_at = datetime.now()
    await db.flush()
    return {"message": "ok"}


@router.delete("/api/admin/abnormal-thresholds/{tid}")
async def admin_delete_threshold(
    tid: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_admin(current_user)
    t = (
        await db.execute(select(AbnormalThreshold).where(AbnormalThreshold.id == tid))
    ).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="阈值不存在")
    await db.delete(t)
    await db.flush()
    return {"message": "ok"}


# ───── 推送记录查询 + 导出 ─────


def _build_logs_query(
    start_at: Optional[datetime],
    end_at: Optional[datetime],
    channel: Optional[str],
    status: Optional[str],
    clicked: Optional[bool],
    guardian_keyword: Optional[str],
    member_keyword: Optional[str],
):
    q = select(FamilyAlertLog)
    cq = select(func.count(FamilyAlertLog.id))
    conds = []
    if start_at:
        conds.append(FamilyAlertLog.pushed_at >= start_at)
    if end_at:
        conds.append(FamilyAlertLog.pushed_at < end_at)
    if channel:
        conds.append(FamilyAlertLog.channel == channel)
    if status:
        conds.append(FamilyAlertLog.delivery_status == status)
    if clicked is True:
        conds.append(FamilyAlertLog.clicked_at.is_not(None))
    elif clicked is False:
        conds.append(FamilyAlertLog.clicked_at.is_(None))
    if conds:
        for c in conds:
            q = q.where(c)
            cq = cq.where(c)
    return q, cq


@router.get("/api/admin/alert-logs")
async def admin_list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    start_at: Optional[str] = Query(None),
    end_at: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    clicked: Optional[bool] = Query(None),
    guardian_keyword: Optional[str] = Query(None, description="守护者手机号/姓名搜索"),
    member_keyword: Optional[str] = Query(None, description="被守护者手机号/姓名搜索"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_admin(current_user)
    # 默认近 7 天
    start_dt = None
    end_dt = None
    if start_at:
        try:
            start_dt = datetime.fromisoformat(start_at)
        except Exception:
            start_dt = None
    if end_at:
        try:
            end_dt = datetime.fromisoformat(end_at)
        except Exception:
            end_dt = None
    if start_dt is None and end_dt is None:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)

    q, cq = _build_logs_query(start_dt, end_dt, channel, status, clicked, guardian_keyword, member_keyword)

    total = (await db.execute(cq)).scalar() or 0
    rows = await db.execute(
        q.order_by(FamilyAlertLog.pushed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for log in rows.scalars():
        # 守护者 / 被守护者基本信息
        guardian = (
            await db.execute(select(User).where(User.id == log.guardian_user_id))
        ).scalar_one_or_none()
        member = (
            await db.execute(select(FamilyMember).where(FamilyMember.id == log.member_id))
        ).scalar_one_or_none()
        item = {
            "id": log.id,
            "guardian_user_id": log.guardian_user_id,
            "guardian_nickname": guardian.nickname if guardian else None,
            "guardian_phone": guardian.phone if guardian else None,
            "member_id": log.member_id,
            "member_nickname": member.nickname if member else None,
            "report_id": log.report_id,
            "severity": log.severity,
            "abnormal_count": log.abnormal_count,
            "template_code": log.template_code,
            "channel": log.channel,
            "delivery_status": log.delivery_status,
            "error_msg": log.error_msg,
            "pushed_at": log.pushed_at.isoformat() if log.pushed_at else None,
            "clicked_at": log.clicked_at.isoformat() if log.clicked_at else None,
        }
        # 关键字筛选（内存层，简化实现）
        if guardian_keyword:
            kw = guardian_keyword
            if not (
                (item["guardian_nickname"] and kw in item["guardian_nickname"])
                or (item["guardian_phone"] and kw in item["guardian_phone"])
            ):
                continue
        if member_keyword:
            kw = member_keyword
            if not (item["member_nickname"] and kw in item["member_nickname"]):
                continue
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/api/admin/alert-logs/export")
async def admin_export_logs(
    start_at: Optional[str] = Query(None),
    end_at: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    clicked: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出 CSV（Excel 可直接打开）。最多 1 万条。"""
    _ensure_admin(current_user)
    start_dt = None
    end_dt = None
    if start_at:
        try:
            start_dt = datetime.fromisoformat(start_at)
        except Exception:
            start_dt = None
    if end_at:
        try:
            end_dt = datetime.fromisoformat(end_at)
        except Exception:
            end_dt = None
    if start_dt is None and end_dt is None:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)

    q, _ = _build_logs_query(start_dt, end_dt, channel, status, clicked, None, None)
    rows = await db.execute(q.order_by(FamilyAlertLog.pushed_at.desc()).limit(10000))

    buf = io.StringIO()
    buf.write("\ufeff")  # BOM for Excel
    writer = csv.writer(buf)
    writer.writerow([
        "推送时间", "守护者ID", "守护者昵称", "守护者手机号",
        "被守护者档案ID", "被守护者昵称", "报告ID", "严重程度",
        "异常项数", "通道", "状态", "是否点击", "错误信息",
    ])
    for log in rows.scalars():
        guardian = (
            await db.execute(select(User).where(User.id == log.guardian_user_id))
        ).scalar_one_or_none()
        member = (
            await db.execute(select(FamilyMember).where(FamilyMember.id == log.member_id))
        ).scalar_one_or_none()
        writer.writerow([
            log.pushed_at.isoformat() if log.pushed_at else "",
            log.guardian_user_id,
            (guardian.nickname if guardian else "") or "",
            (guardian.phone if guardian else "") or "",
            log.member_id,
            (member.nickname if member else "") or "",
            log.report_id or "",
            log.severity,
            log.abnormal_count,
            log.channel,
            log.delivery_status,
            "是" if log.clicked_at else "否",
            log.error_msg or "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=family_alert_logs.csv"},
    )
