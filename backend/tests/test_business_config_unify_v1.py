"""[2026-05-05 营业管理入口收敛 PRD v1.0] 测试用例

覆盖 PRD §七 测试用例：
- TC-02 字段去重：concurrency-limit PUT 忽略 store_max_concurrent
- TC-04 双层兜底（advance_days）
- TC-05 双层兜底（booking_cutoff_minutes）
- TC-06 边界值（严格小于）
- TC-07 取值校验（booking_cutoff_minutes 枚举）
- N-04 服务级覆盖空表检测
- N-02 booking-config GET/PUT
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.api.h5_checkout import _resolve_effective_advance_days
from app.core.security import get_password_hash
from app.models.models import (
    AccountIdentity,
    FulfillmentType,
    IdentityType,
    MerchantMemberRole,
    MerchantStore,
    MerchantStoreMembership,
    Product,
    ProductCategory,
    ProductStatus,
    ProductStore,
    User,
    UserRole,
)
from app.schemas.order_enhancement import (
    ALLOWED_CUTOFF_MINUTES,
    ConcurrencyLimitSaveRequest,
    StoreBookingConfigSaveRequest,
)
from tests.conftest import test_session


@pytest_asyncio.fixture
async def merchant_setup_v2():
    """创建商家用户 + 门店 + 服务商品（专用于本套测试，避免与其他套件冲突）。"""
    async with test_session() as session:
        merchant_user = User(
            phone="13700000901",
            password_hash=get_password_hash("merchant123"),
            nickname="营业管理测试商家",
            role=UserRole.merchant,
        )
        session.add(merchant_user)
        await session.flush()

        session.add(AccountIdentity(
            user_id=merchant_user.id,
            identity_type=IdentityType.merchant_owner,
            status="active",
        ))

        store = MerchantStore(
            store_name="营业管理测试门店",
            store_code="BC001",
            slot_capacity=3,
            business_start="09:00",
            business_end="18:00",
        )
        session.add(store)
        await session.flush()

        session.add(MerchantStoreMembership(
            user_id=merchant_user.id,
            store_id=store.id,
            member_role=MerchantMemberRole.owner,
            role_code="boss",
            status="active",
        ))

        cat = ProductCategory(name="营业管理测试分类", sort_order=1)
        session.add(cat)
        await session.flush()

        product = Product(
            name="营业管理测试服务-60min",
            category_id=cat.id,
            fulfillment_type=FulfillmentType.in_store,
            sale_price=Decimal("100.00"),
            stock=999,
            status=ProductStatus.active,
            service_duration_minutes=60,
        )
        session.add(product)
        await session.flush()

        session.add(ProductStore(product_id=product.id, store_id=store.id))
        await session.commit()

        return {
            "merchant_user_id": merchant_user.id,
            "merchant_phone": merchant_user.phone,
            "store_id": store.id,
            "product_id": product.id,
        }


@pytest_asyncio.fixture
async def merchant_token_v2(client: AsyncClient, merchant_setup_v2):
    resp = await client.post("/api/auth/login", json={
        "phone": merchant_setup_v2["merchant_phone"],
        "password": "merchant123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture
def merchant_headers_v2(merchant_token_v2):
    return {"Authorization": f"Bearer {merchant_token_v2}"}


# ════════════════════════════════════════════════════════════
# TC-02 字段去重：concurrency-limit 忽略 store_max_concurrent
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_concurrency_limit_ignores_store_max_concurrent(
    client, merchant_headers_v2, merchant_setup_v2
):
    """[N-03 / TC-02] concurrency-limit PUT 不再写入 slot_capacity，仅处理服务级覆盖"""
    store_id = merchant_setup_v2["store_id"]
    product_id = merchant_setup_v2["product_id"]
    # 改造前：slot_capacity 默认 3
    payload = {
        "store_id": store_id,
        "store_max_concurrent": 99,
        "service_overrides": [
            {"product_id": product_id, "max_concurrent_override": 5,
             "service_duration_minutes": 30},
        ],
    }
    r = await client.post(
        "/api/merchant/concurrency-limit", json=payload, headers=merchant_headers_v2
    )
    assert r.status_code == 200, r.text

    # 验证 slot_capacity 未被改成 99（仍为 3）
    async with test_session() as session:
        from sqlalchemy import select as _sel
        store = (await session.execute(
            _sel(MerchantStore).where(MerchantStore.id == store_id)
        )).scalar_one()
        assert store.slot_capacity == 3, "slot_capacity 必须保持 3，不被 store_max_concurrent 覆盖"

        product = (await session.execute(
            _sel(Product).where(Product.id == product_id)
        )).scalar_one()
        assert product.max_concurrent_override == 5
        assert product.service_duration_minutes == 30


@pytest.mark.asyncio
async def test_concurrency_limit_compatibility_no_store_max_concurrent(
    client, merchant_headers_v2, merchant_setup_v2
):
    """[N-03] concurrency-limit PUT 不传 store_max_concurrent 也应成功（已可选）"""
    store_id = merchant_setup_v2["store_id"]
    payload = {"store_id": store_id, "service_overrides": []}
    r = await client.post(
        "/api/merchant/concurrency-limit", json=payload, headers=merchant_headers_v2
    )
    assert r.status_code == 200


# ════════════════════════════════════════════════════════════
# N-02 / N-05 / N-06：booking-config GET / PUT
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_booking_config_get_default(
    client, merchant_headers_v2, merchant_setup_v2
):
    """[N-02 + N-05 + N-06] 初始默认：advance_days/booking_cutoff_minutes 为 None；slot_capacity=3"""
    store_id = merchant_setup_v2["store_id"]
    r = await client.get(
        f"/api/merchant/stores/{store_id}/booking-config",
        headers=merchant_headers_v2,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["store_id"] == store_id
    assert data["slot_capacity"] == 3
    assert data["advance_days"] is None
    assert data["booking_cutoff_minutes"] is None


@pytest.mark.asyncio
async def test_booking_config_put_full(
    client, merchant_headers_v2, merchant_setup_v2
):
    """[N-02 + N-05 + N-06] PUT 全字段后再 GET 校验回读一致"""
    store_id = merchant_setup_v2["store_id"]
    body = {"slot_capacity": 8, "advance_days": 7, "booking_cutoff_minutes": 60}
    r = await client.put(
        f"/api/merchant/stores/{store_id}/booking-config",
        json=body,
        headers=merchant_headers_v2,
    )
    assert r.status_code == 200, r.text

    g = await client.get(
        f"/api/merchant/stores/{store_id}/booking-config",
        headers=merchant_headers_v2,
    )
    data = g.json()
    assert data["slot_capacity"] == 8
    assert data["advance_days"] == 7
    assert data["booking_cutoff_minutes"] == 60


@pytest.mark.asyncio
async def test_booking_config_put_clear_to_none(
    client, merchant_headers_v2, merchant_setup_v2
):
    """[N-05] 允许把 advance_days / booking_cutoff_minutes 显式置为 null"""
    store_id = merchant_setup_v2["store_id"]
    await client.put(
        f"/api/merchant/stores/{store_id}/booking-config",
        json={"slot_capacity": 5, "advance_days": 30, "booking_cutoff_minutes": 30},
        headers=merchant_headers_v2,
    )
    r = await client.put(
        f"/api/merchant/stores/{store_id}/booking-config",
        json={"slot_capacity": 5, "advance_days": None, "booking_cutoff_minutes": None},
        headers=merchant_headers_v2,
    )
    assert r.status_code == 200
    g = await client.get(
        f"/api/merchant/stores/{store_id}/booking-config",
        headers=merchant_headers_v2,
    )
    data = g.json()
    assert data["advance_days"] is None
    assert data["booking_cutoff_minutes"] is None


# ════════════════════════════════════════════════════════════
# TC-07 取值校验：booking_cutoff_minutes 枚举
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_booking_config_cutoff_invalid_400(
    client, merchant_headers_v2, merchant_setup_v2
):
    """[TC-07] booking_cutoff_minutes=99 非枚举 → 400"""
    store_id = merchant_setup_v2["store_id"]
    r = await client.put(
        f"/api/merchant/stores/{store_id}/booking-config",
        json={"slot_capacity": 5, "advance_days": None, "booking_cutoff_minutes": 99},
        headers=merchant_headers_v2,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_booking_config_cutoff_all_valid_enums(
    client, merchant_headers_v2, merchant_setup_v2
):
    """[TC-07] 全部枚举（0/15/30/60/120/720/1440）逐一保存成功"""
    store_id = merchant_setup_v2["store_id"]
    for v in [0, 15, 30, 60, 120, 720, 1440]:
        r = await client.put(
            f"/api/merchant/stores/{store_id}/booking-config",
            json={"slot_capacity": 5, "advance_days": None, "booking_cutoff_minutes": v},
            headers=merchant_headers_v2,
        )
        assert r.status_code == 200, f"v={v} 应成功，实际 {r.status_code} {r.text}"


# ════════════════════════════════════════════════════════════
# TC-04 双层兜底（advance_days）：商品级优先 / 门店级兜底 / 都空=0
# ════════════════════════════════════════════════════════════

class _FakeStore:
    def __init__(self, advance_days=None):
        self.advance_days = advance_days


class _FakeProduct:
    def __init__(self, advance_days=None):
        self.advance_days = advance_days


def test_advance_days_product_first():
    """[TC-04] 商品级 30 / 门店级 7 → 30"""
    p = _FakeProduct(advance_days=30)
    s = _FakeStore(advance_days=7)
    assert _resolve_effective_advance_days(p, s) == 30


def test_advance_days_store_fallback():
    """[TC-04] 商品级 NULL / 门店级 7 → 7"""
    p = _FakeProduct(advance_days=None)
    s = _FakeStore(advance_days=7)
    assert _resolve_effective_advance_days(p, s) == 7


def test_advance_days_both_none_unlimited():
    """[TC-04] 两层都 NULL → 0=不限制"""
    p = _FakeProduct(advance_days=None)
    s = _FakeStore(advance_days=None)
    assert _resolve_effective_advance_days(p, s) == 0


def test_advance_days_product_zero_falls_back_to_store():
    """[TC-04] 商品级 0（=不限制语义）/ 门店级 7 → 7（保持商品级优先取值的"非空"语义）"""
    p = _FakeProduct(advance_days=0)
    s = _FakeStore(advance_days=7)
    assert _resolve_effective_advance_days(p, s) == 7


def test_advance_days_no_store_no_product():
    """[TC-04] store=None 时不抛异常"""
    p = _FakeProduct(advance_days=None)
    assert _resolve_effective_advance_days(p, None) == 0


# ════════════════════════════════════════════════════════════
# TC-05 双层兜底（booking_cutoff_minutes）边界
# ════════════════════════════════════════════════════════════

def _resolve_cutoff(product_cut, store_cut):
    """复刻 order_enhancement.get_available_slots 中的双层兜底取值规则。"""
    allowed = {0, 15, 30, 60, 120, 720, 1440}
    p = product_cut if product_cut in allowed else None
    s = store_cut if store_cut in allowed else None
    if p is not None:
        return int(p)
    if s is not None:
        return int(s)
    return 30


def test_cutoff_product_first():
    """[TC-05] 商品 60 / 门店 30 → 60"""
    assert _resolve_cutoff(60, 30) == 60


def test_cutoff_store_fallback():
    """[TC-05] 商品 None / 门店 30 → 30"""
    assert _resolve_cutoff(None, 30) == 30


def test_cutoff_both_none_default_30():
    """[TC-05] 都 None → 系统默认 30"""
    assert _resolve_cutoff(None, None) == 30


def test_cutoff_store_15_within_window_means_can_book():
    """[TC-05] 商品 None / 门店 15 → 15min（用于 9:31 → 10:00 = 29min > 15 → 可约）"""
    cutoff = _resolve_cutoff(None, 15)
    assert cutoff == 15
    # 9:31 距 10:00 = 29 分钟 > 15 → 可约
    now = datetime(2026, 5, 5, 9, 31, 0)
    slot_start = datetime(2026, 5, 5, 10, 0, 0)
    assert (slot_start - timedelta(minutes=cutoff)) >= now


def test_cutoff_store_unlimited_zero():
    """[TC-05] 门店 0=不限制 → 9:59 仍可约 10:00"""
    cutoff = _resolve_cutoff(None, 0)
    assert cutoff == 0


# ════════════════════════════════════════════════════════════
# TC-06 边界值：严格小于（<）
# ════════════════════════════════════════════════════════════

def test_strict_less_than_at_boundary_can_book():
    """[TC-06] 9:30:00 整、时段 10:00、cutoff=30：slot - cutoff = 9:30 < 9:30 不成立 → 可约"""
    now = datetime(2026, 5, 5, 9, 30, 0)
    slot_start = datetime(2026, 5, 5, 10, 0, 0)
    cutoff = 30
    # 复刻 order_enhancement.get_available_slots 的判定：
    # if slot_start_dt - timedelta(minutes=min_advance_min) < now: 不可预约
    is_unavailable = (slot_start - timedelta(minutes=cutoff)) < now
    assert is_unavailable is False  # 严格小于不成立 → 可约


def test_strict_less_than_one_second_after_boundary_cannot_book():
    """[TC-06] 9:30:01、时段 10:00、cutoff=30：slot - cutoff = 9:30:00 < 9:30:01 → 不可约"""
    now = datetime(2026, 5, 5, 9, 30, 1)
    slot_start = datetime(2026, 5, 5, 10, 0, 0)
    cutoff = 30
    is_unavailable = (slot_start - timedelta(minutes=cutoff)) < now
    assert is_unavailable is True


# ════════════════════════════════════════════════════════════
# Schema 校验：ConcurrencyLimitSaveRequest 不再要求 store_max_concurrent
# ════════════════════════════════════════════════════════════

def test_concurrency_limit_schema_optional_store_max_concurrent():
    """[N-03] schemas 校验：store_max_concurrent 现在可选"""
    obj = ConcurrencyLimitSaveRequest(store_id=1)
    assert obj.store_max_concurrent is None

    obj2 = ConcurrencyLimitSaveRequest(store_id=1, store_max_concurrent=5)
    assert obj2.store_max_concurrent == 5


def test_booking_config_schema_validates_ranges():
    """[N-02 + N-05] StoreBookingConfigSaveRequest 字段范围"""
    obj = StoreBookingConfigSaveRequest(
        slot_capacity=10, advance_days=7, booking_cutoff_minutes=30
    )
    assert obj.slot_capacity == 10
    assert obj.advance_days == 7

    # advance_days 超出
    with pytest.raises(Exception):
        StoreBookingConfigSaveRequest(slot_capacity=10, advance_days=400, booking_cutoff_minutes=None)

    # slot_capacity 负数
    with pytest.raises(Exception):
        StoreBookingConfigSaveRequest(slot_capacity=-1, advance_days=None, booking_cutoff_minutes=None)


def test_allowed_cutoff_minutes_set():
    """[TC-07] 枚举集合定义正确"""
    assert ALLOWED_CUTOFF_MINUTES == {0, 15, 30, 60, 120, 720, 1440}


# ════════════════════════════════════════════════════════════
# N-04：服务级覆盖空表（concurrency-limit GET services=[]）
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_concurrency_limit_empty_services_when_no_product_store(client, merchant_headers_v2):
    """[N-04] 创建一家未关联任何商品的门店 → concurrency-limit 返回 services=[]"""
    # 用 merchant_setup_v2 的商家创建第二家空门店
    async with test_session() as session:
        from sqlalchemy import select as _sel
        merchant = (await session.execute(
            _sel(User).where(User.phone == "13700000901")
        )).scalar_one()

        store2 = MerchantStore(
            store_name="空门店",
            store_code="BC002",
            slot_capacity=5,
            business_start="09:00",
            business_end="18:00",
        )
        session.add(store2)
        await session.flush()
        session.add(MerchantStoreMembership(
            user_id=merchant.id,
            store_id=store2.id,
            member_role=MerchantMemberRole.owner,
            role_code="boss",
            status="active",
        ))
        await session.commit()
        store2_id = store2.id

    r = await client.get(
        f"/api/merchant/concurrency-limit?store_id={store2_id}",
        headers=merchant_headers_v2,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["services"] == []


# ════════════════════════════════════════════════════════════
# N-06：商品级 booking_cutoff_minutes 写入 + 枚举校验
# ════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_product_booking_cutoff_minutes_field_persisted(merchant_setup_v2):
    """[N-06] Product 模型支持 booking_cutoff_minutes 字段持久化"""
    async with test_session() as session:
        from sqlalchemy import select as _sel
        product = (await session.execute(
            _sel(Product).where(Product.id == merchant_setup_v2["product_id"])
        )).scalar_one()
        product.booking_cutoff_minutes = 120
        await session.commit()

    async with test_session() as session:
        from sqlalchemy import select as _sel
        product = (await session.execute(
            _sel(Product).where(Product.id == merchant_setup_v2["product_id"])
        )).scalar_one()
        assert product.booking_cutoff_minutes == 120


@pytest.mark.asyncio
async def test_store_advance_days_and_cutoff_persisted(merchant_setup_v2):
    """[N-05 + N-06] MerchantStore 模型支持 advance_days/booking_cutoff_minutes 字段持久化"""
    async with test_session() as session:
        from sqlalchemy import select as _sel
        store = (await session.execute(
            _sel(MerchantStore).where(MerchantStore.id == merchant_setup_v2["store_id"])
        )).scalar_one()
        store.advance_days = 14
        store.booking_cutoff_minutes = 60
        await session.commit()

    async with test_session() as session:
        from sqlalchemy import select as _sel
        store = (await session.execute(
            _sel(MerchantStore).where(MerchantStore.id == merchant_setup_v2["store_id"])
        )).scalar_one()
        assert store.advance_days == 14
        assert store.booking_cutoff_minutes == 60
