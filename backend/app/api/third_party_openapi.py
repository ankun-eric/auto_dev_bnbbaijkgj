"""第三方合作方 OpenAPI（C+ 模式）

5 个接口：
1. POST /api/openapi/redeem-codes/batch-fetch  批量获取兑换码
2. POST /api/openapi/redeem-codes/mark-sold     回传售出状态
3. GET  /api/openapi/redeem-codes/{code}/status 查询码状态
4. POST /api/openapi/redeem-codes/disable        作废码
5. POST /api/openapi/redeem-codes/redeem-callback 核销结果回调（合作方主动通知）

鉴权：API Key + Secret 签名（HMAC-SHA256）
请求头：
  X-Api-Key: pk_xxx
  X-Timestamp: <unix>
  X-Nonce: <random>
  X-Signature: HMAC-SHA256(secret, "method\n{path}\n{ts}\n{nonce}\n{body}")
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import (
    Coupon,
    CouponCodeBatch,
    CouponGrant,
    CouponRedeemCode,
    Partner,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/openapi", tags=["第三方-OpenAPI"])


async def authenticate_partner(
    request: Request,
    db: AsyncSession,
    x_api_key: Optional[str],
    x_timestamp: Optional[str],
    x_nonce: Optional[str],
    x_signature: Optional[str],
) -> Partner:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="缺少 X-Api-Key")
    if not x_signature:
        raise HTTPException(status_code=401, detail="缺少 X-Signature")
    if not x_timestamp or not x_nonce:
        raise HTTPException(status_code=401, detail="缺少 X-Timestamp 或 X-Nonce")
    try:
        ts = int(x_timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="X-Timestamp 格式错误")
    now = int(datetime.utcnow().timestamp())
    if abs(now - ts) > 300:
        raise HTTPException(status_code=401, detail="X-Timestamp 已过期（超过 5 分钟）")

    rs = await db.execute(select(Partner).where(Partner.api_key == x_api_key))
    partner = rs.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=401, detail="API Key 无效")
    if partner.status != "active":
        raise HTTPException(status_code=403, detail="合作方已禁用")

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8") if body_bytes else ""
    sign_str = f"{request.method}\n{request.url.path}\n{x_timestamp}\n{x_nonce}\n{body_str}"
    expected = hmac.new(
        (partner.api_secret or "").encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, x_signature):
        logger.warning("OpenAPI 签名校验失败 partner=%s", partner.id)
        raise HTTPException(status_code=401, detail="签名校验失败")

    return partner


# ─── 1. 批量获取兑换码 ───


@router.post("/redeem-codes/batch-fetch")
async def batch_fetch_codes(
    request: Request,
    payload: dict = Body(...),
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
    x_nonce: Optional[str] = Header(None, alias="X-Nonce"),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """批量获取该合作方拥有的批次内的可用码

    请求体: {"batch_id": 1, "limit": 100}
    """
    partner = await authenticate_partner(request, db, x_api_key, x_timestamp, x_nonce, x_signature)
    batch_id = payload.get("batch_id")
    limit = min(int(payload.get("limit") or 100), 1000)
    if not batch_id:
        raise HTTPException(status_code=400, detail="batch_id 必填")
    batch = (await db.execute(select(CouponCodeBatch).where(CouponCodeBatch.id == batch_id))).scalar_one_or_none()
    if not batch or batch.partner_id != partner.id:
        raise HTTPException(status_code=404, detail="批次不存在或不属于该合作方")
    rs = await db.execute(
        select(CouponRedeemCode).where(
            CouponRedeemCode.batch_id == batch_id,
            CouponRedeemCode.status == "available",
        ).limit(limit)
    )
    codes = [{"code": c.code, "status": c.status} for c in rs.scalars().all()]
    return {"batch_id": batch_id, "codes": codes, "count": len(codes)}


# ─── 2. 回传售出状态 ───


@router.post("/redeem-codes/mark-sold")
async def mark_sold(
    request: Request,
    payload: dict = Body(...),
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
    x_nonce: Optional[str] = Header(None, alias="X-Nonce"),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """回传售出状态

    请求体: {"items": [{"code": "ABC...", "buyer_phone": "138..."}]}
    """
    partner = await authenticate_partner(request, db, x_api_key, x_timestamp, x_nonce, x_signature)
    items = payload.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="items 不能为空")
    updated = 0
    skipped = 0
    for it in items:
        code = it.get("code")
        if not code:
            continue
        rec = (await db.execute(select(CouponRedeemCode).where(CouponRedeemCode.code == code))).scalar_one_or_none()
        if not rec or rec.partner_id != partner.id:
            skipped += 1
            continue
        if rec.status != "available":
            skipped += 1
            continue
        rec.status = "sold"
        rec.sold_at = datetime.utcnow()
        rec.sold_to_user_phone = it.get("buyer_phone")
        updated += 1
    return {"updated": updated, "skipped": skipped}


# ─── 3. 查询码状态 ───


@router.get("/redeem-codes/{code}/status")
async def query_code_status(
    code: str,
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
    x_nonce: Optional[str] = Header(None, alias="X-Nonce"),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    db: AsyncSession = Depends(get_db),
):
    partner = await authenticate_partner(request, db, x_api_key, x_timestamp, x_nonce, x_signature)
    rec = (await db.execute(select(CouponRedeemCode).where(CouponRedeemCode.code == code))).scalar_one_or_none()
    if not rec or rec.partner_id != partner.id:
        raise HTTPException(status_code=404, detail="码不存在或不属于该合作方")
    return {
        "code": rec.code, "status": rec.status,
        "sold_at": rec.sold_at.isoformat() if rec.sold_at else None,
        "used_at": rec.used_at.isoformat() if rec.used_at else None,
        "buyer_phone": rec.sold_to_user_phone,
    }


# ─── 4. 作废码 ───


@router.post("/redeem-codes/disable")
async def disable_codes(
    request: Request,
    payload: dict = Body(...),
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
    x_nonce: Optional[str] = Header(None, alias="X-Nonce"),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """作废码（仅 available/sold 状态可作废）

    请求体: {"codes": ["ABC...", ...], "reason": "退款"}
    """
    partner = await authenticate_partner(request, db, x_api_key, x_timestamp, x_nonce, x_signature)
    codes = payload.get("codes") or []
    if not codes:
        raise HTTPException(status_code=400, detail="codes 不能为空")
    rs = await db.execute(select(CouponRedeemCode).where(CouponRedeemCode.code.in_(codes)))
    disabled = 0
    skipped = 0
    for rec in rs.scalars().all():
        if rec.partner_id != partner.id:
            skipped += 1
            continue
        if rec.status not in ("available", "sold"):
            skipped += 1
            continue
        rec.status = "disabled"
        disabled += 1
    return {"disabled": disabled, "skipped": skipped}


# ─── 5. 核销结果回调 ───


@router.post("/redeem-codes/redeem-callback")
async def redeem_callback(
    request: Request,
    payload: dict = Body(...),
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
    x_nonce: Optional[str] = Header(None, alias="X-Nonce"),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """合作方主动回传核销结果（用于线下场景）

    请求体: {"code": "ABC...", "used_at": "2026-04-19T12:00:00Z", "user_phone": "138..."}
    """
    partner = await authenticate_partner(request, db, x_api_key, x_timestamp, x_nonce, x_signature)
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code 必填")
    rec = (await db.execute(select(CouponRedeemCode).where(CouponRedeemCode.code == code))).scalar_one_or_none()
    if not rec or rec.partner_id != partner.id:
        raise HTTPException(status_code=404, detail="码不存在或不属于该合作方")
    if rec.status == "used":
        return {"message": "已是核销状态", "code": code}
    if rec.status == "disabled":
        raise HTTPException(status_code=400, detail="码已作废")
    rec.status = "used"
    used_at = payload.get("used_at")
    try:
        rec.used_at = datetime.fromisoformat(used_at.replace("Z", "+00:00")) if used_at else datetime.utcnow()
    except Exception:
        rec.used_at = datetime.utcnow()
    rec.sold_to_user_phone = payload.get("user_phone") or rec.sold_to_user_phone

    # 同步登记一条 grant 记录
    db.add(CouponGrant(
        coupon_id=rec.coupon_id, user_id=None, user_phone=rec.sold_to_user_phone,
        method="redeem_code", status="used", granted_at=datetime.utcnow(),
        used_at=rec.used_at, batch_id=rec.batch_id, redeem_code=rec.code,
    ))
    return {"message": "核销成功", "code": code, "used_at": rec.used_at.isoformat()}
