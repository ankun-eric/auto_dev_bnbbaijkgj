"""门店编号自动生成与已停用门店显示控制 — 自动化测试"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import test_session
from app.models.models import MerchantCategory, MerchantStore


@pytest_asyncio.fixture
async def seed_category():
    async with test_session() as session:
        cat = MerchantCategory(code="self_store", name="自营门店", sort=0, status="active")
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return cat.id


@pytest.mark.asyncio
async def test_create_store_auto_code(client: AsyncClient, admin_headers, seed_category):
    """新建门店时不传 store_code，后端应自动分配 MD00001"""
    res = await client.post(
        "/api/admin/merchant/stores",
        json={"store_name": "测试门店A", "category_id": seed_category, "contact_name": "张三"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["store_code"] == "MD00001"


@pytest.mark.asyncio
async def test_create_store_incremental_code(client: AsyncClient, admin_headers, seed_category):
    """连续创建多个门店，编号应递增"""
    for i in range(1, 4):
        res = await client.post(
            "/api/admin/merchant/stores",
            json={"store_name": f"门店{i}", "category_id": seed_category},
            headers=admin_headers,
        )
        assert res.status_code == 200
        assert res.json()["store_code"] == f"MD{i:05d}"


@pytest.mark.asyncio
async def test_store_code_readonly_on_update(client: AsyncClient, admin_headers, seed_category):
    """编辑门店时即使传了 store_code 也不应被修改"""
    create_res = await client.post(
        "/api/admin/merchant/stores",
        json={"store_name": "原名", "category_id": seed_category},
        headers=admin_headers,
    )
    store_id = create_res.json()["id"]

    await client.put(
        f"/api/admin/merchant/stores/{store_id}",
        json={"store_name": "新名", "store_code": "HACK001"},
        headers=admin_headers,
    )

    get_res = await client.get(f"/api/admin/merchant/stores/{store_id}", headers=admin_headers)
    assert get_res.json()["store_code"] == "MD00001"
    assert get_res.json()["store_name"] == "新名"


@pytest.mark.asyncio
async def test_list_stores_default_active_only(client: AsyncClient, admin_headers, seed_category):
    """默认只返回营业中门店"""
    await client.post(
        "/api/admin/merchant/stores",
        json={"store_name": "活跃店", "category_id": seed_category},
        headers=admin_headers,
    )
    create2 = await client.post(
        "/api/admin/merchant/stores",
        json={"store_name": "停用店", "category_id": seed_category},
        headers=admin_headers,
    )
    store2_id = create2.json()["id"]
    await client.put(
        f"/api/admin/merchant/stores/{store2_id}",
        json={"status": "disabled"},
        headers=admin_headers,
    )

    res = await client.get("/api/admin/merchant/stores", headers=admin_headers)
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["store_name"] == "活跃店"


@pytest.mark.asyncio
async def test_list_stores_include_inactive(client: AsyncClient, admin_headers, seed_category):
    """include_inactive=true 返回全部门店，且 active 排前面"""
    await client.post(
        "/api/admin/merchant/stores",
        json={"store_name": "活跃店", "category_id": seed_category},
        headers=admin_headers,
    )
    create2 = await client.post(
        "/api/admin/merchant/stores",
        json={"store_name": "停用店", "category_id": seed_category},
        headers=admin_headers,
    )
    store2_id = create2.json()["id"]
    await client.put(
        f"/api/admin/merchant/stores/{store2_id}",
        json={"status": "disabled"},
        headers=admin_headers,
    )

    res = await client.get(
        "/api/admin/merchant/stores?include_inactive=true",
        headers=admin_headers,
    )
    items = res.json()["items"]
    assert len(items) == 2
    assert items[0]["status"] == "active"
    assert items[1]["status"] == "disabled"
