"""管理后台 - 优惠券模板管理 + 发放记录 + 4 种发放方式 + 兑换码 + 第三方合作方"""
import csv
import io
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    Coupon,
    CouponCodeBatch,
    CouponGrant,
    CouponRedeemCode,
    Partner,
    SystemConfig,
    User,
    UserCoupon,
    UserCouponStatus,
)
from app.schemas.coupons import (
    CouponCreate,
    CouponResponse,
    CouponUpdate,
    DirectGrantRequest,
    GrantRecallRequest,
    PartnerCreate,
    PartnerResponse,
    PartnerUpdate,
    RedeemCodeBatchCreate,
    VALIDITY_DAYS_OPTIONS,
)

admin_dep = require_role("admin")

router = APIRouter(prefix="/api/admin/coupons", tags=["管理后台-优惠券"])
partner_router = APIRouter(prefix="/api/admin/partners", tags=["管理后台-合作方"])
new_user_router = APIRouter(prefix="/api/admin/new-user-coupons", tags=["管理后台-新人券"])


def _calc_expire_at(coupon: Coupon, base: Optional[datetime] = None) -> datetime:
    base = base or datetime.utcnow()
    days = coupon.validity_days or 30
    return base + timedelta(days=days)


def _coupon_to_dict(c: Coupon) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "type": c.type.value if hasattr(c.type, "value") else str(c.type),
        "condition_amount": float(c.condition_amount or 0),
        "discount_value": float(c.discount_value or 0),
        "discount_rate": float(c.discount_rate or 1.0),
        "scope": c.scope.value if hasattr(c.scope, "value") else str(c.scope),
        "scope_ids": c.scope_ids,
        "total_count": c.total_count or 0,
        "claimed_count": c.claimed_count or 0,
        "used_count": c.used_count or 0,
        "validity_days": c.validity_days or 30,
        "status": c.status.value if hasattr(c.status, "value") else str(c.status),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ─── 优惠券模板 CRUD ───


@router.get("")
async def list_coupons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(Coupon)
    count_query = select(func.count(Coupon.id))
    if status:
        query = query.where(Coupon.status == status)
        count_query = count_query.where(Coupon.status == status)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(Coupon.name.like(like))
        count_query = count_query.where(Coupon.name.like(like))

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Coupon.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = [_coupon_to_dict(c) for c in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/validity-options")
async def get_validity_options(_: User = Depends(admin_dep)):
    """有效期 8 档下拉选项"""
    return {"options": VALIDITY_DAYS_OPTIONS}


@router.post("")
async def create_coupon(
    data: CouponCreate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if data.validity_days not in VALIDITY_DAYS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"有效期天数必须为 {VALIDITY_DAYS_OPTIONS} 之一")
    c = Coupon(
        name=data.name,
        type=data.type,
        condition_amount=data.condition_amount,
        discount_value=data.discount_value,
        discount_rate=data.discount_rate,
        scope=data.scope,
        scope_ids=data.scope_ids,
        total_count=data.total_count,
        validity_days=data.validity_days,
        status=data.status,
    )
    db.add(c)
    await db.flush()
    return _coupon_to_dict(c)


@router.put("/{coupon_id}")
async def update_coupon(
    coupon_id: int,
    data: CouponUpdate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    if data.validity_days is not None and data.validity_days not in VALIDITY_DAYS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"有效期天数必须为 {VALIDITY_DAYS_OPTIONS} 之一")
    for f in ("name", "type", "condition_amount", "discount_value", "discount_rate",
              "scope", "scope_ids", "total_count", "validity_days", "status"):
        v = getattr(data, f)
        if v is not None:
            setattr(c, f, v)
    return _coupon_to_dict(c)


@router.delete("/{coupon_id}")
async def delete_coupon(
    coupon_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    await db.delete(c)
    return {"message": "删除成功"}


# ─── 发放记录 ───


@router.get("/{coupon_id}/grants")
async def list_coupon_grants(
    coupon_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    phone: Optional[str] = None,
    status: Optional[str] = None,
    method: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """4 维筛选：手机号 / 状态 / 时间 / 方式"""
    query = select(CouponGrant).where(CouponGrant.coupon_id == coupon_id)
    count_query = select(func.count(CouponGrant.id)).where(CouponGrant.coupon_id == coupon_id)
    conds = []
    if phone:
        conds.append(CouponGrant.user_phone.like(f"%{phone}%"))
    if status:
        conds.append(CouponGrant.status == status)
    if method:
        conds.append(CouponGrant.method == method)
    if start:
        conds.append(CouponGrant.granted_at >= start)
    if end:
        conds.append(CouponGrant.granted_at <= end)
    if conds:
        query = query.where(and_(*conds))
        count_query = count_query.where(and_(*conds))

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(CouponGrant.granted_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = []
    for g in result.scalars().all():
        items.append({
            "id": g.id,
            "coupon_id": g.coupon_id,
            "user_id": g.user_id,
            "user_phone": g.user_phone,
            "method": g.method,
            "status": g.status,
            "granted_at": g.granted_at.isoformat() if g.granted_at else None,
            "used_at": g.used_at.isoformat() if g.used_at else None,
            "order_no": g.order_no,
            "operator_name": g.operator_name,
            "redeem_code": g.redeem_code,
            "recall_reason": g.recall_reason,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{coupon_id}/grants/export")
async def export_coupon_grants(
    coupon_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """导出发放记录为 CSV（Excel 兼容）"""
    result = await db.execute(
        select(CouponGrant).where(CouponGrant.coupon_id == coupon_id)
        .order_by(CouponGrant.granted_at.desc()).limit(10000)
    )
    grants = result.scalars().all()

    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM for Excel
    writer = csv.writer(buf)
    writer.writerow(["发放ID", "用户ID", "手机号", "发放时间", "发放方式", "状态",
                     "使用时间", "订单号", "操作人", "兑换码", "回收原因"])
    for g in grants:
        writer.writerow([
            g.id, g.user_id or "", g.user_phone or "",
            g.granted_at.strftime("%Y-%m-%d %H:%M:%S") if g.granted_at else "",
            g.method, g.status,
            g.used_at.strftime("%Y-%m-%d %H:%M:%S") if g.used_at else "",
            g.order_no or "", g.operator_name or "",
            g.redeem_code or "", g.recall_reason or "",
        ])
    buf.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=coupon_grants_{coupon_id}.csv"}
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


@router.post("/grants/recall")
async def recall_grants(
    data: GrantRecallRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """单/批量回收（必填原因）"""
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="回收原因必填")
    result = await db.execute(select(CouponGrant).where(CouponGrant.id.in_(data.grant_ids)))
    grants = result.scalars().all()
    if not grants:
        raise HTTPException(status_code=404, detail="未找到对应发放记录")

    recalled = 0
    for g in grants:
        if g.status in ("used", "recalled"):
            continue
        g.status = "recalled"
        g.recall_reason = data.reason
        # 同步将 user_coupon 标为过期
        if g.user_coupon_id:
            uc = (await db.execute(select(UserCoupon).where(UserCoupon.id == g.user_coupon_id))).scalar_one_or_none()
            if uc and uc.status == UserCouponStatus.unused:
                uc.status = UserCouponStatus.expired
        recalled += 1
    return {"message": f"成功回收 {recalled} 条", "recalled": recalled}


# ─── 4 种发放方式 ───


@router.post("/{coupon_id}/grant/direct")
async def grant_direct(
    coupon_id: int,
    data: DirectGrantRequest,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """B 定向发放：根据 user_ids / phones / 标签筛选"""
    coupon = (await db.execute(select(Coupon).where(Coupon.id == coupon_id))).scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    # 收集目标用户
    users: list[User] = []
    if data.user_ids:
        rs = await db.execute(select(User).where(User.id.in_(data.user_ids)))
        users.extend(rs.scalars().all())
    if data.phones:
        rs = await db.execute(select(User).where(User.phone.in_(data.phones)))
        users.extend(rs.scalars().all())
    if data.filter_tags:
        # 标签维度：用户等级 + 注册时长 + 消费行为
        tag_query = select(User)
        conds = []
        lvl = data.filter_tags.get("member_level")
        if lvl is not None:
            conds.append(User.member_level == int(lvl))
        reg_days = data.filter_tags.get("registered_within_days")
        if reg_days:
            since = datetime.utcnow() - timedelta(days=int(reg_days))
            conds.append(User.created_at >= since)
        if conds:
            tag_query = tag_query.where(and_(*conds))
            rs = await db.execute(tag_query.limit(5000))
            users.extend(rs.scalars().all())

    if not users:
        raise HTTPException(status_code=400, detail="没有匹配到任何用户")

    # 去重
    seen = set()
    uniq_users: list[User] = []
    for u in users:
        if u.id in seen:
            continue
        seen.add(u.id)
        uniq_users.append(u)

    granted = 0
    skipped = 0
    now = datetime.utcnow()
    for u in uniq_users:
        # 限领规则：每人每券 1 张
        existing = await db.execute(
            select(UserCoupon).where(
                UserCoupon.user_id == u.id, UserCoupon.coupon_id == coupon_id
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue
        uc = UserCoupon(
            user_id=u.id, coupon_id=coupon_id,
            expire_at=_calc_expire_at(coupon, now),
            source="direct",
        )
        db.add(uc)
        await db.flush()
        coupon.claimed_count += 1
        db.add(CouponGrant(
            coupon_id=coupon_id, user_id=u.id, user_phone=u.phone,
            method="direct", status="granted", granted_at=now,
            user_coupon_id=uc.id,
            operator_id=current_user.id, operator_name=current_user.nickname or current_user.phone,
        ))
        granted += 1

    return {"message": f"成功发放 {granted} 张，跳过 {skipped} 个已领用户", "granted": granted, "skipped": skipped}


# ─── D 新人券规则 ───


NEW_USER_COUPON_KEY = "new_user_coupon_ids"


@new_user_router.get("")
async def get_new_user_coupons(
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(SystemConfig).where(SystemConfig.config_key == NEW_USER_COUPON_KEY))).scalar_one_or_none()
    ids: list[int] = []
    if cfg and cfg.config_value:
        try:
            import json as _json
            ids = _json.loads(cfg.config_value)
        except Exception:
            ids = []
    coupons = []
    if ids:
        rs = await db.execute(select(Coupon).where(Coupon.id.in_(ids)))
        coupons = [_coupon_to_dict(c) for c in rs.scalars().all()]
    return {"coupon_ids": ids, "coupons": coupons}


class NewUserCouponSet(BaseModel):
    coupon_ids: list[int]


@new_user_router.put("")
async def set_new_user_coupons(
    data: NewUserCouponSet,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    import json as _json
    cfg = (await db.execute(select(SystemConfig).where(SystemConfig.config_key == NEW_USER_COUPON_KEY))).scalar_one_or_none()
    val = _json.dumps(data.coupon_ids)
    if cfg:
        cfg.config_value = val
    else:
        db.add(SystemConfig(config_key=NEW_USER_COUPON_KEY, config_value=val, config_type="coupon"))
    return {"coupon_ids": data.coupon_ids}


# ─── F 兑换码批次 ───


def _gen_unique_code(length: int = 16) -> str:
    alphabet = string.ascii_uppercase + string.digits
    # 排除易混淆字符 0/O/1/I
    alphabet = alphabet.translate(str.maketrans("", "", "0O1I"))
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/redeem-code-batches")
async def create_redeem_batch(
    data: RedeemCodeBatchCreate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    coupon = (await db.execute(select(Coupon).where(Coupon.id == data.coupon_id))).scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    if data.code_type not in ("universal", "unique"):
        raise HTTPException(status_code=400, detail="code_type 仅支持 universal / unique")

    universal_code = data.universal_code
    if data.code_type == "universal":
        if not universal_code:
            universal_code = _gen_unique_code(12)
    else:
        if not data.total_count or data.total_count <= 0:
            raise HTTPException(status_code=400, detail="一次性唯一码必须指定 total_count")
        if data.total_count > 100000:
            raise HTTPException(status_code=400, detail="单批最多 100000 个")

    batch = CouponCodeBatch(
        coupon_id=data.coupon_id,
        code_type=data.code_type,
        name=data.name,
        total_count=data.total_count or 0,
        universal_code=universal_code if data.code_type == "universal" else None,
        per_user_limit=data.per_user_limit if data.code_type == "universal" else 1,
        partner_id=data.partner_id,
        status="active",
        created_by=current_user.id,
    )
    db.add(batch)
    await db.flush()

    # unique 模式批量生成
    if data.code_type == "unique":
        existing_codes: set[str] = set()
        codes_to_add = []
        target = data.total_count
        while len(codes_to_add) < target:
            c = _gen_unique_code(16)
            if c in existing_codes:
                continue
            existing_codes.add(c)
            codes_to_add.append(c)
        # 检查数据库已存在的码
        rs = await db.execute(select(CouponRedeemCode.code).where(CouponRedeemCode.code.in_(list(existing_codes))))
        dup_in_db = {r[0] for r in rs.all()}
        codes_to_add = [c for c in codes_to_add if c not in dup_in_db]
        for c in codes_to_add:
            db.add(CouponRedeemCode(
                batch_id=batch.id, coupon_id=data.coupon_id,
                code=c, status="available",
                partner_id=data.partner_id,
            ))
    return {
        "id": batch.id,
        "code_type": batch.code_type,
        "universal_code": batch.universal_code,
        "total_count": batch.total_count,
        "partner_id": batch.partner_id,
    }


@router.get("/redeem-code-batches")
async def list_redeem_batches(
    coupon_id: Optional[int] = None,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(CouponCodeBatch)
    if coupon_id:
        query = query.where(CouponCodeBatch.coupon_id == coupon_id)
    rs = await db.execute(query.order_by(CouponCodeBatch.created_at.desc()).limit(500))
    items = []
    for b in rs.scalars().all():
        items.append({
            "id": b.id, "coupon_id": b.coupon_id, "code_type": b.code_type, "name": b.name,
            "total_count": b.total_count, "used_count": b.used_count,
            "universal_code": b.universal_code, "per_user_limit": b.per_user_limit,
            "partner_id": b.partner_id, "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items}


@router.get("/redeem-code-batches/{batch_id}/codes/export")
async def export_batch_codes(
    batch_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """导出批次内所有码为 CSV"""
    rs = await db.execute(select(CouponRedeemCode).where(CouponRedeemCode.batch_id == batch_id).limit(200000))
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(["code", "status", "sold_at", "used_at"])
    for c in rs.scalars().all():
        writer.writerow([
            c.code, c.status,
            c.sold_at.strftime("%Y-%m-%d %H:%M:%S") if c.sold_at else "",
            c.used_at.strftime("%Y-%m-%d %H:%M:%S") if c.used_at else "",
        ])
    buf.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=batch_{batch_id}_codes.csv"}
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


# ─── 第三方合作方管理 ───


def _gen_api_key() -> str:
    return "pk_" + secrets.token_urlsafe(24)


def _gen_api_secret() -> str:
    return secrets.token_urlsafe(32)


@partner_router.get("")
async def list_partners(
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    rs = await db.execute(select(Partner).order_by(Partner.created_at.desc()).limit(500))
    items = [PartnerResponse.model_validate(p).model_dump() for p in rs.scalars().all()]
    return {"items": items}


@partner_router.post("")
async def create_partner(
    data: PartnerCreate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = Partner(
        name=data.name, contact_name=data.contact_name, contact_phone=data.contact_phone,
        mode=data.mode, notes=data.notes, status="active",
        api_key=_gen_api_key(), api_secret=_gen_api_secret(),
    )
    db.add(p)
    await db.flush()
    return PartnerResponse.model_validate(p).model_dump()


@partner_router.put("/{partner_id}")
async def update_partner(
    partner_id: int,
    data: PartnerUpdate,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(Partner).where(Partner.id == partner_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="合作方不存在")
    for f in ("name", "contact_name", "contact_phone", "mode", "status", "notes"):
        v = getattr(data, f)
        if v is not None:
            setattr(p, f, v)
    return PartnerResponse.model_validate(p).model_dump()


@partner_router.post("/{partner_id}/regenerate-key")
async def regenerate_partner_key(
    partner_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(Partner).where(Partner.id == partner_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="合作方不存在")
    p.api_key = _gen_api_key()
    p.api_secret = _gen_api_secret()
    return {"api_key": p.api_key, "api_secret": p.api_secret}


@partner_router.delete("/{partner_id}")
async def delete_partner(
    partner_id: int,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(Partner).where(Partner.id == partner_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="合作方不存在")
    await db.delete(p)
    return {"message": "删除成功"}


@partner_router.get("/{partner_id}/reconciliation")
async def partner_reconciliation(
    partner_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    current_user: User = Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """合作方对账数据：批次发放/售出/核销统计"""
    batches = (await db.execute(select(CouponCodeBatch).where(CouponCodeBatch.partner_id == partner_id))).scalars().all()
    batch_ids = [b.id for b in batches]
    total_codes = 0
    sold = 0
    used = 0
    if batch_ids:
        total_codes = (await db.execute(select(func.count(CouponRedeemCode.id)).where(CouponRedeemCode.batch_id.in_(batch_ids)))).scalar() or 0
        sold = (await db.execute(select(func.count(CouponRedeemCode.id)).where(
            CouponRedeemCode.batch_id.in_(batch_ids), CouponRedeemCode.status.in_(("sold", "used"))
        ))).scalar() or 0
        used = (await db.execute(select(func.count(CouponRedeemCode.id)).where(
            CouponRedeemCode.batch_id.in_(batch_ids), CouponRedeemCode.status == "used"
        ))).scalar() or 0
    return {
        "partner_id": partner_id,
        "batches": len(batches),
        "total_codes": total_codes,
        "sold": sold,
        "used": used,
        "unsold": total_codes - sold,
    }
