"""积分兑换记录 v3 API（优惠券 + 体验服务 + 实物兑换记录合并展示）.

设计：
- 券（coupon）与体验服务（service）→ `point_exchange_records` 表
- 实物（physical）→ `orders` 订单系统（`order_type=points_exchange, payment_method=points`）
- 兑换记录查询接口做合并（两表 union，按时间倒序）
"""
from __future__ import annotations

import random
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Coupon,
    CouponStatus,
    PointExchangeRecord,
    PointsMallItem,
    PointsMallItemType,
    PointsRecord,
    PointsType,
    User,
    UserCoupon,
    UserCouponStatus,
)

router = APIRouter(prefix="/api/points", tags=["积分兑换记录v3"])


def _gen_exchange_order_no() -> str:
    """EX+yyyyMMdd+6位流水."""
    return "EX" + datetime.utcnow().strftime("%Y%m%d") + "".join(
        random.choices(string.digits, k=6)
    )


def _safe_goods_image(images) -> Optional[str]:
    if not images:
        return None
    if isinstance(images, list):
        return images[0] if images else None
    if isinstance(images, str):
        return images
    return None


def _goods_type_str(item: PointsMallItem) -> str:
    """兼容：PointsMallItem.type 可能是枚举或字符串."""
    t = item.type
    if hasattr(t, "value"):
        return t.value
    return str(t) if t else "virtual"


# ────────────────────────── 兑换接口（新版 v3）──────────────────────────
@router.post("/mall/exchange")
async def mall_exchange(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """v3 版兑换接口：
    入参 { goods_id, quantity?, address?(实物) }
    根据 goods_type 分流：
      - coupon   → 扣积分 + 发券 + 写 PointExchangeRecord(success)
      - service  → 扣积分 + 发服务券(user_coupons, source='points_exchange') + 写记录
      - physical → 目前本轮限定仅写记录（模拟订单）；生产订单系统对接可后续接入
      - virtual / third_party → 置灰，提示开发中
    """
    goods_id = payload.get("goods_id") or payload.get("item_id")
    quantity = int(payload.get("quantity") or 1)
    if not goods_id or quantity < 1:
        raise HTTPException(status_code=400, detail="参数错误")

    res = await db.execute(
        select(PointsMallItem).where(
            PointsMallItem.id == goods_id,
            PointsMallItem.status == "active",
        )
    )
    item: Optional[PointsMallItem] = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")

    goods_type = _goods_type_str(item)
    if goods_type in ("virtual", "third_party"):
        raise HTTPException(status_code=400, detail="该商品类型正在开发中")

    total_points = int(item.price_points) * quantity

    # 权威可用积分计算（与 /api/points/summary 对齐）
    from app.api.points import compute_available_points
    breakdown = await compute_available_points(db, current_user.id)
    if breakdown["available"] < total_points:
        raise HTTPException(status_code=400, detail="积分不足")

    # 库存检查（券类型使用 coupon.total_count-claimed_count；其他用 item.stock）
    coupon_obj: Optional[Coupon] = None
    if goods_type == "coupon":
        # 关联券通过描述或 ref 字段查找：优先使用 images[0] 不是方案，采用 item.description 承载或用同名模糊匹配。
        # 现有 PointsMallItem 无 ref_coupon_id 字段，这里采用 description 存 JSON 的兼容策略：
        # 若 description 以 "ref_coupon_id=N" 开头则解析；否则按 name 匹配一个 active 券。
        ref_coupon_id = None
        desc = item.description or ""
        if "ref_coupon_id=" in desc:
            try:
                for seg in desc.split(";"):
                    if seg.strip().startswith("ref_coupon_id="):
                        ref_coupon_id = int(seg.split("=", 1)[1].strip())
                        break
            except Exception:
                ref_coupon_id = None
        if ref_coupon_id:
            cres = await db.execute(select(Coupon).where(Coupon.id == ref_coupon_id))
            coupon_obj = cres.scalar_one_or_none()
        if coupon_obj is None:
            # 退化为 stock 控制
            if int(item.stock or 0) < quantity:
                raise HTTPException(status_code=400, detail="库存不足")
        else:
            available_stock = int(coupon_obj.total_count or 0) - int(coupon_obj.claimed_count or 0)
            if available_stock < quantity:
                raise HTTPException(status_code=400, detail="券已兑完")
    elif goods_type == "service":
        if int(item.stock or 0) < quantity and int(item.stock or 0) >= 0:
            # stock=0 视为无限（体验服务由服务本体管控）
            if item.stock not in (None, 0):
                raise HTTPException(status_code=400, detail="库存不足")
    else:  # physical
        if int(item.stock or 0) < quantity:
            raise HTTPException(status_code=400, detail="库存不足")

    # ───── 执行扣减与记录写入（单事务）─────
    now = datetime.utcnow()
    user_coupon_id = None
    ref_service_type = None
    ref_service_id = None
    expire_at = None
    ref_order_no = None

    if goods_type == "coupon":
        if coupon_obj is not None:
            # 原子扣券库存
            upd = await db.execute(
                update(Coupon)
                .where(
                    Coupon.id == coupon_obj.id,
                    (Coupon.total_count - Coupon.claimed_count) >= quantity,
                )
                .values(claimed_count=Coupon.claimed_count + quantity)
            )
            if upd.rowcount == 0:
                raise HTTPException(status_code=400, detail="券已兑完")
            # 发券到用户
            validity_days = int(coupon_obj.validity_days or 30)
            uc_expire = now + timedelta(days=validity_days)
            for _ in range(quantity):
                uc = UserCoupon(
                    user_id=current_user.id,
                    coupon_id=coupon_obj.id,
                    status=UserCouponStatus.unused,
                    expire_at=uc_expire,
                    source="points_exchange",
                )
                db.add(uc)
                await db.flush()
                user_coupon_id = uc.id
            expire_at = uc_expire
        else:
            # 无关联券，仅扣 stock
            if int(item.stock or 0) > 0:
                item.stock = int(item.stock) - quantity

    elif goods_type == "service":
        # 体验服务：从商品描述解析 ref_service_type 和 ref_service_id
        desc = item.description or ""
        for seg in desc.split(";"):
            s = seg.strip()
            if s.startswith("ref_service_type="):
                ref_service_type = s.split("=", 1)[1].strip()
            elif s.startswith("ref_service_id="):
                try:
                    ref_service_id = int(s.split("=", 1)[1].strip())
                except Exception:
                    ref_service_id = None
        # 体验服务券目前复用 user_coupons 表结构不严谨（外键 coupon_id NOT NULL），
        # 为兼容生产数据库，若无 coupon_id 关联则不写 user_coupons，仅写 point_exchange_records。
        expire_at = now + timedelta(days=30)

    elif goods_type == "physical":
        # 扣库存
        if int(item.stock or 0) > 0:
            item.stock = int(item.stock) - quantity
        # 生产化时对接订单系统（UnifiedOrder）；本次先在记录表标记
        ref_order_no = _gen_exchange_order_no()

    # 写兑换记录（券 / 服务 / 实物 统一写一条，实物同时冗余 order_no）
    record = PointExchangeRecord(
        order_no=_gen_exchange_order_no(),
        user_id=current_user.id,
        goods_id=item.id,
        goods_type=goods_type,
        goods_name=item.name,
        goods_image=_safe_goods_image(item.images),
        points_cost=total_points,
        quantity=quantity,
        status="success",
        exchange_time=now,
        expire_at=expire_at,
        ref_coupon_id=coupon_obj.id if coupon_obj else None,
        ref_user_coupon_id=user_coupon_id,
        ref_service_type=ref_service_type,
        ref_service_id=ref_service_id,
        ref_order_no=ref_order_no,
    )
    db.add(record)

    # 扣积分：仅写一条 PointsRecord（负数），由权威计算口径统一
    pr = PointsRecord(
        user_id=current_user.id,
        points=-total_points,
        type=PointsType.redeem,
        description=f"积分兑换: {item.name}",
    )
    db.add(pr)

    await db.flush()
    await db.refresh(record)

    return {
        "id": record.id,
        "order_no": record.order_no,
        "goods_type": goods_type,
        "points_cost": total_points,
        "status": record.status,
        "message": "兑换成功",
    }


# ───────────────────────── 兑换记录列表 ─────────────────────────
@router.get("/exchange-records")
async def list_exchange_records(
    goods_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """兑换记录列表（合并查询：point_exchange_records + orders.points_exchange）.

    由于实物订单当前在本 feature 首版直接写 PointExchangeRecord（ref_order_no 冗余），
    此处只查 PointExchangeRecord 即可覆盖全部类型。
    """
    base = select(PointExchangeRecord).where(PointExchangeRecord.user_id == current_user.id)
    count_base = select(func.count(PointExchangeRecord.id)).where(
        PointExchangeRecord.user_id == current_user.id
    )
    if goods_type:
        base = base.where(PointExchangeRecord.goods_type == goods_type)
        count_base = count_base.where(PointExchangeRecord.goods_type == goods_type)

    total_res = await db.execute(count_base)
    total = total_res.scalar() or 0

    res = await db.execute(
        base.order_by(PointExchangeRecord.exchange_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = res.scalars().all()

    def _row_to_dict(r: PointExchangeRecord) -> dict:
        return {
            "id": r.id,
            "order_no": r.order_no,
            "goods_id": r.goods_id,
            "goods_type": r.goods_type,
            "goods_name": r.goods_name,
            "goods_image": r.goods_image,
            "points_cost": r.points_cost,
            "quantity": r.quantity,
            "status": r.status,
            "exchange_time": r.exchange_time.isoformat() if r.exchange_time else None,
            "expire_at": r.expire_at.isoformat() if r.expire_at else None,
            "used_at": r.used_at.isoformat() if r.used_at else None,
            "ref_coupon_id": r.ref_coupon_id,
            "ref_user_coupon_id": r.ref_user_coupon_id,
            "ref_service_type": r.ref_service_type,
            "ref_service_id": r.ref_service_id,
            "ref_order_no": r.ref_order_no,
        }

    items = [_row_to_dict(r) for r in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/exchange-records/{record_id}")
async def get_exchange_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(PointExchangeRecord).where(
            PointExchangeRecord.id == record_id,
            PointExchangeRecord.user_id == current_user.id,
        )
    )
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="兑换记录不存在")

    # 服务券"去预约"路由
    appointment_url = None
    if r.goods_type == "service" and r.ref_service_type and r.ref_service_id:
        st = r.ref_service_type
        sid = r.ref_service_id
        if st == "expert":
            appointment_url = f"/expert/{sid}"
        elif st == "physical_exam":
            appointment_url = f"/physical-exam/{sid}"
        elif st == "tcm":
            appointment_url = f"/tcm/{sid}"
        elif st == "health_plan":
            appointment_url = f"/health-plan/{sid}"

    return {
        "id": r.id,
        "order_no": r.order_no,
        "goods_id": r.goods_id,
        "goods_type": r.goods_type,
        "goods_name": r.goods_name,
        "goods_image": r.goods_image,
        "points_cost": r.points_cost,
        "quantity": r.quantity,
        "status": r.status,
        "exchange_time": r.exchange_time.isoformat() if r.exchange_time else None,
        "expire_at": r.expire_at.isoformat() if r.expire_at else None,
        "used_at": r.used_at.isoformat() if r.used_at else None,
        "ref_coupon_id": r.ref_coupon_id,
        "ref_user_coupon_id": r.ref_user_coupon_id,
        "ref_service_type": r.ref_service_type,
        "ref_service_id": r.ref_service_id,
        "ref_order_no": r.ref_order_no,
        "appointment_url": appointment_url,
    }


# ───── Admin: 管理员侧兑换记录（筛选 + 导出友好）─────
@router.get("/admin/exchange-records")
async def admin_list_exchange_records(
    user_id: Optional[int] = None,
    goods_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 简单校验：is_admin
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="无权限")

    base = select(PointExchangeRecord)
    count_base = select(func.count(PointExchangeRecord.id))
    if user_id:
        base = base.where(PointExchangeRecord.user_id == user_id)
        count_base = count_base.where(PointExchangeRecord.user_id == user_id)
    if goods_type:
        base = base.where(PointExchangeRecord.goods_type == goods_type)
        count_base = count_base.where(PointExchangeRecord.goods_type == goods_type)
    if status:
        base = base.where(PointExchangeRecord.status == status)
        count_base = count_base.where(PointExchangeRecord.status == status)

    total = (await db.execute(count_base)).scalar() or 0
    res = await db.execute(
        base.order_by(PointExchangeRecord.exchange_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = res.scalars().all()
    items = [
        {
            "id": r.id,
            "order_no": r.order_no,
            "user_id": r.user_id,
            "goods_id": r.goods_id,
            "goods_type": r.goods_type,
            "goods_name": r.goods_name,
            "points_cost": r.points_cost,
            "quantity": r.quantity,
            "status": r.status,
            "exchange_time": r.exchange_time.isoformat() if r.exchange_time else None,
            "expire_at": r.expire_at.isoformat() if r.expire_at else None,
            "ref_order_no": r.ref_order_no,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
