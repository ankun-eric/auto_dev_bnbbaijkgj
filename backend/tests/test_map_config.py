"""[2026-05-01 地图配置 PRD v1.0] 后端自动化测试

覆盖：
1. GET /api/admin/map-config 未保存过 → has_record=False，返回环境变量回填值
2. PUT /api/admin/map-config 必填 3 个 Key 缺一报 400
3. PUT /api/admin/map-config 经纬度合法/缩放级别越界报 400
4. PUT /api/admin/map-config 正常保存后再 GET → has_record=True 且字段一致
5. POST /api/admin/map-config/test 逐项返回 ok/fail（无网络环境用桩）
6. 测试后写入测试记录，GET /api/admin/map-config/test-logs 返回最近 5 条
7. /api/maps/geo-config 公开接口能读取到数据库中保存的配置（保存后立即生效）
8. PUT 新建一行后再次 PUT 不会创建第二行（始终单行更新）
9. 普通用户访问 admin 接口 → 401/403
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.models.models import MapConfig, MapTestLog


# ──────── 工具：mock 高德/JS 接口 ────────


@pytest_asyncio.fixture
async def fake_amap(monkeypatch):
    """让所有 _amap_xxx / _test_xxx 函数都返回固定结果，避免真实网络请求。"""
    from app.api import maps as maps_module
    from app.schemas.map_config import MapTestSubResult

    async def fake_test_server_key(server_key: str) -> MapTestSubResult:
        if server_key.startswith("OK_"):
            return MapTestSubResult(status="ok", detail="正常（地理编码）")
        if not server_key:
            return MapTestSubResult(status="fail", detail="未配置 Server Key")
        return MapTestSubResult(status="fail", detail="失败：INVALID_USER_KEY（错误码 10001）")

    async def fake_test_js_key(js_key: str, key_label: str) -> MapTestSubResult:
        if js_key.startswith("OK_"):
            return MapTestSubResult(status="ok", detail="正常（脚本加载）")
        if not js_key:
            return MapTestSubResult(status="fail", detail=f"未配置 {key_label}")
        return MapTestSubResult(status="fail", detail="失败：INVALID_USER_KEY")

    monkeypatch.setattr(maps_module, "_test_server_key", fake_test_server_key)
    monkeypatch.setattr(maps_module, "_test_js_key", fake_test_js_key)
    yield


# ──────── 测试 ────────


@pytest.mark.asyncio
async def test_get_map_config_no_record(client: AsyncClient, admin_headers):
    """初始状态下数据库无记录，has_record=False，仍能返回环境变量回填值。"""
    res = await client.get("/api/admin/map-config", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["has_record"] is False
    assert body["provider"] == "amap"
    assert body["default_zoom"] == 12
    assert body["default_city"] == "北京"


@pytest.mark.asyncio
async def test_put_map_config_missing_keys_400(client: AsyncClient, admin_headers):
    """3 个必填 Key 缺一应 400。"""
    res = await client.put(
        "/api/admin/map-config",
        json={
            "provider": "amap",
            "server_key": "",
            "web_js_key": "abc",
            "h5_js_key": "def",
        },
        headers=admin_headers,
    )
    assert res.status_code == 400
    assert "Server Key" in res.json()["detail"]


@pytest.mark.asyncio
async def test_put_map_config_invalid_coord(client: AsyncClient, admin_headers):
    res = await client.put(
        "/api/admin/map-config",
        json={
            "server_key": "k1",
            "web_js_key": "k2",
            "h5_js_key": "k3",
            "default_center_lng": 999,
            "default_center_lat": 39.0,
            "default_zoom": 12,
        },
        headers=admin_headers,
    )
    assert res.status_code == 422 or res.status_code == 400


@pytest.mark.asyncio
async def test_put_map_config_zoom_out_of_range(client: AsyncClient, admin_headers):
    res = await client.put(
        "/api/admin/map-config",
        json={
            "server_key": "k1",
            "web_js_key": "k2",
            "h5_js_key": "k3",
            "default_zoom": 25,
        },
        headers=admin_headers,
    )
    assert res.status_code == 422 or res.status_code == 400


@pytest.mark.asyncio
async def test_put_then_get_roundtrip(client: AsyncClient, admin_headers):
    """正常保存后立即再 GET，应取回保存的配置。"""
    payload = {
        "provider": "amap",
        "server_key": "OK_SERVER_K",
        "web_js_key": "OK_WEB_K",
        "h5_js_key": "OK_H5_K",
        "security_js_code": "SCODE_X",
        "default_city": "上海",
        "default_center_lng": 121.4737,
        "default_center_lat": 31.2304,
        "default_zoom": 14,
    }
    res = await client.put("/api/admin/map-config", json=payload, headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["has_record"] is True
    assert body["server_key"] == "OK_SERVER_K"
    assert body["default_city"] == "上海"

    res2 = await client.get("/api/admin/map-config", headers=admin_headers)
    body2 = res2.json()
    assert body2["has_record"] is True
    assert body2["server_key"] == "OK_SERVER_K"
    assert body2["web_js_key"] == "OK_WEB_K"
    assert abs(body2["default_center_lng"] - 121.4737) < 1e-4
    assert body2["default_zoom"] == 14


@pytest.mark.asyncio
async def test_put_idempotent_single_row(client: AsyncClient, admin_headers):
    """多次 PUT 始终更新单行，不会插入第二行。"""
    payload = {
        "server_key": "K1",
        "web_js_key": "K2",
        "h5_js_key": "K3",
    }
    for _ in range(3):
        res = await client.put("/api/admin/map-config", json=payload, headers=admin_headers)
        assert res.status_code == 200, res.text

    async with test_session() as s:
        rows = (await s.execute(select(MapConfig))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_test_connection_writes_log_and_logs_listing(
    client: AsyncClient, admin_headers, fake_amap
):
    """测试连接 + 查看测试历史。"""
    # 先写一份配置
    await client.put(
        "/api/admin/map-config",
        json={
            "server_key": "OK_S",
            "web_js_key": "OK_W",
            "h5_js_key": "BAD_H5",  # 故意失败
        },
        headers=admin_headers,
    )

    res = await client.post("/api/admin/map-config/test", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["server"]["status"] == "ok"
    assert body["web"]["status"] == "ok"
    assert body["h5"]["status"] == "fail"
    assert body["overall_pass"] is False

    # 测试日志已写入
    logs_res = await client.get("/api/admin/map-config/test-logs", headers=admin_headers)
    items = logs_res.json()["items"]
    assert len(items) == 1
    assert items[0]["server_status"] == "ok"
    assert items[0]["overall_pass"] is False

    # 再做一次全 OK 测试，日志总数累加且按时间倒序
    await client.put(
        "/api/admin/map-config",
        json={"server_key": "OK_S", "web_js_key": "OK_W", "h5_js_key": "OK_H"},
        headers=admin_headers,
    )
    await client.post("/api/admin/map-config/test", headers=admin_headers)
    logs_res2 = await client.get("/api/admin/map-config/test-logs", headers=admin_headers)
    items2 = logs_res2.json()["items"]
    assert len(items2) == 2
    assert items2[0]["overall_pass"] is True  # 最新在前


@pytest.mark.asyncio
async def test_geo_config_reads_db_after_save(client: AsyncClient, admin_headers):
    """保存后 /api/maps/geo-config 公开接口立即返回数据库的值（即配即生效）。"""
    await client.put(
        "/api/admin/map-config",
        json={
            "server_key": "S_KEY_DB",
            "web_js_key": "WEB_KEY_DB",
            "h5_js_key": "H5_KEY_DB",
            "default_city": "深圳",
            "default_center_lng": 114.0579,
            "default_center_lat": 22.5431,
            "default_zoom": 13,
        },
        headers=admin_headers,
    )

    res = await client.get("/api/maps/geo-config")
    assert res.status_code == 200
    body = res.json()
    assert body["web_js_key"] == "WEB_KEY_DB"
    assert body["h5_js_key"] == "H5_KEY_DB"
    assert body["has_server_key"] is True
    assert body["default_city"] == "深圳"
    assert body["default_zoom"] == 13


@pytest.mark.asyncio
async def test_admin_endpoints_require_auth(client: AsyncClient):
    """无 token 访问 admin 接口应被拒绝。"""
    r1 = await client.get("/api/admin/map-config")
    assert r1.status_code in (401, 403)
    r2 = await client.put(
        "/api/admin/map-config",
        json={"server_key": "x", "web_js_key": "y", "h5_js_key": "z"},
    )
    assert r2.status_code in (401, 403)
    r3 = await client.post("/api/admin/map-config/test")
    assert r3.status_code in (401, 403)
    r4 = await client.get("/api/admin/map-config/test-logs")
    assert r4.status_code in (401, 403)


@pytest.mark.asyncio
async def test_copy_domain_endpoint(client: AsyncClient, admin_headers):
    """复制当前域名辅助接口：能从 Origin/Host 头中提取域名。"""
    res = await client.get(
        "/api/admin/map-config/copy-domain",
        headers={**admin_headers, "Origin": "https://admin.example.com"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["web_admin_origin"].endswith("admin.example.com")


@pytest.mark.asyncio
async def test_static_map_uses_db_key(client: AsyncClient, admin_headers):
    """保存高德 Server Key 后，静态地图 URL 切换到 amap 提供商。"""
    res0 = await client.get("/api/maps/static-map?lat=23.0&lng=113.0&zoom=14")
    assert res0.status_code == 200
    # 没有 Key 时应该走 osm
    assert res0.json()["provider"] == "osm"

    await client.put(
        "/api/admin/map-config",
        json={"server_key": "AMAP_S", "web_js_key": "W", "h5_js_key": "H"},
        headers=admin_headers,
    )
    res1 = await client.get("/api/maps/static-map?lat=23.0&lng=113.0&zoom=14")
    assert res1.status_code == 200
    body = res1.json()
    assert body["provider"] == "amap"
    assert "AMAP_S" in body["url"]
