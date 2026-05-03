"""卡管理 v2.0 商家/管理员侧 API（第 5 期 销售看板 + 商家核销流水）+ 第 3 期商家核销流水。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import (
    CardDefinition,
    CardUsageLog,
    MerchantStore,
    Product,
    UnifiedOrder,
    User,
    UserCard,
)
from pydantic import BaseModel


router = APIRouter(prefix="/api/admin/cards", tags=["卡管理 v2.0（Admin）"])


# ───────────────────────────── Schemas ─────────────────────────────


class DashboardSummaryResponse(BaseModel):
    sales_count: int
    sales_amount: float
    redemption_count: int
    start: datetime
    end: datetime


class DashboardTrendPoint(BaseModel):
    period: str  # YYYY-MM-DD or YYYY-Www
    sales_count: int
    sales_amount: float
    redemption_count: int


class DashboardTrendResponse(BaseModel):
    granularity: str  # day | week
    items: List[DashboardTrendPoint]


class CardUsageAdminLog(BaseModel):
    id: int
    user_card_id: int
    user_id: Optional[int] = None
    product_id: int
    product_name: Optional[str] = None
    store_id: Optional[int] = None
    store_name: Optional[str] = None
    technician_id: Optional[int] = None
    used_at: datetime


class CardUsageAdminListResponse(BaseModel):
    total: int
    items: List[CardUsageAdminLog]


# ───────────────────────────── 第 3 期：商家端核销流水 ─────────────────────────────


@router.get(
    "/{card_def_id}/usage-logs",
    response_model=CardUsageAdminListResponse,
    summary="商家端按卡定义查询核销流水",
)
async def admin_card_usage_logs(
    card_def_id: int,
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    store_id: Optional[int] = Query(default=None),
    technician_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "merchant")),
):
    cd_q = await db.execute(select(CardDefinition).where(CardDefinition.id == card_def_id))
    cd = cd_q.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="卡定义不存在")

    # 通过 user_card 关联出该卡定义下所有 usage logs
    base = (
        select(CardUsageLog)
        .join(UserCard, UserCard.id == CardUsageLog.user_card_id)
        .where(UserCard.card_definition_id == card_def_id)
    )
    cnt = (
        select(func.count(CardUsageLog.id))
        .join(UserCard, UserCard.id == CardUsageLog.user_card_id)
        .where(UserCard.card_definition_id == card_def_id)
    )
    if start:
        base = base.where(CardUsageLog.used_at >= start)
        cnt = cnt.where(CardUsageLog.used_at >= start)
    if end:
        base = base.where(CardUsageLog.used_at <= end)
        cnt = cnt.where(CardUsageLog.used_at <= end)
    if store_id:
        base = base.where(CardUsageLog.store_id == store_id)
        cnt = cnt.where(CardUsageLog.store_id == store_id)
    if technician_id:
        base = base.where(CardUsageLog.technician_id == technician_id)
        cnt = cnt.where(CardUsageLog.technician_id == technician_id)

    total = int((await db.execute(cnt)).scalar() or 0)
    base = base.order_by(CardUsageLog.used_at.desc()).offset((page - 1) * page_size).limit(page_size)
    logs = list((await db.execute(base)).scalars().all())
    out: List[CardUsageAdminLog] = []
    if logs:
        pids = [l.product_id for l in logs]
        sids = [l.store_id for l in logs if l.store_id]
        ucids = [l.user_card_id for l in logs]
        pname_map = {}
        sname_map = {}
        uc_user_map = {}
        if pids:
            pres = await db.execute(
                select(Product.id, Product.name).where(Product.id.in_(pids))
            )
            pname_map = {row[0]: row[1] for row in pres.all()}
        if sids:
            sres = await db.execute(
                select(MerchantStore.id, MerchantStore.store_name).where(
                    MerchantStore.id.in_(sids)
                )
            )
            sname_map = {row[0]: row[1] for row in sres.all()}
        if ucids:
            ures = await db.execute(
                select(UserCard.id, UserCard.user_id).where(UserCard.id.in_(ucids))
            )
            uc_user_map = {row[0]: row[1] for row in ures.all()}
        for l in logs:
            out.append(
                CardUsageAdminLog(
                    id=l.id,
                    user_card_id=l.user_card_id,
                    user_id=uc_user_map.get(l.user_card_id),
                    product_id=l.product_id,
                    product_name=pname_map.get(l.product_id),
                    store_id=l.store_id,
                    store_name=sname_map.get(l.store_id) if l.store_id else None,
                    technician_id=l.technician_id,
                    used_at=l.used_at,
                )
            )
    return CardUsageAdminListResponse(total=total, items=out)


# ───────────────────────────── 第 5 期：销售看板 ─────────────────────────────


def _parse_range(start: Optional[datetime], end: Optional[datetime]) -> tuple[datetime, datetime]:
    if end is None:
        end = datetime.utcnow()
    if start is None:
        start = end - timedelta(days=7)
    if start > end:
        raise HTTPException(status_code=400, detail="start 不能晚于 end")
    return start, end


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    summary="卡销售看板 - 三大核心指标",
)
async def dashboard_summary(
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "merchant")),
):
    s, e = _parse_range(start, end)

    # 销量 = 卡订单数（status in completed/refunded 兼容；不算 cancelled）
    sales_q = await db.execute(
        select(func.count(UnifiedOrder.id), func.coalesce(func.sum(UnifiedOrder.paid_amount), 0))
        .where(
            UnifiedOrder.product_type == "card",
            UnifiedOrder.created_at >= s,
            UnifiedOrder.created_at <= e,
            UnifiedOrder.status.in_(
                [
                    "completed",
                    "pending_use",
                    "partial_used",
                    "used_up",
                    "expired",
                ]
            ),
        )
    )
    sales_row = sales_q.first()
    sales_count = int(sales_row[0] or 0) if sales_row else 0
    sales_amount = float(sales_row[1] or 0) if sales_row else 0.0

    # 核销次数
    redeem_q = await db.execute(
        select(func.count(CardUsageLog.id)).where(
            CardUsageLog.used_at >= s, CardUsageLog.used_at <= e
        )
    )
    redemption_count = int(redeem_q.scalar() or 0)

    return DashboardSummaryResponse(
        sales_count=sales_count,
        sales_amount=round(sales_amount, 2),
        redemption_count=redemption_count,
        start=s,
        end=e,
    )


@router.get(
    "/dashboard/trend",
    response_model=DashboardTrendResponse,
    summary="卡销售看板 - 趋势曲线",
)
async def dashboard_trend(
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    granularity: str = Query(default="day", pattern="^(day|week)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "merchant")),
):
    s, e = _parse_range(start, end)

    # 简化：在 Python 端聚合（避免 sqlite/mysql 时间函数差异）
    sales_orders = (await db.execute(
        select(UnifiedOrder.created_at, UnifiedOrder.paid_amount).where(
            UnifiedOrder.product_type == "card",
            UnifiedOrder.created_at >= s,
            UnifiedOrder.created_at <= e,
            UnifiedOrder.status.in_(
                ["completed", "pending_use", "partial_used", "expired"]
            ),
        )
    )).all()
    redeem_logs = (await db.execute(
        select(CardUsageLog.used_at).where(
            CardUsageLog.used_at >= s, CardUsageLog.used_at <= e
        )
    )).all()

    def _key(dt: datetime) -> str:
        if granularity == "day":
            return dt.strftime("%Y-%m-%d")
        # ISO 周
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    bucket = {}
    for created_at, paid in sales_orders:
        k = _key(created_at)
        b = bucket.setdefault(k, {"sales_count": 0, "sales_amount": 0.0, "redemption_count": 0})
        b["sales_count"] += 1
        b["sales_amount"] += float(paid or 0)
    for (used_at,) in redeem_logs:
        k = _key(used_at)
        b = bucket.setdefault(k, {"sales_count": 0, "sales_amount": 0.0, "redemption_count": 0})
        b["redemption_count"] += 1

    items = [
        DashboardTrendPoint(
            period=k,
            sales_count=v["sales_count"],
            sales_amount=round(v["sales_amount"], 2),
            redemption_count=v["redemption_count"],
        )
        for k, v in sorted(bucket.items())
    ]
    return DashboardTrendResponse(granularity=granularity, items=items)


# ───────────────────────────── 第 5 期：分享海报 ─────────────────────────────


# 公开访问的分享海报路由（不在 /admin 之下）
poster_router = APIRouter(prefix="/api/cards", tags=["卡分享海报 v2.0"])


@poster_router.get("/{card_id}/share-poster", summary="生成卡分享海报（800x1200 PNG）")
async def share_poster(
    card_id: int,
    inviter_user_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    cd_q = await db.execute(select(CardDefinition).where(CardDefinition.id == card_id))
    cd = cd_q.scalar_one_or_none()
    if not cd:
        raise HTTPException(status_code=404, detail="卡不存在")

    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
    except ImportError:
        # Pillow 未安装时返回 PNG 占位（对接生产时应安装 Pillow）
        raise HTTPException(status_code=503, detail="Pillow 未安装，海报生成不可用")

    img = Image.new("RGB", (800, 1200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # 简单海报：背景色块 + 卡名 + 价格 + 总次数 + 有效期 + 二维码占位文字
    draw.rectangle([(0, 0), (800, 400)], fill=(180, 220, 255))
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text((50, 50), cd.name, fill=(0, 0, 0), font=font)
    draw.text((50, 450), f"价格：¥ {cd.price}", fill=(0, 0, 0), font=font)
    if cd.total_times:
        draw.text((50, 500), f"总次数：{cd.total_times} 次", fill=(0, 0, 0), font=font)
    draw.text((50, 550), f"有效期：{cd.valid_days} 天", fill=(0, 0, 0), font=font)
    if inviter_user_id:
        draw.text((50, 600), f"邀请人：{inviter_user_id}", fill=(0, 0, 0), font=font)
    draw.rectangle([(280, 800), (520, 1040)], outline=(0, 0, 0), width=2)
    draw.text((300, 900), "扫码识别", fill=(0, 0, 0), font=font)
    draw.text((50, 1100), "长按识别二维码进入小程序", fill=(80, 80, 80), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
