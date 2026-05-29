"""[PRD-HOME-SAFETY-V2 2026-05-27] 居家安全设备外部 API 对接 v2 测试套件

覆盖：
- F1~F7 后台回调地址配置 Tab：字段拆分、保存、推送历史等
- F8~F11 后端回调接收：字段映射、永久幂等、来源 IP、8 大异常兜底
- F12 AI 外呼降级
- F13 push_upstream 真实 HTTP 调用（通过注入 mock）
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.api import home_safety_v1


# ────────────── F8 字段映射 + F10 来源 IP ──────────────
@pytest.mark.asyncio
async def test_v2_vendor_payload_field_mapping(client: AsyncClient, auth_headers):
    """[F8] 厂商真实报文 → 内部字段映射全部正确落库"""
    # 先绑定设备
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 1, "gateway_sn": "GW123456", "emergency_phone": "13800001234", "remark": "测试备注", "device_sn": "00084bd7"},
        headers=auth_headers,
    )
    # 发送厂商真实报文
    vendor_payload = {
        "param": {
            "devId": "00084bd7",
            "devType": "1",
            "occurTime": 1547100617645,
            "gwId": "AC000397",
            "devName": "客厅紧急按钮",
            "callType": 0,
        },
        "dataType": "call-msg",
        "msgId": "VMSG_FIELD_MAP_001",
    }
    r = await client.post(
        "/api/home_safety/callback/alarm",
        json=vendor_payload,
        headers={"X-Real-IP": "203.0.113.45"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["code"] == 0
    assert j["created"] == 1

    # 在管理后台查询，校验所有字段
    rsp = await client.get("/api/admin/home_safety/alarms", headers=auth_headers)
    items = rsp.json()["items"]
    hits = [x for x in items if x.get("vendor_msg_id") == "VMSG_FIELD_MAP_001"]
    assert hits, "应能查询到 VMSG_FIELD_MAP_001"
    a = hits[0]
    assert a["device_sn"] == "00084bd7"
    assert a["device_type"] == 1
    assert a["gw_id"] == "AC000397"
    assert a["dev_name"] == "客厅紧急按钮"
    assert a["call_type"] == 0
    assert a["data_type"] == "call-msg"
    assert a["source_ip"] == "203.0.113.45"
    # AI 外呼降级
    assert a["notify_ai_call_status"] == "failed"
    assert "本期未对接" in (a["notify_ai_call_fail_reason"] or "")


# ────────────── F9 永久幂等 ──────────────
@pytest.mark.asyncio
async def test_v2_idempotent_by_vendor_msg_id(client: AsyncClient, auth_headers):
    """[F9] msgId 重复推送 → 直接返回 200，不重复落库"""
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 2, "gateway_sn": "GWIDEMP1", "emergency_phone": "13800001234", "remark": "测试备注", "device_sn": "IDEMP001"},
        headers=auth_headers,
    )
    payload = {
        "param": {"devId": "IDEMP001", "devType": "2", "occurTime": 1547100617645, "gwId": "GWIDEMP000001"},
        "dataType": "call-msg",
        "msgId": "MSG_DUP_KEY_001",
    }
    r1 = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r1.status_code == 200
    assert r1.json()["created"] == 1

    r2 = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r2.status_code == 200
    j = r2.json()
    assert j["code"] == 0
    # 幂等：不再产生新 created
    assert j.get("created", 0) == 0 or j.get("matched", 0) == 0


# ────────────── F11 异常场景 ──────────────
@pytest.mark.asyncio
async def test_v2_unsupported_data_type(client: AsyncClient, auth_headers):
    """[F11 异常 2] dataType 不支持 → 落日志，跳过业务处理，返回 200"""
    payload = {
        "param": {"devId": "ANY12345", "devType": "1", "occurTime": 1547100617645},
        "dataType": "heartbeat",  # 不支持
        "msgId": "MSG_UNSUP_001",
    }
    r = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r.status_code == 200
    assert r.json()["code"] == 0


@pytest.mark.asyncio
async def test_v2_unknown_dev_type(client: AsyncClient, auth_headers):
    """[F11 异常 3] devType 不在 {1,2,7} → 返回 200，落异常日志"""
    payload = {
        "param": {"devId": "ANY12345", "devType": "99", "occurTime": 1547100617645},
        "dataType": "call-msg",
        "msgId": "MSG_BADDEVTYPE_001",
    }
    r = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_v2_unbound_device(client: AsyncClient):
    """[F11 异常 4] devId 未绑定 → 返回 200，不触发通知"""
    payload = {
        "param": {"devId": "NOBODY01", "devType": "1", "occurTime": 1547100617645},
        "dataType": "call-msg",
        "msgId": "MSG_UNBOUND_001",
    }
    r = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r.status_code == 200
    j = r.json()
    assert j["code"] == 0
    assert j.get("matched", 0) == 0


@pytest.mark.asyncio
async def test_v2_missing_dev_id(client: AsyncClient):
    """[F11 异常 6] 关键字段 devId 缺失 → 返回 200，落异常日志"""
    payload = {
        "param": {"devType": "1", "occurTime": 1547100617645},
        "dataType": "call-msg",
        "msgId": "MSG_NODEV_001",
    }
    r = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r.status_code == 200
    assert r.json()["code"] == 0


@pytest.mark.asyncio
async def test_v2_compat_flat_payload(client: AsyncClient, auth_headers):
    """v1 旧契约（扁平字段）仍能正确处理"""
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 7, "gateway_sn": "GWCOMPT1", "emergency_phone": "13800001234", "remark": "测试备注", "device_sn": "COMPAT01"},
        headers=auth_headers,
    )
    r = await client.post(
        "/api/home_safety/callback/alarm",
        json={"device_sn": "COMPAT01", "type": 7, "alarm_time": "2026-05-27T18:30:00"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["code"] == 0
    assert j["created"] == 1


# ────────────── F1, F4 配置 ──────────────
@pytest.mark.asyncio
async def test_v2_callback_config_url_split_fields(client: AsyncClient, auth_headers):
    """[F1] 配置字段拆分：upstream_base_url + upstream_path → 完整 URL 自动拼接"""
    body = {
        "org_id": "test_dept_001",
        "upstream_base_url": "http://119.3.169.29/",  # 末尾 /
        "upstream_path": "treatment/api/setMsgCallBackUrl",  # 无开头 /
        "auth_token": "eyJhbGciOiJIUzI1NiJ9.abcdef",
        "callback_domain": "https://test.example.com/",
    }
    r1 = await client.put("/api/admin/home_safety/callback_config", json=body, headers=auth_headers)
    assert r1.status_code == 200

    r2 = await client.get("/api/admin/home_safety/callback_config", headers=auth_headers)
    j = r2.json()
    # 完整 URL 应正确拼接（去除尾部 /，补开头 /）
    assert j["full_upstream_url"] == "http://119.3.169.29/treatment/api/setMsgCallBackUrl"
    assert j["full_callback_url"].endswith("/api/home_safety/callback/alarm")
    assert j["callback_path"] == "/api/home_safety/callback/alarm"
    assert j["org_id"] == "test_dept_001"
    # Token 密文展示
    assert j["auth_token_masked"]
    assert "****" in j["auth_token_masked"]


@pytest.mark.asyncio
async def test_v2_token_mask_query(client: AsyncClient, auth_headers):
    """[F7] Token 默认明文返回，mask_token=true 时不返回明文"""
    body = {
        "org_id": "dept_mask",
        "upstream_base_url": "http://up.example.com",
        "upstream_path": "/api/cb",
        "auth_token": "very_secret_token_value",
        "callback_domain": "https://cb.example.com",
    }
    await client.put("/api/admin/home_safety/callback_config", json=body, headers=auth_headers)
    r = await client.get(
        "/api/admin/home_safety/callback_config?mask_token=true", headers=auth_headers
    )
    j = r.json()
    assert j["auth_token"] is None
    assert "****" in (j["auth_token_masked"] or "")


# ────────────── F13 push_upstream 真实 HTTP（通过 mock 注入）──────────────
@pytest.mark.asyncio
async def test_v2_push_upstream_success(client: AsyncClient, auth_headers, monkeypatch):
    """[F13] push_upstream 成功路径：上游返回 code=0 → status=success，并写入推送历史"""

    async def fake_push(full_url, auth_token, dept_id, callback_url):
        # 校验出参契约
        assert full_url
        assert dept_id == "DEPT_PUSH_OK"
        assert callback_url
        return {
            "status": "success",
            "code": 0,
            "message": "ok",
            "raw": '{"code":0,"message":"ok"}',
        }

    monkeypatch.setattr(home_safety_v1, "_PUSH_UPSTREAM_OVERRIDE", fake_push)

    body = {
        "org_id": "DEPT_PUSH_OK",
        "upstream_base_url": "http://up.example.com",
        "upstream_path": "/treatment/api/setMsgCallBackUrl",
        "auth_token": "tk1",
        "callback_domain": "https://my.example.com",
    }
    await client.put("/api/admin/home_safety/callback_config", json=body, headers=auth_headers)

    r = await client.post("/api/admin/home_safety/callback_config/push_upstream", headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["success"] is True
    assert j["status"] == "success"
    assert j["pushed_url"].endswith("/api/home_safety/callback/alarm")

    # 推送历史
    r2 = await client.get(
        "/api/admin/home_safety/callback_config/push_history?limit=3", headers=auth_headers
    )
    items = r2.json()["items"]
    assert items, "应有推送历史"
    assert items[0]["status"] == "success"

    # 复位 override
    monkeypatch.setattr(home_safety_v1, "_PUSH_UPSTREAM_OVERRIDE", None)


@pytest.mark.asyncio
async def test_v2_push_upstream_timeout(client: AsyncClient, auth_headers, monkeypatch):
    """[F13 异常 1] push_upstream 超时 → status=fail，message 包含『超时』"""

    async def fake_push(full_url, auth_token, dept_id, callback_url):
        return {"status": "fail", "code": None, "message": "请求超时", "raw": ""}

    monkeypatch.setattr(home_safety_v1, "_PUSH_UPSTREAM_OVERRIDE", fake_push)

    body = {
        "org_id": "DEPT_TIMEOUT",
        "upstream_base_url": "http://up.example.com",
        "upstream_path": "/api/cb",
        "auth_token": "tk",
        "callback_domain": "https://my.example.com",
    }
    await client.put("/api/admin/home_safety/callback_config", json=body, headers=auth_headers)

    r = await client.post("/api/admin/home_safety/callback_config/push_upstream", headers=auth_headers)
    assert r.status_code == 200
    j = r.json()
    assert j["success"] is False
    assert j["status"] == "fail"
    assert "超时" in (j["message"] or "")

    monkeypatch.setattr(home_safety_v1, "_PUSH_UPSTREAM_OVERRIDE", None)


@pytest.mark.asyncio
async def test_v2_push_history_limit(client: AsyncClient, auth_headers, monkeypatch):
    """[F5] 推送历史 limit=3 仅返回最近 3 条"""

    async def fake_push(full_url, auth_token, dept_id, callback_url):
        return {"status": "success", "code": 0, "message": "ok", "raw": "{}"}

    monkeypatch.setattr(home_safety_v1, "_PUSH_UPSTREAM_OVERRIDE", fake_push)

    body = {
        "org_id": "DEPT_HIST",
        "upstream_base_url": "http://up.example.com",
        "upstream_path": "/api/cb",
        "auth_token": "tk",
        "callback_domain": "https://my.example.com",
    }
    await client.put("/api/admin/home_safety/callback_config", json=body, headers=auth_headers)

    for _ in range(5):
        await client.post("/api/admin/home_safety/callback_config/push_upstream", headers=auth_headers)

    r = await client.get(
        "/api/admin/home_safety/callback_config/push_history?limit=3", headers=auth_headers
    )
    assert len(r.json()["items"]) == 3

    monkeypatch.setattr(home_safety_v1, "_PUSH_UPSTREAM_OVERRIDE", None)


@pytest.mark.asyncio
async def test_v2_push_upstream_missing_config(client: AsyncClient, auth_headers):
    """[F13 异常 6] 配置字段缺失 → 不发起调用，返回 400"""
    # 不保存任何配置
    r = await client.post("/api/admin/home_safety/callback_config/push_upstream", headers=auth_headers)
    # 可能是 400（没有 cfg）或 400（配置不完整）
    assert r.status_code == 400


# ────────────── 兼容性：v2 路径不破坏 v1 测试 ──────────────
@pytest.mark.asyncio
async def test_v2_backward_compat_two_callback_paths(client: AsyncClient, auth_headers):
    """[兼容性] /api/home_safety/callback/alarm 和 /callback/home_safety/alarm 均可用"""
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 1, "gateway_sn": "GWBC1000", "emergency_phone": "13800001234", "remark": "测试备注", "device_sn": "BCPATH01"},
        headers=auth_headers,
    )
    # 路径 A
    r1 = await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "param": {"devId": "BCPATH01", "devType": "1", "occurTime": 1547100617645},
            "dataType": "call-msg",
            "msgId": "BCPATH_MSG_A",
        },
    )
    assert r1.status_code == 200
    assert r1.json()["code"] == 0
    # 路径 B
    r2 = await client.post(
        "/callback/home_safety/alarm",
        json={
            "param": {"devId": "BCPATH01", "devType": "1", "occurTime": 1547100617650},
            "dataType": "call-msg",
            "msgId": "BCPATH_MSG_B",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["code"] == 0
