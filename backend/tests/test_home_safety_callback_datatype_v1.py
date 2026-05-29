"""[BUGFIX HS-CALLBACK-DATATYPE 2026-05-29]
紧急呼叫器厂商回调 new-call-msg 兼容 & 回调原始流水"失败原因"治理 测试套件。

覆盖：
- TC-01：新版告警报文 dataType=new-call-msg → 走告警链路，data_type=new-call-msg, parse_status=ok
- TC-02：旧版告警报文兼容 dataType=call-msg → 走告警链路，data_type=call-msg, parse_status=ok
- TC-03：心跳报文 dataType=smb-real-time-msg → 不走告警，parse_status=ignored, parse_fail_reason=None
- TC-04：未知类型 dataType=foo-bar → parse_status=unsupported_type, parse_fail_reason 含"未识别 dataType"
- TC-05：管理后台流水列表返回 data_type 字段且支持筛选
- TC-06：alertState/voltageState 不入业务（只检查不出错）
- TC-07：详情接口包含 data_type
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_callback_new_call_msg_treated_as_alert(client: AsyncClient, auth_headers):
    """TC-01：dataType=new-call-msg 与 call-msg 同样走告警链路，并落库 data_type=new-call-msg。"""
    # 绑定设备
    await client.post(
        "/api/home_safety/devices/bind",
        json={
            "device_type": 1,
            "gateway_sn": "GWNEW001",
            "emergency_phone": "13800001234",
            "device_sn": "NEWCM001",
        },
        headers=auth_headers,
    )
    payload = {
        "param": {
            "devId": "NEWCM001",
            "devType": "1",
            "occurTime": 1547100617645,
            "gwId": "GWNEW001",
            "devName": "卧室紧急按钮",
            "callType": 0,
            "alertState": 1,
            "voltageState": 2,
        },
        "dataType": "new-call-msg",
        "msgId": "VMSG_NEWCM_001",
    }
    r = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["code"] == 0
    assert j["created"] == 1

    # 校验流水：data_type=new-call-msg, parse_status=ok, parse_fail_reason 为空
    rsp = await client.get("/api/admin/home_safety/callback_log?size=200", headers=auth_headers)
    items = rsp.json()["items"]
    hits = [
        x for x in items
        if x.get("vendor_msg_id") == "VMSG_NEWCM_001"
        or (x.get("device_sn") == "NEWCM001" and x.get("data_type") == "new-call-msg")
    ]
    assert hits, "应能查询到 VMSG_NEWCM_001 的流水"
    log = hits[0]
    assert log["data_type"] == "new-call-msg"
    assert log["parse_status"] == "ok"
    assert not log.get("parse_fail_reason"), "成功流水的失败原因必须为空"


@pytest.mark.asyncio
async def test_callback_legacy_call_msg_still_supported(client: AsyncClient, auth_headers):
    """TC-02：旧版 dataType=call-msg 兼容继续走告警链路。"""
    await client.post(
        "/api/home_safety/devices/bind",
        json={
            "device_type": 1,
            "gateway_sn": "GWOLD001",
            "emergency_phone": "13800001234",
            "device_sn": "OLDCM001",
        },
        headers=auth_headers,
    )
    payload = {
        "param": {
            "devId": "OLDCM001",
            "devType": "1",
            "occurTime": 1547100617645,
            "gwId": "GWOLD001",
        },
        "dataType": "call-msg",
        "msgId": "VMSG_OLDCM_001",
    }
    r = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["code"] == 0
    assert j["created"] == 1

    rsp = await client.get("/api/admin/home_safety/callback_log?size=200", headers=auth_headers)
    items = rsp.json()["items"]
    hits = [x for x in items if x.get("vendor_msg_id") == "VMSG_OLDCM_001"]
    assert hits
    assert hits[0]["data_type"] == "call-msg"
    assert hits[0]["parse_status"] == "ok"
    assert not hits[0].get("parse_fail_reason")


@pytest.mark.asyncio
async def test_callback_heartbeat_marked_ignored_with_blank_reason(client: AsyncClient, auth_headers):
    """TC-03：心跳报文 dataType=smb-real-time-msg → parse_status=ignored，
    parse_fail_reason 必须为空（治理"失败原因"被心跳污染）。"""
    payload = {
        "param": {"devId": "HBDEV001", "devType": "1"},
        "dataType": "smb-real-time-msg",
        "msgId": "VMSG_HB_001",
    }
    r = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["code"] == 0
    assert j.get("ignored") is True

    rsp = await client.get(
        "/api/admin/home_safety/callback_log?size=200&data_type=smb-real-time-msg",
        headers=auth_headers,
    )
    items = rsp.json()["items"]
    assert items, "应能查询到心跳报文流水"
    # 找到本次推入的那条
    hb = [x for x in items if x.get("data_type") == "smb-real-time-msg"]
    assert hb, "data_type 必须为 smb-real-time-msg"
    # 所有 smb-real-time-msg 流水：状态必须是 ignored，失败原因必须为空
    for log in hb:
        assert log["parse_status"] == "ignored", f"心跳流水状态应为 ignored，实际 {log['parse_status']}"
        assert not log.get("parse_fail_reason"), (
            f"心跳流水失败原因必须为空，实际为 {log.get('parse_fail_reason')!r}"
        )


@pytest.mark.asyncio
async def test_callback_unknown_data_type_marked_unsupported(client: AsyncClient, auth_headers):
    """TC-04：未知 dataType → parse_status=unsupported_type，
    parse_fail_reason 必须包含"未识别 dataType"。"""
    payload = {
        "param": {"devId": "UNKDEV01", "devType": "1"},
        "dataType": "foo-bar",
        "msgId": "VMSG_UNK_001",
    }
    r = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r.status_code == 200, r.text

    rsp = await client.get("/api/admin/home_safety/callback_log?size=200", headers=auth_headers)
    items = rsp.json()["items"]
    hits = [x for x in items if x.get("data_type") == "foo-bar"]
    assert hits, "应能查询到未知 dataType 流水"
    log = hits[0]
    assert log["parse_status"] == "unsupported_type"
    assert "未识别 dataType" in (log.get("parse_fail_reason") or "")


@pytest.mark.asyncio
async def test_callback_log_list_supports_data_type_filter(client: AsyncClient, auth_headers):
    """TC-05：管理后台流水列表支持 data_type 筛选（4 个固定选项 + __other__）。"""
    # 准备 3 类报文 + 1 类其它
    await client.post(
        "/api/home_safety/devices/bind",
        json={
            "device_type": 1,
            "gateway_sn": "GWFLT001",
            "emergency_phone": "13800001234",
            "device_sn": "FLTDEV01",
        },
        headers=auth_headers,
    )
    payloads = [
        {"param": {"devId": "FLTDEV01", "devType": "1"}, "dataType": "new-call-msg", "msgId": "VMSG_FLT_NEW"},
        {"param": {"devId": "FLTDEV01", "devType": "1"}, "dataType": "call-msg", "msgId": "VMSG_FLT_OLD"},
        {"param": {"devId": "FLTDEV01"}, "dataType": "smb-real-time-msg", "msgId": "VMSG_FLT_HB"},
        {"param": {"devId": "FLTDEV01"}, "dataType": "xx-other-xx", "msgId": "VMSG_FLT_OTHER"},
    ]
    for p in payloads:
        await client.post("/api/home_safety/callback/alarm", json=p)

    # new-call-msg 筛选
    r1 = await client.get(
        "/api/admin/home_safety/callback_log?size=200&data_type=new-call-msg",
        headers=auth_headers,
    )
    items1 = r1.json()["items"]
    assert items1
    assert all(x["data_type"] == "new-call-msg" for x in items1)

    # call-msg 筛选
    r2 = await client.get(
        "/api/admin/home_safety/callback_log?size=200&data_type=call-msg",
        headers=auth_headers,
    )
    items2 = r2.json()["items"]
    assert items2
    assert all(x["data_type"] == "call-msg" for x in items2)

    # smb-real-time-msg 筛选
    r3 = await client.get(
        "/api/admin/home_safety/callback_log?size=200&data_type=smb-real-time-msg",
        headers=auth_headers,
    )
    items3 = r3.json()["items"]
    assert items3
    assert all(x["data_type"] == "smb-real-time-msg" for x in items3)

    # 其它（__other__）筛选：应当至少能命中 xx-other-xx
    r4 = await client.get(
        "/api/admin/home_safety/callback_log?size=200&data_type=__other__",
        headers=auth_headers,
    )
    items4 = r4.json()["items"]
    KNOWN = {"new-call-msg", "call-msg", "smb-real-time-msg"}
    assert items4
    for x in items4:
        assert x["data_type"] not in KNOWN and x["data_type"] is not None


@pytest.mark.asyncio
async def test_callback_alertstate_voltagestate_not_in_business(client: AsyncClient, auth_headers):
    """TC-06：alertState/voltageState 仅保留在 raw_body 中，不影响业务流程。"""
    await client.post(
        "/api/home_safety/devices/bind",
        json={
            "device_type": 1,
            "gateway_sn": "GWAVS001",
            "emergency_phone": "13800001234",
            "device_sn": "AVSDEV01",
        },
        headers=auth_headers,
    )
    payload = {
        "param": {
            "devId": "AVSDEV01",
            "devType": "1",
            "occurTime": 1547100617645,
            "alertState": 9,  # 任意值
            "voltageState": 42,
        },
        "dataType": "new-call-msg",
        "msgId": "VMSG_AVS_001",
    }
    r = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r.status_code == 200
    j = r.json()
    assert j["code"] == 0
    assert j["created"] == 1

    # 流水 raw_body 应包含 alertState
    rsp = await client.get("/api/admin/home_safety/callback_log?size=200", headers=auth_headers)
    items = rsp.json()["items"]
    hits = [x for x in items if x.get("vendor_msg_id") == "VMSG_AVS_001"]
    assert hits
    # 取详情确认 raw body 含 alertState
    log_id = hits[0]["id"]
    detail = await client.get(
        f"/api/admin/home_safety/callback_log/{log_id}", headers=auth_headers
    )
    d = detail.json()
    assert "alertState" in (d.get("request_body") or "")
    assert "voltageState" in (d.get("request_body") or "")


@pytest.mark.asyncio
async def test_callback_log_detail_contains_data_type(client: AsyncClient, auth_headers):
    """TC-07：流水详情接口返回 data_type 字段。"""
    payload = {
        "param": {"devId": "DTLDEV01"},
        "dataType": "smb-real-time-msg",
        "msgId": "VMSG_DTL_001",
    }
    await client.post("/api/home_safety/callback/alarm", json=payload)
    rsp = await client.get(
        "/api/admin/home_safety/callback_log?size=200&data_type=smb-real-time-msg",
        headers=auth_headers,
    )
    items = rsp.json()["items"]
    assert items
    log_id = items[0]["id"]
    detail = await client.get(
        f"/api/admin/home_safety/callback_log/{log_id}", headers=auth_headers
    )
    d = detail.json()
    assert "data_type" in d
    assert d["data_type"] == "smb-real-time-msg"
