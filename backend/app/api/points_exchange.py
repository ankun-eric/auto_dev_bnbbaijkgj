"""积分兑换记录 v3.1 API（PRD v2 合并发版）.

设计变更（相对 v3）：
- 体验服务（service）改为直接关联 ``products.id``（``PointsMallItem.ref_service_id``），
  老数据兜底从 description 字符串 ``ref_service_id=xx`` 回读（双读兜底）。
- 兑换体验服务时**自动生成一张"服务抵扣优惠券"**入账到 ``user_coupons``，
  与 ``applicable_products`` 绑定在 ``ref_service_id`` 指向的服务商品上，用户下次购买该商品可抵扣。
- 券类（coupon）走 ``PointsMallItem.ref_coupon_id``；老数据兜底。
- 所有接口的报错统一抛 ``HTTPException(status_code, detail)``，前端读 ``detail`` 展示。
"""
from __future__ import annotations

import logging
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Coupon,
    CouponStatus,
    CouponType,
    PointExchangeRecord,
    PointsMallItem,
    PointsMallItemType,
    PointsRecord,
    PointsType,
    Product,
    User,
    UserCoupon,
    UserCouponStatus,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/points", tags=["积分兑换记录v3.1"])


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


def _parse_legacy_ref(desc: str, key: str) -> Optional[int]:
    """从老商品 description 里反解 ``<key>=<int>``（双读兜底）."""
    if not desc or key not in desc:
        return None
    for seg in desc.split(";"):
        s = seg.strip()
        if s.startswith(f"{key}="):
            try:
                return int(s.split("=", 1)[1].strip())
            except Exception:
                return None
    return None


def _item_detail_dict(i: PointsMallItem) -> dict:
    """C 端商品详情页展示用字段."""
    t = _goods_type_str(i)
    return {
        "id": i.id,
        "name": i.name,
        "description": i.description or "",
        "detail_html": getattr(i, "detail_html", None) or "",
        "images": i.images if isinstance(i.images, list) else ([] if not i.images else [i.images]),
        "type": t,
        "price_points": i.price_points,
        "stock": i.stock,
        "status": i.status,
        "ref_coupon_id": getattr(i, "ref_coupon_id", None),
        "ref_service_id": getattr(i, "ref_service_id", None),
        "limit_per_user": getattr(i, "limit_per_user", 0) or 0,
    }


# ────────────────────────── 商品详情（v3.1 新增：F4）──────────────────────────
@router.get("/mall/items/{item_id}")
async def get_mall_item_detail(
    item_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """积分商品详情页数据源（F4）.

    返回：商品基础字段 + ``detail_html`` + 按钮 5 态判定 + 用户已兑换次数（用于限兑判断）。
    """
    res = await db.execute(select(PointsMallItem).where(PointsMallItem.id == item_id))
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")

    data = _item_detail_dict(item)

    # 关联服务商品元数据（如用于详情页展示服务名/图）
    service_info = None
    sid = data["ref_service_id"] or _parse_legacy_ref(item.description or "", "ref_service_id")
    if data["type"] == "service" and sid:
        pr = (await db.execute(select(Product).where(Product.id == sid))).scalar_one_or_none()
        if pr:
            pr_images = pr.images if isinstance(pr.images, list) else []
            service_info = {
                "id": pr.id,
                "name": pr.name,
                "image": pr_images[0] if pr_images else None,
                "sale_price": float(pr.sale_price) if pr.sale_price is not None else None,
            }
    data["service_info"] = service_info

    # 用户已兑换次数（用于 limit_per_user 判断）
    user_exchanged = 0
    if current_user:
        cnt = await db.execute(
            select(func.count(PointExchangeRecord.id)).where(
                PointExchangeRecord.user_id == current_user.id,
                PointExchangeRecord.goods_id == item.id,
                PointExchangeRecord.status.in_(["success", "used"]),
            )
        )
        user_exchanged = int(cnt.scalar() or 0)
    data["user_exchanged"] = user_exchanged

    # 按钮 5 态（前端也可按字段自行判定，这里给出推荐态便于三端统一）
    btn_state = "normal"
    btn_text = f"立即兑换（消耗 {item.price_points} 积分）"
    if (item.status or "active") != "active":
        btn_state = "offline"
        btn_text = "已下架"
    elif _goods_type_str(item) != "coupon" and int(item.stock or 0) == 0:
        # stock=0 只对非 coupon 类型视为兑完（coupon 的真实库存由 Coupon.total_count 管）
        btn_state = "sold_out"
        btn_text = "已兑完"
    elif data["limit_per_user"] and user_exchanged >= data["limit_per_user"]:
        btn_state = "limit_reached"
        btn_text = "已达兑换上限"
    data["button_state"] = btn_state
    data["button_text"] = btn_text
    return data


# ────────────────────────── 兑换接口（v3.1 升级版）──────────────────────────
@router.post("/mall/exchange")
async def mall_exchange(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """v3.1 版兑换接口：
    入参 { goods_id, quantity?, address?(实物) }
    根据 goods_type 分流：
      - coupon   → 扣积分 + 发券（ref_coupon_id 优先，description 兜底）
      - service  → 扣积分 + 自动生成"服务抵扣优惠券"（与 products.ref_service_id 绑定）
      - physical → 扣积分 + 扣库存 + 写记录
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

    # 限兑次数（PRD F4.3 优先级 3）
    limit_per_user = int(getattr(item, "limit_per_user", 0) or 0)
    if limit_per_user > 0:
        cnt = await db.execute(
            select(func.count(PointExchangeRecord.id)).where(
                PointExchangeRecord.user_id == current_user.id,
                PointExchangeRecord.goods_id == item.id,
                PointExchangeRecord.status.in_(["success", "used"]),
            )
        )
        used = int(cnt.scalar() or 0)
        if used + quantity > limit_per_user:
            raise HTTPException(status_code=400, detail="已达兑换上限")

    # 权威可用积分（与 /api/points/summary 对齐）
    from app.api.points import compute_available_points
    breakdown = await compute_available_points(db, current_user.id)
    available = int(breakdown.get("available") or 0)
    if available < total_points:
        raise HTTPException(status_code=400, detail=f"积分不足（差 {total_points - available} 分）")

    # ───── 按类型处理库存/关联 ─────
    coupon_obj: Optional[Coupon] = None
    product_obj: Optional[Product] = None

    if goods_type == "coupon":
        ref_coupon_id = getattr(item, "ref_coupon_id", None) or _parse_legacy_ref(
            item.description or "", "ref_coupon_id"
        )
        if ref_coupon_id:
            coupon_obj = (
                await db.execute(select(Coupon).where(Coupon.id == ref_coupon_id))
            ).scalar_one_or_none()
        if coupon_obj is None:
            # 没关联券 → 只靠 stock 管理
            if int(item.stock or 0) < quantity:
                raise HTTPException(status_code=400, detail="已兑完")
        else:
            available_stock = int(coupon_obj.total_count or 0) - int(coupon_obj.claimed_count or 0)
            if available_stock < quantity:
                raise HTTPException(status_code=400, detail="已兑完")

    elif goods_type == "service":
        ref_service_id = getattr(item, "ref_service_id", None) or _parse_legacy_ref(
            item.description or "", "ref_service_id"
        )
        if not ref_service_id:
            raise HTTPException(
                status_code=400,
                detail="体验服务类商品未关联服务商品，请联系运营在后台补配",
            )
        product_obj = (
            await db.execute(select(Product).where(Product.id == ref_service_id))
        ).scalar_one_or_none()
        if not product_obj:
            raise HTTPException(
                status_code=400,
                detail=f"关联的服务商品（id={ref_service_id}）不存在或已删除",
            )
        # 库存：stock=0 视为无限（体验服务由服务本体管控）
        if int(item.stock or 0) > 0 and int(item.stock or 0) < quantity:
            raise HTTPException(status_code=400, detail="已兑完")

    else:  # physical
        if int(item.stock or 0) < quantity:
            raise HTTPException(status_code=400, detail="已兑完")

    # ───── 执行扣减与记录写入（单事务）─────
    now = datetime.utcnow()
    user_coupon_id = None
    ref_service_type = None
    ref_service_id_out = None
    expire_at = None
    ref_order_no = None

    if goods_type == "coupon":
        if coupon_obj is not None:
            upd = await db.execute(
                update(Coupon)
                .where(
                    Coupon.id == coupon_obj.id,
                    (Coupon.total_count - Coupon.claimed_count) >= quantity,
                )
                .values(claimed_count=Coupon.claimed_count + quantity)
            )
            if upd.rowcount == 0:
                raise HTTPException(status_code=400, detail="已兑完")
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
            if int(item.stock or 0) > 0:
                item.stock = int(item.stock) - quantity

    elif goods_type == "service":
        # PRD Bug-Q6-b.B：自动生成"服务抵扣优惠券"并绑定到该服务商品
        ref_service_id_out = product_obj.id if product_obj else None
        ref_service_type = "product_in_store"  # 新口径：统一指向 products 表
        expire_at = now + timedelta(days=30)

        from app.models.models import CouponScope
        coupon_name = (
            f"服务抵扣券（{product_obj.name}）" if product_obj else f"服务抵扣券（{item.name}）"
        )
        discount_amount = (
            float(product_obj.sale_price)
            if product_obj and product_obj.sale_price is not None
            else 0.0
        )
        auto_coupon = Coupon(
            name=coupon_name,
            type=CouponType.full_reduction,  # 满 discount_amount 减 discount_amount 的全额抵扣券
            condition_amount=discount_amount,
            discount_value=discount_amount,
            scope=CouponScope.product,
            scope_ids=[product_obj.id] if product_obj else None,
            total_count=quantity,
            claimed_count=quantity,
            validity_days=30,
            status=CouponStatus.active,
        )
        try:
            db.add(auto_coupon)
            await db.flush()
        except Exception as e:  # noqa: BLE001
            _logger.error("生成服务抵扣券失败：%s", e)
            raise HTTPException(
                status_code=500,
                detail=f"生成服务抵扣券失败：{e}",
            )

        for _ in range(quantity):
            uc = UserCoupon(
                user_id=current_user.id,
                coupon_id=auto_coupon.id,
                status=UserCouponStatus.unused,
                expire_at=expire_at,
                source="points_exchange",
            )
            db.add(uc)
            await db.flush()
            user_coupon_id = uc.id

        # 扣库存（积分商品层面，体验服务 stock 允许为 0 不扣）
        if int(item.stock or 0) > 0:
            item.stock = int(item.stock) - quantity

    elif goods_type == "physical":
        if int(item.stock or 0) > 0:
            item.stock = int(item.stock) - quantity
        ref_order_no = _gen_exchange_order_no()

    # 写兑换记录
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
        ref_service_id=ref_service_id_out,
        ref_order_no=ref_order_no,
    )
    db.add(record)

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
    """兑换记录列表。"""
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
    if r.goods_type == "service" and r.ref_service_id:
        # v3.1 统一走 products，跳转商品详情让用户下单用券
        appointment_url = f"/product-detail/{r.ref_service_id}"

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
