"""[PRD-FAMILY-GUARDIAN-V1] 家庭体检异常·守护推送 - 用户端 API。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    CheckupReport,
    FamilyAlertLog,
    FamilyManagement,
    FamilyMember,
    User,
    VirtualMemberMigration,
)
from app.services.family_guardian_service import (
    guardians_of,
    list_alert_logs_for_user,
    push_aggregated_alert,
)
from app.utils.alert_sig import verify_alert_redirect

router = APIRouter(tags=["家庭体检异常守护推送"])

_alert_logger = logging.getLogger("alert_redirect")


class CheckupParsedPayload(BaseModel):
    report_id: Optional[int] = None
    member_id: int
    abnormal_count: int = 0
    severity: str = "warning"
    report_date: Optional[str] = None


@router.post("/api/internal/checkup/parsed")
async def internal_checkup_parsed(
    payload: CheckupParsedPayload,
    db: AsyncSession = Depends(get_db),
):
    """体检报告解析完成回调：触发守护者集合 + 5min 去重 + 聚合推送。

    设计为内部接口，正式部署可通过 nginx 限制访问来源，这里为开发联调方便保留可调用。
    """
    member = (
        await db.execute(select(FamilyMember).where(FamilyMember.id == payload.member_id))
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    report_date = None
    if payload.report_date:
        try:
            report_date = datetime.fromisoformat(payload.report_date).date()
        except Exception:
            try:
                report_date = datetime.strptime(payload.report_date, "%Y-%m-%d").date()
            except Exception:
                report_date = None
    if report_date is None and payload.report_id:
        rep = (
            await db.execute(select(CheckupReport).where(CheckupReport.id == payload.report_id))
        ).scalar_one_or_none()
        if rep is not None:
            report_date = rep.report_date

    result = await push_aggregated_alert(
        db,
        member,
        abnormal_count=payload.abnormal_count,
        report_id=payload.report_id,
        report_date=report_date,
        severity=payload.severity,
    )
    return result


@router.get("/api/family/guardians/{member_id}")
async def get_guardians(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询某家庭档案的守护者集合（用户可查询自己或自己档案下的成员）。"""
    member = (
        await db.execute(select(FamilyMember).where(FamilyMember.id == member_id))
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")
    # 权限：建档人 / 被守护者本人 / 双向共管的另一方均可查询
    allowed = {member.user_id, member.member_user_id}
    if current_user.id not in allowed:
        # 检查是否有共管关系
        fm = (
            await db.execute(
                select(FamilyManagement).where(
                    (
                        (FamilyManagement.managed_member_id == member_id)
                        & (FamilyManagement.manager_user_id == current_user.id)
                    )
                    | (
                        (FamilyManagement.managed_member_id == member_id)
                        & (FamilyManagement.managed_user_id == current_user.id)
                    ),
                    FamilyManagement.status == "active",
                )
            )
        ).scalar_one_or_none()
        if fm is None:
            raise HTTPException(status_code=403, detail="无权查询该档案的守护者")

    guardians = await guardians_of(db, member)
    # 返回守护者基本信息
    items = []
    if guardians:
        rows = await db.execute(select(User).where(User.id.in_(guardians)))
        for u in rows.scalars():
            items.append({
                "user_id": u.id,
                "nickname": u.nickname,
                "phone": u.phone,
            })
    return {"member_id": member_id, "guardians": items, "count": len(items)}


@router.get("/api/me/alert-logs")
async def my_alert_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """当前用户作为守护者收到的推送列表。"""
    return await list_alert_logs_for_user(db, current_user.id, page=page, page_size=page_size)


@router.get("/api/me/pending-migrations")
async def list_my_pending_migrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """老人首页弹窗：拉取待确认的虚拟档案迁移记录。"""
    rows = await db.execute(
        select(VirtualMemberMigration).where(
            VirtualMemberMigration.target_user_id == current_user.id,
            VirtualMemberMigration.status == "pending",
        )
    )
    items = []
    for m in rows.scalars():
        # 取关联 member 与 creator 信息
        member = (
            await db.execute(select(FamilyMember).where(FamilyMember.id == m.member_id))
        ).scalar_one_or_none()
        creator = (
            await db.execute(select(User).where(User.id == m.creator_user_id))
        ).scalar_one_or_none()
        items.append({
            "id": m.id,
            "member_id": m.member_id,
            "member_nickname": member.nickname if member else None,
            "relationship_type": member.relationship_type if member else None,
            "creator_user_id": m.creator_user_id,
            "creator_nickname": creator.nickname if creator else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return {"items": items, "total": len(items)}


@router.post("/api/me/migrations/{mig_id}/confirm")
async def confirm_migration(
    mig_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """接受迁移：将虚拟档案绑定到当前用户，建立 family_management 守护关系。"""
    m = (
        await db.execute(select(VirtualMemberMigration).where(VirtualMemberMigration.id == mig_id))
    ).scalar_one_or_none()
    if not m or m.target_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="迁移记录不存在")
    if m.status != "pending":
        raise HTTPException(status_code=400, detail="迁移已处理")

    member = (
        await db.execute(select(FamilyMember).where(FamilyMember.id == m.member_id))
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="家庭成员不存在")

    # 绑定 member.member_user_id；清空 virtual_phone
    member.member_user_id = current_user.id
    member.virtual_phone = None

    # 建立守护关系（建档人作为 manager，老人作为 managed）
    existing = (
        await db.execute(
            select(FamilyManagement).where(
                FamilyManagement.manager_user_id == m.creator_user_id,
                FamilyManagement.managed_user_id == current_user.id,
                FamilyManagement.managed_member_id == member.id,
                FamilyManagement.status == "active",
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        mgmt = FamilyManagement(
            manager_user_id=m.creator_user_id,
            managed_user_id=current_user.id,
            managed_member_id=member.id,
            status="active",
        )
        db.add(mgmt)

    m.status = "confirmed"
    m.confirmed_at = datetime.utcnow()
    await db.flush()
    return {"message": "已确认", "member_id": member.id}


@router.post("/api/me/migrations/{mig_id}/reject")
async def reject_migration(
    mig_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """拒绝迁移：保留虚拟档案不动。"""
    m = (
        await db.execute(select(VirtualMemberMigration).where(VirtualMemberMigration.id == mig_id))
    ).scalar_one_or_none()
    if not m or m.target_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="迁移记录不存在")
    if m.status != "pending":
        raise HTTPException(status_code=400, detail="迁移已处理")
    m.status = "rejected"
    m.confirmed_at = datetime.utcnow()
    await db.flush()
    return {"message": "已拒绝"}


class RegisterHookPayload(BaseModel):
    user_id: int
    phone: str


# ============================================================
# [PRD-FAMILY-GUARDIAN-V1] 公众号推送·中转页 alert-redirect 配套接口
# ------------------------------------------------------------
# /api/alert/click-tracking ：点击回执（更新 family_alert_logs.delivery_status='clicked'）
# /api/alert/verify         ：sig 校验工具（前端中转页 SSR / 客户端可调用）
# /api/alert/event          ：埋点事件（曝光、唤起成功、降级、点击各按钮等）
# ============================================================


class AlertClickTrackingPayload(BaseModel):
    """点击回执：仅 logId 必传；sig/t/memberId/reportId 可选（一旦传入则强制校验）。"""

    logId: int
    memberId: Optional[int] = None
    reportId: Optional[int] = None
    t: Optional[int] = None
    sig: Optional[str] = None


@router.post("/api/alert/click-tracking")
async def alert_click_tracking(
    payload: AlertClickTrackingPayload,
    db: AsyncSession = Depends(get_db),
):
    """中转页点击回执：将 family_alert_logs.delivery_status 由 sent/delivered → clicked。

    设计说明：
    - 当且仅当客户端同时提供了 t + sig 时才执行 HMAC 校验；缺失则按宽松模式仅校验 logId
      （这是为了兼容旧版前端落地链接，新链接均带签名）。
    - 仅当当前状态为 sent / delivered 时更新；其余状态（如 clicked / failed）静默忽略以保证幂等。
    - 接口不强制鉴权（公众号点击无 JWT），靠 sig + 状态机防越权。
    """
    log = (
        await db.execute(select(FamilyAlertLog).where(FamilyAlertLog.id == payload.logId))
    ).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="推送日志不存在")

    # sig 校验（如客户端提供）
    if payload.sig is not None or payload.t is not None:
        if payload.sig is None or payload.t is None:
            raise HTTPException(status_code=403, detail="签名缺失")
        if not verify_alert_redirect(
            log_id=payload.logId,
            member_id=payload.memberId if payload.memberId is not None else log.member_id,
            report_id=payload.reportId if payload.reportId is not None else log.report_id,
            t=payload.t,
            sig=payload.sig,
        ):
            raise HTTPException(status_code=403, detail="签名校验失败")

    if log.delivery_status in ("sent", "delivered"):
        log.delivery_status = "clicked"
        log.clicked_at = datetime.utcnow()
        await db.flush()
        return {
            "ok": True,
            "log_id": log.id,
            "status": log.delivery_status,
            "clicked_at": log.clicked_at.isoformat(),
        }

    # 已点击 / 失败 → 幂等返回当前状态
    return {
        "ok": True,
        "log_id": log.id,
        "status": log.delivery_status,
        "clicked_at": log.clicked_at.isoformat() if log.clicked_at else None,
        "idempotent": True,
    }


class AlertVerifyPayload(BaseModel):
    logId: int
    memberId: Optional[int] = None
    reportId: Optional[int] = None
    t: int
    sig: str


@router.post("/api/alert/verify")
async def alert_verify_sig(payload: AlertVerifyPayload):
    """sig 校验：前端中转页可在加载时调用，签名失败时直接展示 403 友好页。"""
    ok = verify_alert_redirect(
        log_id=payload.logId,
        member_id=payload.memberId,
        report_id=payload.reportId,
        t=payload.t,
        sig=payload.sig,
    )
    if not ok:
        raise HTTPException(status_code=403, detail="链接已失效")
    return {"ok": True}


_ALLOWED_ALERT_EVENTS = {
    "alert_redirect_view",
    "alert_redirect_app_launched",
    "alert_redirect_fallback_wechat",
    "alert_redirect_fallback_browser",
    "alert_redirect_click_weapp",
    "alert_redirect_click_download",
    "alert_redirect_click_h5",
}


class AlertEventPayload(BaseModel):
    """埋点事件：与 PRD §7 表格保持一致，未在白名单中的事件返回 400。"""

    event: str
    logId: Optional[int] = None
    memberId: Optional[int] = None
    reportId: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None


@router.post("/api/alert/event")
async def alert_event(payload: AlertEventPayload):
    """埋点事件接收：服务端仅记录 access log（数据量大，不入业务表）。

    生产环境可对接埋点 SDK 或写入 ClickHouse。这里 stdout 落盘即可。
    """
    if payload.event not in _ALLOWED_ALERT_EVENTS:
        raise HTTPException(status_code=400, detail="未知埋点事件")
    _alert_logger.info(
        "[ALERT_EVENT] event=%s logId=%s memberId=%s reportId=%s extra=%s",
        payload.event,
        payload.logId,
        payload.memberId,
        payload.reportId,
        payload.extra,
    )
    return {"ok": True, "event": payload.event}


@router.post("/api/internal/user/registered")
async def internal_user_registered_hook(
    payload: RegisterHookPayload,
    db: AsyncSession = Depends(get_db),
):
    """用户注册成功钩子：扫描 family_members.virtual_phone == phone，写入 pending_migration。"""
    rows = await db.execute(
        select(FamilyMember).where(
            FamilyMember.virtual_phone == payload.phone,
            FamilyMember.status == "active",
        )
    )
    created = 0
    for member in rows.scalars():
        # 跳过：该 member 已绑定其它 user
        if member.member_user_id and member.member_user_id != payload.user_id:
            continue
        # 已有 pending 不重复
        existing = (
            await db.execute(
                select(VirtualMemberMigration).where(
                    VirtualMemberMigration.member_id == member.id,
                    VirtualMemberMigration.target_user_id == payload.user_id,
                    VirtualMemberMigration.status == "pending",
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        mig = VirtualMemberMigration(
            member_id=member.id,
            target_user_id=payload.user_id,
            creator_user_id=member.user_id,
            virtual_phone=payload.phone,
            status="pending",
        )
        db.add(mig)
        created += 1
    await db.flush()
    return {"created": created}
