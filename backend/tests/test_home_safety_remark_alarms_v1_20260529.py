"""[BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29]
居家安全 - 设备备注 + 报警记录字段 + 公共成员 Tab 数据源 测试。

覆盖：
- 绑定时 remark 必填校验（empty/missing → 400 remark_required）
- 绑定时 remark > 20 字 → 400 remark_too_long
- 绑定时 remark 仅空白 → 400 remark_required
- PATCH /devices/{id}/remark 单独修改设备备注
- list_my_devices 响应包含 remark 字段
- /api/home_safety/alarms 响应包含 device_remark、notify_phone_mask、total 字段
- /api/home_safety/members 仍可用且响应包含 deprecated=True 标记
- /api/admin/home_safety/bindings 包含 remark 字段
- /api/admin/home_safety/alarms 包含 device_remark 字段
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


def _bind_body(**overrides):
    base = {
        "device_type": 1,
        "gateway_sn": "REMK0001",
        "device_sn": "REMK0001",
        "emergency_phone": "13800001234",
        "remark": "客厅紧急呼叫器",
    }
    base.update(overrides)
    return base


# ============== 1. remark 必填校验 ==============
@pytest.mark.asyncio
async def test_bind_remark_required_missing(client: AsyncClient, auth_headers):
    """绑定时未传 remark → 400 remark_required"""
    body = _bind_body()
    body.pop("remark")
    body["device_sn"] = "REMKMISS"
    body["gateway_sn"] = "REMKMISS"
    rsp = await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    assert rsp.status_code == 400, rsp.text
    assert "remark_required" in rsp.text


@pytest.mark.asyncio
async def test_bind_remark_required_empty(client: AsyncClient, auth_headers):
    """绑定时 remark 为空字符串 → 400 remark_required"""
    body = _bind_body(remark="", device_sn="REMKEMP1", gateway_sn="REMKEMP1")
    rsp = await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    assert rsp.status_code == 400, rsp.text
    assert "remark_required" in rsp.text


@pytest.mark.asyncio
async def test_bind_remark_required_blank(client: AsyncClient, auth_headers):
    """绑定时 remark 仅空白 → 400 remark_required"""
    body = _bind_body(remark="     ", device_sn="REMKBLN1", gateway_sn="REMKBLN1")
    rsp = await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    assert rsp.status_code == 400, rsp.text
    assert "remark_required" in rsp.text


@pytest.mark.asyncio
async def test_bind_remark_too_long(client: AsyncClient, auth_headers):
    """绑定时 remark > 20 字 → 400 remark_too_long"""
    body = _bind_body(
        remark="a" * 21,
        device_sn="REMKLNG1",
        gateway_sn="REMKLNG1",
    )
    rsp = await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    assert rsp.status_code == 400, rsp.text
    assert "remark_too_long" in rsp.text


# ============== 2. 绑定 + 响应字段 ==============
@pytest.mark.asyncio
async def test_bind_returns_remark_in_response(client: AsyncClient, auth_headers):
    """绑定成功后响应包含 remark 字段"""
    body = _bind_body(
        device_sn="REMKOK01",
        gateway_sn="REMKOK01",
        remark="爸爸家",
    )
    rsp = await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    assert rsp.status_code == 200, rsp.text
    data = rsp.json()
    assert data.get("remark") == "爸爸家"


@pytest.mark.asyncio
async def test_devices_list_contains_remark(client: AsyncClient, auth_headers):
    """list_my_devices 响应分组项含 remark 字段"""
    body = _bind_body(
        device_sn="REMKLST1",
        gateway_sn="REMKLST1",
        remark="客厅设备",
    )
    await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    rsp_m = await client.get("/api/home_safety/members", headers=auth_headers)
    self_id = next(m["id"] for m in rsp_m.json()["items"] if m["is_self"])
    rsp = await client.get(
        f"/api/home_safety/devices?member_id={self_id}", headers=auth_headers
    )
    assert rsp.status_code == 200, rsp.text
    groups = rsp.json()["groups"]
    found = False
    for g in groups:
        for it in g.get("items", []):
            if it["device_sn"] == "REMKLST1":
                assert it.get("remark") == "客厅设备"
                found = True
                break
    assert found, "新绑定的设备未在列表中找到"


# ============== 3. PATCH /devices/{id}/remark ==============
@pytest.mark.asyncio
async def test_patch_device_remark_success(client: AsyncClient, auth_headers):
    """PATCH /devices/{id}/remark 可单独修改备注"""
    body = _bind_body(
        device_sn="REMKPCH1",
        gateway_sn="REMKPCH1",
        remark="老备注",
    )
    rb = await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    bid = rb.json()["id"]

    rsp = await client.patch(
        f"/api/home_safety/devices/{bid}/remark",
        json={"remark": "新备注"},
        headers=auth_headers,
    )
    assert rsp.status_code == 200, rsp.text
    assert rsp.json().get("remark") == "新备注"


@pytest.mark.asyncio
async def test_patch_device_remark_too_long(client: AsyncClient, auth_headers):
    """PATCH 备注 > 20 字 → 400 remark_too_long"""
    body = _bind_body(
        device_sn="REMKPLN1",
        gateway_sn="REMKPLN1",
        remark="正常备注",
    )
    rb = await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    bid = rb.json()["id"]
    rsp = await client.patch(
        f"/api/home_safety/devices/{bid}/remark",
        json={"remark": "x" * 25},
        headers=auth_headers,
    )
    assert rsp.status_code == 400, rsp.text
    assert "remark_too_long" in rsp.text


@pytest.mark.asyncio
async def test_patch_device_remark_not_found(client: AsyncClient, auth_headers):
    """PATCH 不存在的设备 → 404"""
    rsp = await client.patch(
        "/api/home_safety/devices/99999999/remark",
        json={"remark": "x"},
        headers=auth_headers,
    )
    assert rsp.status_code == 404, rsp.text


# ============== 4. /alarms 响应字段 ==============
@pytest.mark.asyncio
async def test_alarms_response_contains_new_fields(client: AsyncClient, auth_headers):
    """/api/home_safety/alarms 响应包含 device_remark、member_name、notify_phone_mask、total 字段"""
    # 1) 绑定一个设备
    body = _bind_body(
        device_sn="REMKAL01",
        gateway_sn="REMKAL01",
        remark="测试告警备注",
    )
    await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    # 2) 模拟厂商回调，制造一条告警
    cb = await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "MSGREMKAL01",
            "dataType": "new-call-msg",
            "param": {
                "devId": "REMKAL01",
                "devType": "1",
                "occurTime": 1900000000000,
                "gwId": "REMKAL01",
            },
        },
    )
    assert cb.status_code == 200, cb.text

    rsp = await client.get(
        "/api/home_safety/alarms?page=1&size=20", headers=auth_headers
    )
    assert rsp.status_code == 200, rsp.text
    data = rsp.json()
    # 包含 total 字段
    assert "total" in data
    assert "page" in data
    assert "size" in data
    items = data["items"]
    target = next((it for it in items if it["device_sn"] == "REMKAL01"), None)
    assert target is not None, "新告警未出现在列表中"
    # 新字段
    assert "device_remark" in target
    assert target["device_remark"] == "测试告警备注"
    assert "notify_phone_mask" in target
    assert "member_id" in target


# ============== 5. /members 接口标记 deprecated ==============
@pytest.mark.asyncio
async def test_home_safety_members_marked_deprecated(client: AsyncClient, auth_headers):
    """旧 /api/home_safety/members 仍可用并标记 deprecated=True"""
    rsp = await client.get("/api/home_safety/members", headers=auth_headers)
    assert rsp.status_code == 200, rsp.text
    data = rsp.json()
    assert data.get("deprecated") is True
    assert data.get("replaced_by") == "/api/family/members"


# ============== 6. admin/home_safety/bindings 包含 remark ==============
@pytest.mark.asyncio
async def test_admin_bindings_includes_remark(client: AsyncClient, auth_headers):
    """管理后台 bindings 响应包含 remark 字段"""
    body = _bind_body(
        device_sn="REMKADM1",
        gateway_sn="REMKADM1",
        remark="管理后台测试",
    )
    await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    rsp = await client.get("/api/admin/home_safety/bindings", headers=auth_headers)
    assert rsp.status_code == 200, rsp.text
    items = rsp.json()["items"]
    target = next((it for it in items if it["device_sn"] == "REMKADM1"), None)
    assert target is not None
    assert "remark" in target
    assert target["remark"] == "管理后台测试"


# ============== 7. admin/home_safety/alarms 包含 device_remark ==============
@pytest.mark.asyncio
async def test_admin_alarms_includes_device_remark(client: AsyncClient, auth_headers):
    """管理后台 alarms 响应包含 device_remark 字段"""
    body = _bind_body(
        device_sn="REMKAA01",
        gateway_sn="REMKAA01",
        remark="后台告警备注",
    )
    await client.post(
        "/api/home_safety/devices/bind", json=body, headers=auth_headers
    )
    # 制造告警
    cb = await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "MSGADMREMKAA01",
            "dataType": "new-call-msg",
            "param": {
                "devId": "REMKAA01",
                "devType": "1",
                "occurTime": 1900000001000,
                "gwId": "REMKAA01",
            },
        },
    )
    assert cb.status_code == 200, cb.text

    rsp = await client.get("/api/admin/home_safety/alarms", headers=auth_headers)
    assert rsp.status_code == 200, rsp.text
    items = rsp.json()["items"]
    target = next((it for it in items if it["device_sn"] == "REMKAA01"), None)
    assert target is not None
    assert "device_remark" in target
    assert target["device_remark"] == "后台告警备注"
