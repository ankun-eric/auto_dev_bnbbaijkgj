"""[PRD-HOME-SAFETY-DEVICE-STATS-V1 2026-06-02] 居家安全设备-设备统计卡片

验收点：
- GET /api/home_safety/devices 返回 total_bound 与 type_counts（emergency/smoke/water）
- 空数据时 total_bound=0，三类计数均为 0
- 绑定不同类型设备后，total_bound 与对应分类计数随之增加
- total_bound 计入所有类型设备之和（含未单列类型，可能大于三分类之和）
- 解绑后统计实时回落
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


def _root(j: dict) -> dict:
    return j.get("data", j) if isinstance(j, dict) else j


@pytest.mark.asyncio
async def test_stats_empty_member(client: AsyncClient, auth_headers):
    """空数据：total_bound=0，三分类均为 0。"""
    r = await client.get("/api/home_safety/devices", headers=auth_headers)
    assert r.status_code == 200, r.text
    j = _root(r.json())
    assert j["total_bound"] == 0
    assert j["type_counts"] == {"emergency": 0, "smoke": 0, "water": 0}


@pytest.mark.asyncio
async def test_stats_after_bind(client: AsyncClient, auth_headers):
    """绑定 1 紧急 + 1 烟雾 + 1 水浸 → total_bound=3，各分类各 1。"""
    binds = [
        {"device_type": 1, "gateway_sn": "GWAA1111", "device_sn": "DEVAA111", "emergency_phone": "13800001234", "remark": "客厅"},
        {"device_type": 2, "gateway_sn": "GWBB2222", "device_sn": "DEVBB222", "emergency_phone": "13800001234", "remark": "厨房"},
        {"device_type": 7, "gateway_sn": "GWCC3333", "device_sn": "DEVCC333", "emergency_phone": "13800001234", "remark": "卫生间"},
    ]
    for b in binds:
        rb = await client.post("/api/home_safety/devices/bind", json=b, headers=auth_headers)
        assert rb.status_code == 200, rb.text

    r = await client.get("/api/home_safety/devices", headers=auth_headers)
    j = _root(r.json())
    assert j["total_bound"] == 3
    assert j["type_counts"]["emergency"] == 1
    assert j["type_counts"]["smoke"] == 1
    assert j["type_counts"]["water"] == 1


@pytest.mark.asyncio
async def test_stats_total_ge_category_sum(client: AsyncClient, auth_headers):
    """total_bound 等于所有类型设备之和；三分类计数与各类型实际数一致。"""
    binds = [
        {"device_type": 1, "gateway_sn": "GWD11111", "device_sn": "DEVD1111", "emergency_phone": "13800001234", "remark": "卧室1"},
        {"device_type": 1, "gateway_sn": "GWD22222", "device_sn": "DEVD2222", "emergency_phone": "13800001234", "remark": "卧室2"},
        {"device_type": 2, "gateway_sn": "GWD33333", "device_sn": "DEVD3333", "emergency_phone": "13800001234", "remark": "阳台"},
    ]
    for b in binds:
        rb = await client.post("/api/home_safety/devices/bind", json=b, headers=auth_headers)
        assert rb.status_code == 200, rb.text

    r = await client.get("/api/home_safety/devices", headers=auth_headers)
    j = _root(r.json())
    tc = j["type_counts"]
    assert tc["emergency"] == 2
    assert tc["smoke"] == 1
    assert tc["water"] == 0
    # total_bound 至少等于三分类之和
    assert j["total_bound"] >= tc["emergency"] + tc["smoke"] + tc["water"]
    assert j["total_bound"] == 3


@pytest.mark.asyncio
async def test_stats_after_unbind(client: AsyncClient, auth_headers):
    """解绑一台后统计实时回落。"""
    rb = await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 1, "gateway_sn": "GWE11111", "device_sn": "DEVE1111", "emergency_phone": "13800001234", "remark": "门口"},
        headers=auth_headers,
    )
    assert rb.status_code == 200, rb.text

    r1 = _root((await client.get("/api/home_safety/devices", headers=auth_headers)).json())
    assert r1["total_bound"] >= 1
    # 取一个设备 id
    dev_id = None
    for g in r1["groups"]:
        if g["items"]:
            dev_id = g["items"][0]["id"]
            break
    assert dev_id is not None

    before = r1["total_bound"]
    ru = await client.post(f"/api/home_safety/devices/{dev_id}/unbind", headers=auth_headers)
    assert ru.status_code == 200, ru.text

    r2 = _root((await client.get("/api/home_safety/devices", headers=auth_headers)).json())
    assert r2["total_bound"] == before - 1
