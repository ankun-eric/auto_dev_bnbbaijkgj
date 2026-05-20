"""[PRD-MY-DEVICES-V1 2026-05-21] 「我的设备」V2 接口测试。

覆盖：
- GET /api/devices/catalog 品牌分组结构（5 品牌、宾尼 7 项、各 is_active/is_unique 字段）
- GET /api/devices/my 未绑定时返回空、绑定后包含正确字段（SN 脱敏等）
- POST /api/devices/bind 正常绑定 / 未接通拒绝 / 唯一类重复拒绝 / 可多绑允许
- POST /api/devices/unbind 软删除生效 + 解绑后区域二按钮状态联动
- PATCH /api/devices/binding/{id} 修改别名 + 不可改 SN
- 同 SN 多账户共享允许
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.devices_v2 import DeviceCatalog
from app.models.models import User, UserRole


@pytest_asyncio.fixture
async def seeded_catalog():
    """直接调用 seed 函数，确保 device_catalog 表已有 17 项种子数据。"""
    from app.api.devices_v2 import seed_device_catalog
    from app.core.database import async_session as _session
    async with _session() as s:
        stats = await seed_device_catalog(s)
        await s.commit()
    return stats


def _binni_smartwatch_id(catalog_groups):
    for g in catalog_groups:
        if g["brand_code"] == "binni":
            for it in g["items"]:
                if it["category_code"] == "smartwatch":
                    return it["id"]
    raise AssertionError("找不到宾尼智能手表")


def _binni_smoke_alarm_id(catalog_groups):
    for g in catalog_groups:
        if g["brand_code"] == "binni":
            for it in g["items"]:
                if it["category_code"] == "smoke_alarm":
                    return it["id"]
    raise AssertionError("找不到宾尼烟雾报警器")


def _apple_watch_id(catalog_groups):
    for g in catalog_groups:
        if g["brand_code"] == "apple":
            for it in g["items"]:
                return it["id"]
    raise AssertionError("找不到 Apple Watch")


@pytest.mark.asyncio
async def test_catalog_structure(client: AsyncClient, auth_headers, seeded_catalog):
    res = await client.get("/api/devices/catalog", headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "groups" in data
    groups = {g["brand_code"]: g for g in data["groups"]}
    # 5 个品牌全部存在
    for b in ["binni", "huawei", "xiaomi", "apple", "other"]:
        assert b in groups, f"品牌 {b} 缺失"
    # 宾尼 7 项
    assert len(groups["binni"]["items"]) == 7
    # 宾尼全部 is_active
    assert all(it["is_active"] is True for it in groups["binni"]["items"])
    # 华为手环 is_active；其他不接通
    huawei_band = [it for it in groups["huawei"]["items"] if it["category_code"] == "band"]
    assert huawei_band and huawei_band[0]["is_active"] is True
    huawei_others = [it for it in groups["huawei"]["items"] if it["category_code"] != "band"]
    assert all(it["is_active"] is False for it in huawei_others)
    # 苹果全部敬请期待
    assert all(it["is_active"] is False for it in groups["apple"]["items"])
    # 烟雾报警器 is_unique=False（可多绑）
    smoke = [it for it in groups["binni"]["items"] if it["category_code"] == "smoke_alarm"]
    assert smoke and smoke[0]["is_unique"] is False


@pytest.mark.asyncio
async def test_my_devices_initial_empty(client: AsyncClient, auth_headers, seeded_catalog):
    res = await client.get("/api/devices/my", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_bind_success_and_my_list_update(client: AsyncClient, auth_headers, seeded_catalog):
    cat_res = await client.get("/api/devices/catalog", headers=auth_headers)
    binni_watch = _binni_smartwatch_id(cat_res.json()["groups"])

    res = await client.post(
        "/api/devices/bind",
        headers=auth_headers,
        json={"catalog_id": binni_watch, "sn": "BNW1234567890", "alias": "爸爸的手表"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] > 0
    assert body["binding"]["sn"] == "BNW1234567890"
    assert body["binding"]["sn_masked"] == "BNW" + "****" + "7890"
    assert body["binding"]["alias"] == "爸爸的手表"
    assert body["binding"]["is_active"] is True
    assert body["binding"]["bound_at"] is not None

    # /my 列表立即有这一条
    my_res = await client.get("/api/devices/my", headers=auth_headers)
    assert my_res.status_code == 200
    items = my_res.json()["items"]
    assert len(items) == 1
    assert items[0]["device_name"] == "宾尼智能手表"

    # catalog 中的 bound_count == 1
    cat2 = await client.get("/api/devices/catalog", headers=auth_headers)
    binni_group = [g for g in cat2.json()["groups"] if g["brand_code"] == "binni"][0]
    sw = [it for it in binni_group["items"] if it["category_code"] == "smartwatch"][0]
    assert sw["bound_count"] == 1


@pytest.mark.asyncio
async def test_bind_inactive_rejected(client: AsyncClient, auth_headers, seeded_catalog):
    cat_res = await client.get("/api/devices/catalog", headers=auth_headers)
    apple = _apple_watch_id(cat_res.json()["groups"])
    res = await client.post(
        "/api/devices/bind",
        headers=auth_headers,
        json={"catalog_id": apple, "sn": "AW123456"},
    )
    assert res.status_code == 400
    assert "敬请期待" in res.text or "未接通" in res.text


@pytest.mark.asyncio
async def test_bind_unique_duplicate_rejected(client: AsyncClient, auth_headers, seeded_catalog):
    cat_res = await client.get("/api/devices/catalog", headers=auth_headers)
    sw = _binni_smartwatch_id(cat_res.json()["groups"])
    r1 = await client.post(
        "/api/devices/bind", headers=auth_headers,
        json={"catalog_id": sw, "sn": "BNW0001"},
    )
    assert r1.status_code == 200
    r2 = await client.post(
        "/api/devices/bind", headers=auth_headers,
        json={"catalog_id": sw, "sn": "BNW0002"},
    )
    assert r2.status_code == 409
    assert "仅可绑定 1 台" in r2.text or "解绑" in r2.text


@pytest.mark.asyncio
async def test_bind_multi_allowed_for_smoke_alarm(client: AsyncClient, auth_headers, seeded_catalog):
    cat_res = await client.get("/api/devices/catalog", headers=auth_headers)
    smoke = _binni_smoke_alarm_id(cat_res.json()["groups"])
    for i in range(3):
        r = await client.post(
            "/api/devices/bind", headers=auth_headers,
            json={"catalog_id": smoke, "sn": f"SMK{i:04d}"},
        )
        assert r.status_code == 200, r.text
    my_res = await client.get("/api/devices/my", headers=auth_headers)
    items = my_res.json()["items"]
    smoke_items = [it for it in items if it["category_code"] == "smoke_alarm"]
    assert len(smoke_items) == 3


@pytest.mark.asyncio
async def test_bind_empty_sn_rejected(client: AsyncClient, auth_headers, seeded_catalog):
    cat_res = await client.get("/api/devices/catalog", headers=auth_headers)
    sw = _binni_smartwatch_id(cat_res.json()["groups"])
    r = await client.post(
        "/api/devices/bind", headers=auth_headers,
        json={"catalog_id": sw, "sn": "   "},
    )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_unbind_softdelete_and_button_state(client: AsyncClient, auth_headers, seeded_catalog):
    cat_res = await client.get("/api/devices/catalog", headers=auth_headers)
    sw = _binni_smartwatch_id(cat_res.json()["groups"])
    r1 = await client.post(
        "/api/devices/bind", headers=auth_headers,
        json={"catalog_id": sw, "sn": "BNW0001"},
    )
    bid = r1.json()["id"]

    r2 = await client.post("/api/devices/unbind", headers=auth_headers, json={"binding_id": bid})
    assert r2.status_code == 200
    assert "已解绑" in r2.text

    # /my 列表为空
    my_res = await client.get("/api/devices/my", headers=auth_headers)
    assert my_res.json()["items"] == []

    # catalog 中 bound_count 回到 0（按钮恢复"绑定"态）
    cat2 = await client.get("/api/devices/catalog", headers=auth_headers)
    binni = [g for g in cat2.json()["groups"] if g["brand_code"] == "binni"][0]
    sw2 = [it for it in binni["items"] if it["category_code"] == "smartwatch"][0]
    assert sw2["bound_count"] == 0

    # 再次绑定应当成功（唯一类解绑后可重绑）
    r3 = await client.post(
        "/api/devices/bind", headers=auth_headers,
        json={"catalog_id": sw, "sn": "BNW0002"},
    )
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_edit_alias_only(client: AsyncClient, auth_headers, seeded_catalog):
    cat_res = await client.get("/api/devices/catalog", headers=auth_headers)
    sw = _binni_smartwatch_id(cat_res.json()["groups"])
    r1 = await client.post(
        "/api/devices/bind", headers=auth_headers,
        json={"catalog_id": sw, "sn": "BNW0001", "alias": "旧别名"},
    )
    bid = r1.json()["id"]
    r2 = await client.patch(
        f"/api/devices/binding/{bid}", headers=auth_headers,
        json={"alias": "新别名"},
    )
    assert r2.status_code == 200
    assert r2.json()["binding"]["alias"] == "新别名"
    assert r2.json()["binding"]["sn"] == "BNW0001"  # SN 不被改


@pytest.mark.asyncio
async def test_same_sn_cross_user_share(client: AsyncClient, seeded_catalog):
    """两个不同账户使用同一 SN 绑定同型号设备应当都成功（家庭共享）。"""
    from app.core.database import async_session as _session
    # 注册 user A
    await client.post("/api/auth/register", json={
        "phone": "13900000010", "password": "user123", "nickname": "用户A",
    })
    a_login = await client.post("/api/auth/login", json={
        "phone": "13900000010", "password": "user123",
    })
    a_token = a_login.json()["access_token"]
    a_headers = {"Authorization": f"Bearer {a_token}", "Client-Type": "h5-user"}

    # 注册 user B
    await client.post("/api/auth/register", json={
        "phone": "13900000011", "password": "user123", "nickname": "用户B",
    })
    b_login = await client.post("/api/auth/login", json={
        "phone": "13900000011", "password": "user123",
    })
    b_token = b_login.json()["access_token"]
    b_headers = {"Authorization": f"Bearer {b_token}", "Client-Type": "h5-user"}

    # 拿一次 catalog（任何账户都能拿）
    cat_res = await client.get("/api/devices/catalog", headers=a_headers)
    sw = _binni_smartwatch_id(cat_res.json()["groups"])

    same_sn = "BNW-SHARED-001"
    ra = await client.post("/api/devices/bind", headers=a_headers,
                            json={"catalog_id": sw, "sn": same_sn})
    rb = await client.post("/api/devices/bind", headers=b_headers,
                            json={"catalog_id": sw, "sn": same_sn})
    assert ra.status_code == 200, ra.text
    assert rb.status_code == 200, rb.text


@pytest.mark.asyncio
async def test_unbind_nonexistent(client: AsyncClient, auth_headers, seeded_catalog):
    r = await client.post("/api/devices/unbind", headers=auth_headers, json={"binding_id": 999999})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_catalog_requires_auth(client: AsyncClient, seeded_catalog):
    """未登录访问应返回 401。"""
    r = await client.get("/api/devices/catalog")
    assert r.status_code in (401, 403)
