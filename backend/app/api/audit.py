"""资金安全 - 审核体系（短信验证码 + 审核手机号配置 + 审核分级 + 退回流程）"""
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.models import (
    AuditCode,
    AuditLockout,
    AuditPhone,
    AuditRequest,
    Coupon,
    CouponCodeBatch,
    CouponGrant,
    CouponRedeemCode,
    User,
    UserCoupon,
    UserCouponStatus,
)
from app.schemas.audit import (
    AuditApproveRequest,
    AuditCodeSendRequest,
    AuditCodeVerifyRequest,
    AuditPhoneCreate,
    AuditPhoneResponse,
    AuditPhoneUpdate,
    AuditRequestResponse,
    AuditResubmitRequest,
    AuditReturnRequest,
)
from app.services.sms_service import send_sms

logger = logging.getLogger(__name__)
admin_dep = require_role("admin")

audit_phone_router = APIRouter(prefix="/api/admin/audit/phones", tags=["资金安全-审核手机号"])
audit_router = APIRouter(prefix="/api/admin/audit", tags=["资金安全-审核"])


# ─── 审核手机号配置 ───


@audit_phone_router.get("")
async def list_audit_phones(
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(AuditPhone).order_by(AuditPhone.created_at.desc()))
    items = [AuditPhoneResponse.model_validate(p).model_dump() for p in rs.scalars().all()]
    return {"items": items}


@audit_phone_router.post("")
async def create_audit_phone(
    data: AuditPhoneCreate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if not data.phone:
        raise HTTPException(status_code=400, detail="手机号必填")
    p = AuditPhone(phone=data.phone, note=data.note, enabled=data.enabled)
    db.add(p)
    await db.flush()
    return AuditPhoneResponse.model_validate(p).model_dump()


@audit_phone_router.put("/{phone_id}")
async def update_audit_phone(
    phone_id: int,
    data: AuditPhoneUpdate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(AuditPhone).where(AuditPhone.id == phone_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="手机号不存在")
    for f in ("phone", "note", "enabled"):
        v = getattr(data, f)
        if v is not None:
            setattr(p, f, v)
    return AuditPhoneResponse.model_validate(p).model_dump()


@audit_phone_router.delete("/{phone_id}")
async def delete_audit_phone(
    phone_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(AuditPhone).where(AuditPhone.id == phone_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="手机号不存在")
    await db.delete(p)
    return {"message": "删除成功"}


async def _get_enabled_audit_phones(db: AsyncSession) -> list[str]:
    rs = await db.execute(select(AuditPhone).where(AuditPhone.enabled == True))  # noqa: E712
    return [p.phone for p in rs.scalars().all()]


# ─── 审核分级 ───


def evaluate_risk_level(est_amount: float, est_count: int, biz_type: str, payload: dict) -> tuple[str, str]:
    """根据规则判定风险级别 + 审批模式

    低风险（≤10 元 且 ≤100 张）→ any（任一通过）
    高风险（>50 元 或 >1000 张 或 兑换码批量 >500 个 或 全员发放）→ joint（联合）
    中间区间默认按低风险走 any
    """
    is_high = False
    if est_amount > 50 and est_count > 0:
        is_high = True
    if est_count > 1000:
        is_high = True
    if biz_type == "redeem_batch" and (payload.get("total_count") or 0) > 500:
        is_high = True
    if biz_type == "coupon_grant" and payload.get("scope") == "all_users":
        is_high = True

    if est_amount <= 10 and est_count <= 100 and not is_high:
        return "low", "any"
    if is_high:
        return "high", "joint"
    return "low", "any"


# ─── 锁定逻辑（3 次错误锁 10 分钟）───


async def _check_lockout(db: AsyncSession, phone: str) -> Optional[datetime]:
    rs = await db.execute(select(AuditLockout).where(AuditLockout.phone == phone))
    lo = rs.scalar_one_or_none()
    if not lo:
        return None
    if lo.locked_until and lo.locked_until > datetime.utcnow():
        return lo.locked_until
    # 自动解锁
    if lo.locked_until and lo.locked_until <= datetime.utcnow():
        lo.fail_count = 0
        lo.locked_until = None
    return None


async def _record_fail(db: AsyncSession, phone: str) -> int:
    rs = await db.execute(select(AuditLockout).where(AuditLockout.phone == phone))
    lo = rs.scalar_one_or_none()
    now = datetime.utcnow()
    if not lo:
        lo = AuditLockout(phone=phone, fail_count=1, last_fail_at=now)
        db.add(lo)
    else:
        # 5 分钟外的失败重置计数
        if lo.last_fail_at and (now - lo.last_fail_at) > timedelta(minutes=5):
            lo.fail_count = 1
        else:
            lo.fail_count += 1
        lo.last_fail_at = now
        if lo.fail_count >= 3:
            lo.locked_until = now + timedelta(minutes=10)
    await db.flush()
    return lo.fail_count


async def _clear_fail(db: AsyncSession, phone: str) -> None:
    rs = await db.execute(select(AuditLockout).where(AuditLockout.phone == phone))
    lo = rs.scalar_one_or_none()
    if lo:
        lo.fail_count = 0
        lo.locked_until = None


# ─── 审核工单 CRUD ───


async def create_audit_request(
    db: AsyncSession,
    biz_type: str,
    payload: dict,
    summary: str,
    est_amount: float,
    est_count: int,
    requester: User,
) -> AuditRequest:
    risk_level, approval_mode = evaluate_risk_level(est_amount, est_count, biz_type, payload)
    req = AuditRequest(
        biz_type=biz_type,
        risk_level=risk_level,
        status="pending",
        payload=payload,
        summary=summary,
        est_amount=est_amount,
        est_count=est_count,
        approval_mode=approval_mode,
        requester_id=requester.id,
        requester_name=requester.nickname or requester.phone,
        history=[{
            "ts": datetime.utcnow().isoformat(),
            "action": "submit",
            "by": requester.nickname or requester.phone,
        }],
        approvals=[],
    )
    db.add(req)
    await db.flush()
    return req


@audit_router.post("/requests")
async def submit_audit_request(
    biz_type: str = Body(...),
    payload: dict = Body(...),
    summary: str = Body(""),
    est_amount: float = Body(0),
    est_count: int = Body(0),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """通用审核工单提交入口（前端可以用它包裹任意业务）"""
    req = await create_audit_request(db, biz_type, payload, summary, est_amount, est_count, current_user)
    return AuditRequestResponse.model_validate(req).model_dump()


@audit_router.get("/requests")
async def list_audit_requests(
    status: Optional[str] = None,
    biz_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditRequest)
    count_query = select(func.count(AuditRequest.id))
    conds = []
    if status:
        conds.append(AuditRequest.status == status)
    if biz_type:
        conds.append(AuditRequest.biz_type == biz_type)
    if risk_level:
        conds.append(AuditRequest.risk_level == risk_level)
    if conds:
        query = query.where(and_(*conds))
        count_query = count_query.where(and_(*conds))
    total = (await db.execute(count_query)).scalar() or 0
    rs = await db.execute(
        query.order_by(AuditRequest.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = [AuditRequestResponse.model_validate(r).model_dump() for r in rs.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@audit_router.get("/requests/{request_id}")
async def get_audit_request(
    request_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    r = (await db.execute(select(AuditRequest).where(AuditRequest.id == request_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="审核工单不存在")
    return AuditRequestResponse.model_validate(r).model_dump()


# ─── 短信验证码（6 位 / 5 分钟有效 / 错误 3 次锁 10 分钟）───


@audit_router.post("/codes/send")
async def send_audit_code(
    data: AuditCodeSendRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    enabled_phones = await _get_enabled_audit_phones(db)
    if data.phone not in enabled_phones:
        raise HTTPException(status_code=403, detail="该手机号未配置为审核手机号")

    locked_until = await _check_lockout(db, data.phone)
    if locked_until:
        raise HTTPException(status_code=429, detail=f"验证码错误次数过多，已锁定至 {locked_until.strftime('%Y-%m-%d %H:%M:%S')}")

    code = "".join(random.choices("0123456789", k=6))
    expires = datetime.utcnow() + timedelta(minutes=5)
    db.add(AuditCode(phone=data.phone, code=code, request_id=data.request_id, expires_at=expires))

    # 调用腾讯云短信
    try:
        await send_sms(
            phone=data.phone, code=code,
            operator_id=current_user.id, db=db,
        )
        return {"message": "验证码已发送", "expires_in": 300}
    except Exception as e:
        logger.error("审核短信发送失败: %s", e)
        # 测试环境兜底：返回 dev_code 便于联调
        from app.core.config import settings
        if getattr(settings, "DEBUG", False):
            return {"message": "验证码已生成（短信发送失败，dev 模式）", "dev_code": code, "expires_in": 300}
        raise HTTPException(status_code=500, detail=f"短信发送失败: {e}")


async def _verify_code(db: AsyncSession, phone: str, code: str, request_id: Optional[int]) -> bool:
    locked_until = await _check_lockout(db, phone)
    if locked_until:
        raise HTTPException(status_code=429, detail=f"验证码错误次数过多，已锁定至 {locked_until.strftime('%Y-%m-%d %H:%M:%S')}")

    query = select(AuditCode).where(
        AuditCode.phone == phone,
        AuditCode.used == False,  # noqa: E712
        AuditCode.expires_at > datetime.utcnow(),
    )
    if request_id:
        query = query.where(AuditCode.request_id == request_id)
    rs = await db.execute(query.order_by(AuditCode.created_at.desc()).limit(1))
    rec = rs.scalar_one_or_none()
    if not rec or rec.code != code:
        cnt = await _record_fail(db, phone)
        remaining = max(0, 3 - cnt)
        raise HTTPException(status_code=400, detail=f"验证码错误（剩余 {remaining} 次机会）")
    rec.used = True
    await _clear_fail(db, phone)
    return True


@audit_router.post("/codes/verify")
async def verify_audit_code(
    data: AuditCodeVerifyRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    await _verify_code(db, data.phone, data.code, data.request_id)
    return {"message": "验证通过"}


# ─── 审批 / 退回 / 重新提交 ───


async def _execute_audit_payload(db: AsyncSession, req: AuditRequest, approver: User) -> dict:
    """审核通过后回放执行业务"""
    payload = req.payload or {}
    biz = req.biz_type
    result = {}
    if biz == "coupon_grant":
        # 定向发放 / 全员发放
        from app.api.coupons_admin import _calc_expire_at
        coupon_id = payload.get("coupon_id")
        coupon = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
        if not coupon:
            raise HTTPException(status_code=404, detail="优惠券不存在")
        users: list[User] = []
        ids = payload.get("user_ids") or []
        if ids:
            rs = await db.execute(select(User).where(User.id.in_(ids)))
            users.extend(rs.scalars().all())
        phones = payload.get("phones") or []
        if phones:
            rs = await db.execute(select(User).where(User.phone.in_(phones)))
            users.extend(rs.scalars().all())
        if payload.get("scope") == "all_users":
            rs = await db.execute(select(User).limit(50000))
            users.extend(rs.scalars().all())
        seen = set()
        granted = 0
        skipped = 0
        now = datetime.utcnow()
        for u in users:
            if u.id in seen:
                continue
            seen.add(u.id)
            existing = await db.execute(select(UserCoupon).where(
                UserCoupon.user_id == u.id, UserCoupon.coupon_id == coupon_id
            ))
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            uc = UserCoupon(user_id=u.id, coupon_id=coupon_id,
                            expire_at=_calc_expire_at(coupon, now), source="direct")
            db.add(uc)
            await db.flush()
            coupon.claimed_count += 1
            db.add(CouponGrant(
                coupon_id=coupon_id, user_id=u.id, user_phone=u.phone,
                method="direct", status="granted", granted_at=now,
                user_coupon_id=uc.id,
                operator_id=approver.id, operator_name=approver.nickname or approver.phone,
            ))
            granted += 1
        result = {"granted": granted, "skipped": skipped}
    elif biz == "coupon_recall":
        grant_ids = payload.get("grant_ids") or []
        reason = payload.get("reason") or "审核通过"
        rs = await db.execute(select(CouponGrant).where(CouponGrant.id.in_(grant_ids)))
        recalled = 0
        for g in rs.scalars().all():
            if g.status in ("used", "recalled"):
                continue
            g.status = "recalled"
            g.recall_reason = reason
            if g.user_coupon_id:
                uc = (await db.execute(select(UserCoupon).where(UserCoupon.id == g.user_coupon_id))).scalar_one_or_none()
                if uc and uc.status == UserCouponStatus.unused:
                    uc.status = UserCouponStatus.expired
            recalled += 1
        result = {"recalled": recalled}
    elif biz == "redeem_batch":
        # 兑换码批次审核通过 → 调用 admin 接口创建
        from app.api.coupons_admin import _gen_unique_code
        coupon_id = payload.get("coupon_id")
        code_type = payload.get("code_type", "unique")
        total = int(payload.get("total_count") or 0)
        partner_id = payload.get("partner_id")
        coupon = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
        if not coupon:
            raise HTTPException(status_code=404, detail="优惠券不存在")
        batch = CouponCodeBatch(
            coupon_id=coupon_id, code_type=code_type, total_count=total,
            partner_id=partner_id, status="active", created_by=approver.id,
        )
        if code_type == "universal":
            batch.universal_code = payload.get("universal_code") or _gen_unique_code(12)
            batch.per_user_limit = int(payload.get("per_user_limit") or 1)
        db.add(batch)
        await db.flush()
        if code_type == "unique":
            existing_codes: set[str] = set()
            for _ in range(total):
                while True:
                    c = _gen_unique_code(16)
                    if c not in existing_codes:
                        existing_codes.add(c)
                        break
                db.add(CouponRedeemCode(
                    batch_id=batch.id, coupon_id=coupon_id,
                    code=c, status="available", partner_id=partner_id,
                ))
        result = {"batch_id": batch.id, "total": total}
    return result


@audit_router.post("/approve")
async def approve_request(
    data: AuditApproveRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """审批通过（联合模式需要多人）"""
    enabled_phones = await _get_enabled_audit_phones(db)
    if data.phone not in enabled_phones:
        raise HTTPException(status_code=403, detail="该手机号未配置为审核手机号")
    await _verify_code(db, data.phone, data.code, data.request_id)

    req = (await db.execute(select(AuditRequest).where(AuditRequest.id == data.request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="工单不存在")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"工单当前状态为 {req.status}，无法审批")

    approvals = list(req.approvals or [])
    name = current_user.nickname or current_user.phone
    approvals.append({"by": name, "at": datetime.utcnow().isoformat(), "phone": data.phone})
    req.approvals = approvals
    history = list(req.history or [])
    history.append({"ts": datetime.utcnow().isoformat(), "action": "approve", "by": name})

    if req.approval_mode == "joint":
        # 联合模式需要 2 个不同手机号通过
        unique_phones = {a.get("phone") for a in approvals}
        if len(unique_phones) < 2:
            req.history = history
            return {"message": "已记录审批，等待第二位审核人通过", "approvals": approvals}

    # 通过 → 执行业务
    try:
        result = await _execute_audit_payload(db, req, current_user)
    except Exception as e:
        history.append({"ts": datetime.utcnow().isoformat(), "action": "execute_failed", "error": str(e)})
        req.history = history
        raise

    req.status = "approved"
    req.approver_id = current_user.id
    req.approver_name = name
    req.approved_at = datetime.utcnow()
    history.append({"ts": datetime.utcnow().isoformat(), "action": "executed", "result": result})
    req.history = history
    return {"message": "审批通过并已执行", "result": result}


@audit_router.post("/return")
async def return_request(
    data: AuditReturnRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """退回（必填修改说明才能再次提交）"""
    if not data.return_reason or not data.return_reason.strip():
        raise HTTPException(status_code=400, detail="退回原因必填")
    req = (await db.execute(select(AuditRequest).where(AuditRequest.id == data.request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="工单不存在")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="只有待审核工单可退回")
    req.status = "returned"
    req.return_reason = data.return_reason
    name = current_user.nickname or current_user.phone
    history = list(req.history or [])
    history.append({"ts": datetime.utcnow().isoformat(), "action": "return", "by": name, "reason": data.return_reason})
    req.history = history
    return {"message": "已退回"}


@audit_router.post("/resubmit")
async def resubmit_request(
    data: AuditResubmitRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """重新提交（必须填修改说明）"""
    if not data.modify_note or not data.modify_note.strip():
        raise HTTPException(status_code=400, detail="修改说明必填")
    req = (await db.execute(select(AuditRequest).where(AuditRequest.id == data.request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="工单不存在")
    if req.status != "returned":
        raise HTTPException(status_code=400, detail="只有已退回工单可重新提交")
    req.status = "pending"
    req.modify_note = data.modify_note
    if data.payload:
        req.payload = data.payload
    name = current_user.nickname or current_user.phone
    history = list(req.history or [])
    history.append({"ts": datetime.utcnow().isoformat(), "action": "resubmit", "by": name, "note": data.modify_note})
    req.history = history
    return AuditRequestResponse.model_validate(req).model_dump()
