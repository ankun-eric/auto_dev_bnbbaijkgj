"""[2026-05-01 门店地图能力 PRD v1.0] 自动化测试

覆盖：
1. 新建门店未传经纬度 → 400
2. 新建门店传非法经纬度（>180/<-180） → 400
3. 新建门店传合法经纬度 → 200，且 GET 详情返回 lat/lng
4. 编辑老门店可只更新经纬度（无 category_id 也行）
5. /api/admin/merchant/stores 列表带回 lat/lng/longitude/latitude/省市区
6. 兼容字段：使用 longitude/latitude 命名提交也能成功
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import test_session
from app.models.models import MerchantCategory


@pytest_asyncio.fixture
async def cat_id():
    async with test_session() as session:
        cat = MerchantCategory(code="self_store", name="自营门店", sort=0, status="active")
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return cat.id


@pytest.mark.asyncio
async def test_create_store_missing_coords_should_400(client: AsyncClient, admin_headers, cat_id):
    """未传经纬度的新建门店请求应被拒绝，提示需要在地图上选点"""
    res = await client.post(
        "/api/admin/merchant/stores",
        json={"store_name": "无坐标门店", "category_id": cat_id},
        headers=admin_headers,
    )
    assert res.status_code == 400
    assert "经纬度" in res.json().get("detail", "") or "地图" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_create_store_invalid_coords_should_400(client: AsyncClient, admin_headers, cat_id):
    """非法经纬度（>180）应被拒绝"""
    res = await client.post(
        "/api/admin/merchant/stores",
        json={"store_name": "非法坐标店", "category_id": cat_id, "lat": 23.0, "lng": 999.0},
        headers=admin_headers,
    )
    assert res.status_code == 400
    assert "经度" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_create_store_valid_coords_succeeds(client: AsyncClient, admin_headers, cat_id):
    """合法经纬度新建并能从详情/列表中取回"""
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "广州黄埔荔红店",
            "category_id": cat_id,
            "address": "荔红路 123 号",
            "province": "广东省",
            "city": "广州市",
            "district": "黄埔区",
            "lat": 23.1234567,
            "lng": 113.4567890,
        },
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    sid = res.json()["id"]

    # 详情
    detail = await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)
    body = detail.json()
    assert abs(body["lat"] - 23.123457) < 0.0001
    assert abs(body["lng"] - 113.456789) < 0.0001
    assert body["latitude"] == body["lat"]
    assert body["longitude"] == body["lng"]
    assert body["province"] == "广东省"
    assert body["district"] == "黄埔区"

    # 列表
    listing = await client.get("/api/admin/merchant/stores", headers=admin_headers)
    items = listing.json()["items"]
    target = next((it for it in items if it["id"] == sid), None)
    assert target is not None
    assert target["lat"] is not None
    assert target["lng"] is not None
    assert target["province"] == "广东省"


@pytest.mark.asyncio
async def test_create_store_with_longitude_latitude_alias(client: AsyncClient, admin_headers, cat_id):
    """使用 PRD §5.1.2 中的 longitude/latitude 命名提交，等价于 lat/lng"""
    res = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "别名提交门店",
            "category_id": cat_id,
            "longitude": 116.4074000,
            "latitude": 39.9042000,
        },
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    sid = res.json()["id"]
    detail = await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)
    body = detail.json()
    assert abs(body["lat"] - 39.9042) < 0.0001
    assert abs(body["lng"] - 116.4074) < 0.0001


@pytest.mark.asyncio
async def test_update_existing_store_coords_only(client: AsyncClient, admin_headers, cat_id):
    """编辑老门店只更新经纬度也应通过"""
    res = await client.post(
        "/api/admin/merchant/stores",
        json={"store_name": "可编辑店", "category_id": cat_id, "lat": 22.0, "lng": 114.0},
        headers=admin_headers,
    )
    sid = res.json()["id"]
    upd = await client.put(
        f"/api/admin/merchant/stores/{sid}",
        json={"lat": 30.5, "lng": 114.3},
        headers=admin_headers,
    )
    assert upd.status_code == 200
    detail = await client.get(f"/api/admin/merchant/stores/{sid}", headers=admin_headers)
    assert abs(detail.json()["lat"] - 30.5) < 0.0001
    assert abs(detail.json()["lng"] - 114.3) < 0.0001


@pytest.mark.asyncio
async def test_geo_config_endpoint_public(client: AsyncClient):
    """/api/maps/geo-config 是公开接口，前端无 token 即可访问，且永不抛异常"""
    res = await client.get("/api/maps/geo-config")
    assert res.status_code == 200
    body = res.json()
    assert "web_js_key" in body
    assert "h5_js_key" in body
    assert "has_server_key" in body
    assert body["provider"] == "amap"


@pytest.mark.asyncio
async def test_static_map_endpoint(client: AsyncClient):
    """静态地图 URL 接口应返回有效 URL"""
    res = await client.get("/api/maps/static-map?lat=23.13&lng=113.27&zoom=16")
    assert res.status_code == 200
    body = res.json()
    assert body["url"].startswith("http")
    assert body["provider"] in ("amap", "osm")
