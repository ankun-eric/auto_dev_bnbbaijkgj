"""[守护人体系 PRD v1.1 2026-05-25 → 健康档案优化 PRD v1.0 2026-05-26 §3.7 收敛]

历史 C 端接口（list / i-guard / transfer / invitations/records / alert-quota / priority /
alert/simulate-serial-call）已全部下线，由 v1.2 接口 `/api/guardian/v12/*` 接管。
本文件仅保留：
- 后台管理接口 `/api/admin/guardian/relations`（admin-web 运营/客服/风控仍在使用）
- 服务于该 admin 接口的工具函数
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import FamilyManagement, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["守护人体系-后台"])


async def _is_paid_member(db: AsyncSession, user_id: int) -> bool:
    """判断用户是否为付费会员（查询 user_memberships 表，若不存在视为免费）。"""
    try:
        from sqlalchemy import text
        res = await db.execute(text(
            "SELECT 1 FROM user_memberships "
            "WHERE user_id=:uid AND status='active' "
            "  AND (expires_at IS NULL OR expires_at > NOW()) LIMIT 1"
        ).bindparams(uid=user_id))
        return res.scalar() is not None
    except Exception as e:
        logger.warning("[Guardian-Admin] check paid member fail, fallback free: %s", e)
        return False


@router.get("/api/admin/guardian/relations", response_model=dict)
async def admin_list_guardian_relations(
    keyword: Optional[str] = Query(None, description="手机号/昵称模糊匹配"),
    is_primary: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-GUARDIAN-V1 / 健康档案优化 v1.0 §3.7 保留] 后台守护关系查询（运营/客服/风控用）"""
    if str(current_user.role) not in ("admin", "UserRole.admin"):
        if getattr(current_user, "role", None) and getattr(current_user.role, "value", None) != "admin":
            raise HTTPException(status_code=403, detail="仅管理员可访问")

    q = select(FamilyManagement).where(FamilyManagement.status == "active")
    if is_primary is not None:
        q = q.where(FamilyManagement.is_primary_guardian == is_primary)
    q = q.order_by(FamilyManagement.created_at.desc())

    total_q = select(func.count(FamilyManagement.id)).where(FamilyManagement.status == "active")
    if is_primary is not None:
        total_q = total_q.where(FamilyManagement.is_primary_guardian == is_primary)
    total = (await db.execute(total_q)).scalar() or 0

    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = []
    for mgmt in rows:
        manager = (await db.execute(select(User).where(User.id == mgmt.manager_user_id))).scalar_one_or_none()
        managed = (await db.execute(select(User).where(User.id == mgmt.managed_user_id))).scalar_one_or_none()
        if keyword:
            k = keyword.strip()
            if not any(k in (v or "") for v in [
                manager.nickname if manager else "",
                manager.phone if manager else "",
                managed.nickname if managed else "",
                managed.phone if managed else "",
            ]):
                continue
        items.append({
            "id": mgmt.id,
            "manager_user_id": mgmt.manager_user_id,
            "manager_nickname": manager.nickname if manager else None,
            "manager_phone": manager.phone if manager else None,
            "managed_user_id": mgmt.managed_user_id,
            "managed_nickname": managed.nickname if managed else None,
            "managed_phone": managed.phone if managed else None,
            "is_primary_guardian": bool(getattr(mgmt, "is_primary_guardian", False)),
            "priority_order": int(getattr(mgmt, "priority_order", 100) or 100),
            "is_paid_manager": await _is_paid_member(db, mgmt.manager_user_id),
            "created_at": mgmt.created_at.isoformat() if mgmt.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
