"""V2.1 优惠券功能测试

覆盖：
- 模块一：领券中心置灰（claimed/sold_out/button_text/button_disabled）
- 模块二：F 兑换码批次/明细/作废（含 batch_no_confirm 强校验）
- 模块三：优惠券下架（is_superuser 校验、新人券强校验、原因预设）
- 模块四：积分兑换次数预留字段
- 数据迁移幂等性
"""
import json

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    Coupon,
    CouponCodeBatch,
    CouponRedeemCode,
    CouponStatus,
    CouponType,
    SystemConfig,
    User,
    UserRole,
)
from app.core.security import get_password_hash
from tests.conftest import test_session


# ───────── helpers ─────────


@pytest_asyncio.fixture
async def super_admin_token(client: AsyncClient):
    async with test_session() as session:
        session.add(User(
            phone="13800000099",
            password_hash=get_password_hash("admin123"),
            nickname="超级管理员",
            role=UserRole.admin,
            is_superuser=True,
        ))
        await session.commit()
    resp = await client.post("/api/admin/login", json={
        "phone": "13800000099",
        "password": "admin123",
    })
    return resp.json()["token"]


@pytest_asyncio.fixture
async def super_admin_headers(super_admin_token):
    return {"Authorization": f"Bearer {super_admin_token}"}


@pytest_asyncio.fixture
async def normal_admin_token(client: AsyncClient):
    """普通管理员（非超级）"""
    async with test_session() as session:
        session.add(User(
            phone="13800000088",
            password_hash=get_password_hash("admin123"),
            nickname="普通管理员",
            role=UserRole.admin,
            is_superuser=False,
        ))
        await session.commit()
    resp = await client.post("/api/admin/login", json={
        "phone": "13800000088",
        "password": "admin123",
    })
    return resp.json()["token"]


@pytest_asyncio.fixture
async def normal_admin_headers(normal_admin_token):
    return {"Authorization": f"Bearer {normal_admin_token}"}


async def _create_coupon(name="测试券", total_count=100):
    async with test_session() as session:
        c = Coupon(
            name=name,
            type=CouponType.full_reduction,
            condition_amount=100,
            discount_value=10,
            total_count=total_count,
            claimed_count=0,
            validity_days=30,
            status=CouponStatus.active,
            is_offline=False,
        )
        session.add(c)
        await session.commit()
        await session.refresh(c)
        return c.id


# ───────── 模块一：领券中心置灰 ─────────


@pytest.mark.asyncio
async def test_T1_1_available_unclaimed_with_stock(client: AsyncClient, auth_headers):
    """T1.1 用户未领过 + 库存>0 → 按钮可点"""
    cid = await _create_coupon()
    resp = await client.get("/api/coupons/available", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    target = next((it for it in items if it["id"] == cid), None)
    assert target is not None
    assert target["claimed"] is False
    assert target["sold_out"] is False
    assert target["button_text"] == "领取"
    assert target["button_disabled"] is False


@pytest.mark.asyncio
async def test_T1_2_available_claimed_unused(client: AsyncClient, auth_headers):
    """T1.2 用户已领过（unused） → 置灰「已领取」"""
    cid = await _create_coupon()
    r1 = await client.post("/api/coupons/claim", json={"coupon_id": cid}, headers=auth_headers)
    assert r1.status_code == 200
    resp = await client.get("/api/coupons/available", headers=auth_headers)
    target = next(it for it in resp.json()["items"] if it["id"] == cid)
    assert target["claimed"] is True
    assert target["button_text"] == "已领取"
    assert target["button_disabled"] is True


@pytest.mark.asyncio
async def test_T1_5_sold_out(client: AsyncClient, auth_headers):
    """T1.5 用户未领过 + 库存=0 → 置灰「已抢光」"""
    async with test_session() as session:
        c = Coupon(
            name="抢光券", type=CouponType.full_reduction,
            condition_amount=100, discount_value=10,
            total_count=5, claimed_count=5,
            validity_days=30, status=CouponStatus.active, is_offline=False,
        )
        session.add(c)
        await session.commit()
        await session.refresh(c)
        cid = c.id
    resp = await client.get("/api/coupons/available", headers=auth_headers)
    target = next(it for it in resp.json()["items"] if it["id"] == cid)
    assert target["claimed"] is False
    assert target["sold_out"] is True
    assert target["button_text"] == "已抢光"
    assert target["button_disabled"] is True


@pytest.mark.asyncio
async def test_T1_6_offline_coupon_not_in_list(client: AsyncClient, auth_headers, super_admin_headers):
    """T1.6 已下架的券 → 不在列表中返回"""
    cid = await _create_coupon("将下架的券")
    r = await client.post(
        f"/api/admin/coupons/{cid}/offline",
        json={"reason_type": "活动结束"},
        headers=super_admin_headers,
    )
    assert r.status_code == 200
    resp = await client.get("/api/coupons/available", headers=auth_headers)
    items = resp.json()["items"]
    assert all(it["id"] != cid for it in items)


@pytest.mark.asyncio
async def test_T1_7_anonymous_access(client: AsyncClient):
    """T1.7 未登录访问 → 正常返回，claimed=false"""
    cid = await _create_coupon("匿名券")
    resp = await client.get("/api/coupons/available")
    assert resp.status_code == 200
    items = resp.json()["items"]
    target = next((it for it in items if it["id"] == cid), None)
    assert target is not None
    assert target["claimed"] is False
    assert target["button_text"] == "领取"


@pytest.mark.asyncio
async def test_T1_8_duplicate_claim_returns_409(client: AsyncClient, auth_headers):
    """T1.8 重复领取请求 → 返回 409"""
    cid = await _create_coupon("仅领一次")
    r1 = await client.post("/api/coupons/claim", json={"coupon_id": cid}, headers=auth_headers)
    assert r1.status_code == 200
    r2 = await client.post("/api/coupons/claim", json={"coupon_id": cid}, headers=auth_headers)
    assert r2.status_code == 409


# ───────── 模块二：兑换码管理 ─────────


@pytest.mark.asyncio
async def test_T2_1_universal_requires_claim_limit(client: AsyncClient, super_admin_headers):
    """T2.1 生成一码通用批次 - claim_limit 必填校验"""
    cid = await _create_coupon()
    resp = await client.post(
        "/api/admin/coupons/redeem-code-batches",
        json={"coupon_id": cid, "code_type": "universal", "universal_code": "TESTCODE1"},
        headers=super_admin_headers,
    )
    assert resp.status_code == 400
    assert "claim_limit" in resp.json()["detail"] or "上限" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_T2_2_unique_auto_claim_limit(client: AsyncClient, super_admin_headers):
    """T2.2 生成一次性唯一码 - claim_limit 自动 = total_count"""
    cid = await _create_coupon()
    resp = await client.post(
        "/api/admin/coupons/redeem-code-batches",
        json={"coupon_id": cid, "code_type": "unique", "total_count": 10},
        headers=super_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["claim_limit"] == 10
    assert data["batch_no"].startswith("BATCH-")


@pytest.mark.asyncio
async def test_T2_3_batch_list_fields(client: AsyncClient, super_admin_headers):
    """T2.3 批次列表返回所需字段"""
    cid = await _create_coupon("批次券")
    await client.post(
        "/api/admin/coupons/redeem-code-batches",
        json={"coupon_id": cid, "code_type": "unique", "total_count": 5},
        headers=super_admin_headers,
    )
    r = await client.get("/api/admin/coupons/redeem-code-batches", headers=super_admin_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    item = items[0]
    for key in ("batch_no", "coupon_name", "code_type", "total_count",
                "used_codes_count", "available_count", "voided_count",
                "claim_limit", "expire_at", "created_at"):
        assert key in item, f"missing field {key}"


@pytest.mark.asyncio
async def test_T2_4_T2_5_universal_detail(client: AsyncClient, super_admin_headers):
    """T2.4/T2.5 一码通用统计 + 脱敏 + reveal"""
    cid = await _create_coupon()
    create = await client.post(
        "/api/admin/coupons/redeem-code-batches",
        json={"coupon_id": cid, "code_type": "universal",
              "universal_code": "ABCDEFGH1234", "claim_limit": 100, "per_user_limit": 1},
        headers=super_admin_headers,
    )
    bid = create.json()["id"]
    # 默认脱敏
    masked = await client.get(
        f"/api/admin/coupons/redeem-code-batches/{bid}/codes",
        headers=super_admin_headers,
    )
    assert masked.status_code == 200
    md = masked.json()
    assert md["code_type"] == "universal"
    assert md["claim_limit"] == 100
    assert "*" in md["code"]
    # reveal=true
    revealed = await client.get(
        f"/api/admin/coupons/redeem-code-batches/{bid}/codes?reveal=true",
        headers=super_admin_headers,
    )
    rd = revealed.json()
    assert rd["code"] == "ABCDEFGH1234"


@pytest.mark.asyncio
async def test_T2_7_void_batch_strict_confirm(client: AsyncClient, super_admin_headers):
    """T2.7 整批作废 - 强确认（批次编号不匹配返回 400）"""
    cid = await _create_coupon()
    create = await client.post(
        "/api/admin/coupons/redeem-code-batches",
        json={"coupon_id": cid, "code_type": "unique", "total_count": 5},
        headers=super_admin_headers,
    )
    bid = create.json()["id"]
    bn = create.json()["batch_no"]

    # 不匹配 → 400
    bad = await client.post(
        f"/api/admin/coupons/redeem-code-batches/{bid}/void",
        json={"batch_no_confirm": "WRONG-BATCH-NO", "reason": "测试"},
        headers=super_admin_headers,
    )
    assert bad.status_code == 400

    # 匹配 → 成功
    good = await client.post(
        f"/api/admin/coupons/redeem-code-batches/{bid}/void",
        json={"batch_no_confirm": bn, "reason": "运营调整"},
        headers=super_admin_headers,
    )
    assert good.status_code == 200
    assert good.json()["voided_count"] == 5


@pytest.mark.asyncio
async def test_T2_8_void_blocks_redeem(client: AsyncClient, auth_headers, super_admin_headers):
    """T2.8 作废后再次兑换返回 422"""
    cid = await _create_coupon()
    create = await client.post(
        "/api/admin/coupons/redeem-code-batches",
        json={"coupon_id": cid, "code_type": "universal",
              "universal_code": "VOIDABLE1", "claim_limit": 100},
        headers=super_admin_headers,
    )
    bid = create.json()["id"]
    bn = create.json()["batch_no"]
    # 作废
    await client.post(
        f"/api/admin/coupons/redeem-code-batches/{bid}/void",
        json={"batch_no_confirm": bn, "reason": "测试作废"},
        headers=super_admin_headers,
    )
    # 再兑换
    r = await client.post(
        "/api/coupons/redeem", json={"code": "VOIDABLE1"}, headers=auth_headers,
    )
    assert r.status_code == 422


# ───────── 模块三：下架 ─────────


@pytest.mark.asyncio
async def test_T3_1_normal_admin_cannot_offline(client: AsyncClient, normal_admin_headers):
    """T3.1 普通管理员调用下架接口返回 403"""
    cid = await _create_coupon()
    r = await client.post(
        f"/api/admin/coupons/{cid}/offline",
        json={"reason_type": "活动结束"},
        headers=normal_admin_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_T3_2_super_admin_offline_ok(client: AsyncClient, super_admin_headers):
    """T3.2 超管下架普通券 - 流程通过"""
    cid = await _create_coupon()
    r = await client.post(
        f"/api/admin/coupons/{cid}/offline",
        json={"reason_type": "活动结束"},
        headers=super_admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["is_offline"] is True


@pytest.mark.asyncio
async def test_T3_3_offline_reason_must_be_preset(client: AsyncClient, super_admin_headers):
    """T3.3 下架原因必须为预设之一"""
    cid = await _create_coupon()
    r = await client.post(
        f"/api/admin/coupons/{cid}/offline",
        json={"reason_type": "随便写"},
        headers=super_admin_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_T3_4_other_requires_5_chars(client: AsyncClient, super_admin_headers):
    """T3.4 "其他"原因 + 备注少于 5 字返回 422"""
    cid = await _create_coupon()
    r = await client.post(
        f"/api/admin/coupons/{cid}/offline",
        json={"reason_type": "其他", "reason_detail": "短"},
        headers=super_admin_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_T3_5_new_user_coupon_blocks_offline(client: AsyncClient, super_admin_headers):
    """T3.5 下架新人券返回 422"""
    cid = await _create_coupon("新人券")
    # 注册为新人券
    r1 = await client.put(
        "/api/admin/new-user-coupons",
        json={"coupon_ids": [cid]},
        headers=super_admin_headers,
    )
    assert r1.status_code == 200
    # 尝试下架
    r2 = await client.post(
        f"/api/admin/coupons/{cid}/offline",
        json={"reason_type": "活动结束"},
        headers=super_admin_headers,
    )
    assert r2.status_code == 422
    assert "新人券" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_T3_6_switch_then_offline(client: AsyncClient, super_admin_headers):
    """T3.6 切换新人券后再下架原券 - 通过"""
    c1 = await _create_coupon("券A")
    c2 = await _create_coupon("券B")
    await client.put("/api/admin/new-user-coupons", json={"coupon_ids": [c1]}, headers=super_admin_headers)
    # 切到 c2
    await client.put("/api/admin/new-user-coupons", json={"coupon_ids": [c2]}, headers=super_admin_headers)
    # 下架 c1 应当通过
    r = await client.post(
        f"/api/admin/coupons/{c1}/offline",
        json={"reason_type": "业务调整"},
        headers=super_admin_headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_T3_8_offline_keeps_user_coupons(client: AsyncClient, auth_headers, super_admin_headers):
    """T3.8 下架后我的券中已领的依然存在"""
    cid = await _create_coupon("待下架")
    # 领取
    r1 = await client.post("/api/coupons/claim", json={"coupon_id": cid}, headers=auth_headers)
    assert r1.status_code == 200
    # 下架
    await client.post(
        f"/api/admin/coupons/{cid}/offline",
        json={"reason_type": "活动结束"},
        headers=super_admin_headers,
    )
    # 我的券（unused）应仍包含
    r2 = await client.get("/api/coupons/mine?tab=unused", headers=auth_headers)
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert any(it["coupon_id"] == cid for it in items)


@pytest.mark.asyncio
async def test_T3_9_online_makes_visible(client: AsyncClient, auth_headers, super_admin_headers):
    """T3.9 重新上架 - 立即在领券中心可见"""
    cid = await _create_coupon("可重新上架")
    await client.post(
        f"/api/admin/coupons/{cid}/offline",
        json={"reason_type": "活动结束"},
        headers=super_admin_headers,
    )
    # 上架
    r = await client.post(f"/api/admin/coupons/{cid}/online", headers=super_admin_headers)
    assert r.status_code == 200
    # 检查可见
    rs = await client.get("/api/coupons/available", headers=auth_headers)
    assert any(it["id"] == cid for it in rs.json()["items"])


@pytest.mark.asyncio
async def test_T3_10_delete_endpoint_removed(client: AsyncClient, super_admin_headers):
    """T3.10 移除 DELETE 接口（404/405 验证）"""
    cid = await _create_coupon("禁止删除")
    r = await client.delete(f"/api/admin/coupons/{cid}", headers=super_admin_headers)
    # 接口已被移除：405 Method Not Allowed
    assert r.status_code in (404, 405)


# ───────── 模块四：积分兑换次数预留 ─────────


@pytest.mark.asyncio
async def test_T4_points_exchange_limit_field(client: AsyncClient, super_admin_headers):
    """T4 创建券时支持 points_exchange_limit 字段"""
    r = await client.post(
        "/api/admin/coupons",
        json={
            "name": "积分券", "type": "voucher",
            "condition_amount": 0, "discount_value": 5,
            "total_count": 50, "validity_days": 30, "status": "active",
            "points_exchange_limit": 3,
        },
        headers=super_admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["points_exchange_limit"] == 3


# ───────── 数据迁移幂等性 ─────────


@pytest.mark.asyncio
async def test_migration_marker_set():
    """T4.4 迁移标记位（SystemConfig.coupons_v2_1_migrated）。

    注：测试库通过 metadata.create_all 直接建表，不会执行 _migrate_coupons_v2_1，
    因此本用例只验证 SystemConfig 字段可写、可读。
    """
    async with test_session() as session:
        session.add(SystemConfig(
            config_key="coupons_v2_1_migrated", config_value="1", config_type="coupon",
        ))
        await session.commit()
        rs = await session.execute(
            select(SystemConfig).where(SystemConfig.config_key == "coupons_v2_1_migrated")
        )
        assert rs.scalar_one_or_none() is not None
