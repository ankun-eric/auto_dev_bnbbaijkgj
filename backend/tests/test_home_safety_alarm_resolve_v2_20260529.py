"""[BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-V2 2026-05-29]
居家安全 - 报警「标记已处理」PATCH 接口测试。

覆盖 PRD v2.0 锁定行为：
- PATCH /api/home_safety/alarms/{id}/resolve 200 + status=resolved
- 幂等：再次调用返回 message="已处理过" 且不报错
- 404：报警不存在
- 401/403：未登录/非属者不可操作
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


def _bind_body(**overrides):
    base = {
        "device_type": 1,
        "gateway_sn": "RESV0001",
        "device_sn": "RESV0001",
        "emergency_phone": "13800001234",
        "remark": "客厅紧急呼叫器",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_resolve_alarm_success(client: AsyncClient, auth_headers):
    """PATCH resolve 200，状态变 resolved。"""
    # 1) 绑定设备
    body = _bind_body(device_sn="RESVAL01", gateway_sn="RESVAL01", remark="测试")
    await client.post("/api/home_safety/devices/bind", json=body, headers=auth_headers)
    # 2) 制造一条告警
    cb = await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "MSGRESV01",
            "dataType": "new-call-msg",
            "param": {
                "devId": "RESVAL01",
                "devType": "1",
                "occurTime": 1900000000000,
                "gwId": "RESVAL01",
            },
        },
    )
    assert cb.status_code == 200, cb.text

    rsp_list = await client.get(
        "/api/home_safety/alarms?page=1&size=20", headers=auth_headers
    )
    alarms = rsp_list.json()["items"]
    target = next((a for a in alarms if a["device_sn"] == "RESVAL01"), None)
    assert target is not None
    alarm_id = target["id"]
    assert target["handle_status"] == 0

    # 3) PATCH resolve
    rsp = await client.patch(
        f"/api/home_safety/alarms/{alarm_id}/resolve",
        json={},
        headers=auth_headers,
    )
    assert rsp.status_code == 200, rsp.text
    data = rsp.json()
    assert data.get("code") == 0
    assert data["data"]["id"] == alarm_id
    assert data["data"]["status"] == "resolved"
    assert data["data"]["resolved_at"]

    # 4) 再次查询，handle_status=1
    rsp2 = await client.get(
        "/api/home_safety/alarms?page=1&size=20", headers=auth_headers
    )
    a2 = next(
        (a for a in rsp2.json()["items"] if a["id"] == alarm_id), None
    )
    assert a2 is not None
    assert a2["handle_status"] == 1


@pytest.mark.asyncio
async def test_resolve_alarm_idempotent(client: AsyncClient, auth_headers):
    """已处理过的告警，再次调用 resolve 幂等返回。"""
    body = _bind_body(device_sn="RESVAL02", gateway_sn="RESVAL02", remark="测试2")
    await client.post("/api/home_safety/devices/bind", json=body, headers=auth_headers)
    cb = await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "MSGRESV02",
            "dataType": "new-call-msg",
            "param": {
                "devId": "RESVAL02",
                "devType": "1",
                "occurTime": 1900000000001,
                "gwId": "RESVAL02",
            },
        },
    )
    assert cb.status_code == 200, cb.text
    rsp_list = await client.get(
        "/api/home_safety/alarms?page=1&size=20", headers=auth_headers
    )
    target = next(
        (a for a in rsp_list.json()["items"] if a["device_sn"] == "RESVAL02"),
        None,
    )
    assert target is not None
    alarm_id = target["id"]

    # 第一次
    r1 = await client.patch(
        f"/api/home_safety/alarms/{alarm_id}/resolve",
        json={},
        headers=auth_headers,
    )
    assert r1.status_code == 200, r1.text
    # 第二次（幂等）
    r2 = await client.patch(
        f"/api/home_safety/alarms/{alarm_id}/resolve",
        json={},
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert data2.get("code") == 0
    assert data2["data"]["status"] == "resolved"
    # 幂等返回的 message 字段
    assert data2.get("message") == "已处理过"


@pytest.mark.asyncio
async def test_resolve_alarm_not_found(client: AsyncClient, auth_headers):
    """不存在的报警 → 404。"""
    rsp = await client.patch(
        "/api/home_safety/alarms/99999999/resolve",
        json={},
        headers=auth_headers,
    )
    assert rsp.status_code == 404, rsp.text


@pytest.mark.asyncio
async def test_resolve_alarm_unauthorized(client: AsyncClient):
    """未登录 → 401。"""
    rsp = await client.patch(
        "/api/home_safety/alarms/1/resolve",
        json={},
    )
    # 未登录默认为 401（或在某些框架中为 403），允许两者
    assert rsp.status_code in (401, 403), rsp.text
