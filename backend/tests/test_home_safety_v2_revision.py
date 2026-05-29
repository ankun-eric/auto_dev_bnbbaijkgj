"""[BUGFIX HOME-SAFETY-V2-REVISION 2026-05-28]
居家安全设备外部 API 对接 v2 修订版三个修复的测试套件。

修复 1：上游推送成功判定改为兼容白名单（修 Bug 1）
修复 2：回调流水"先写 pending → 业务后 update"两步模式（修 Bug 2 审计黑洞）
修复 3：回调地址自检接口（防止 Bug 2 再次发生）

新增审计接口：
- GET /api/admin/home_safety/callback_log
- GET /api/admin/home_safety/callback_log/{id}
- POST /api/admin/home_safety/callback_config/precheck
"""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


# ============== 修复 1：上游推送成功判定兼容白名单 ==============
# 注意：不能 monkeypatch httpx.AsyncClient 全局类，否则会拦截测试自身的 ASGITransport 客户端。
# 因此采用直接单元测试 _real_push_upstream 的判定逻辑（绕过 httpx），
# 同时通过 _PUSH_UPSTREAM_OVERRIDE 测试集成层 status 透传。


@pytest.mark.asyncio
async def test_push_success_with_code_200_message_success(client: AsyncClient, auth_headers):
    """[修 Bug 1] 上游返回 {"code":200,"message":"success"} 应判定为成功（单元 _real_push_upstream）。"""
    from app.api import home_safety_v1 as _hs

    class _FakeResp:
        status_code = 200
        text = '{"code":200,"message":"success"}'

        def json(self):
            return {"code": 200, "message": "success"}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return _FakeResp()

    import httpx

    orig_client = httpx.AsyncClient
    httpx.AsyncClient = _FakeClient  # type: ignore
    try:
        result = await _hs._real_push_upstream(
            "http://119.3.169.29/treatment/api/setMsgCallBackUrl",
            "tk-200",
            "huawei-test",
            "https://newbb.test.bangbangvip.com/autodev/abc/api/home_safety/callback/alarm",
        )
    finally:
        httpx.AsyncClient = orig_client  # type: ignore

    assert result["status"] == "success", f"code=200 message=success 应判成功: {result}"
    assert result["code"] == 200, "上游返回码必须原样透传"
    assert "judge_basis" in result
    assert "命中成功白名单" in result["judge_basis"]


@pytest.mark.asyncio
async def test_push_success_with_code_zero(client: AsyncClient, auth_headers):
    """[修 Bug 1] 上游返回 {"code":0,"message":"ok"} 仍应判成功（理想契约场景）。"""
    from app.api import home_safety_v1 as _hs

    class _FakeResp:
        status_code = 200
        text = '{"code":0,"message":"ok"}'

        def json(self):
            return {"code": 0, "message": "ok"}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return _FakeResp()

    import httpx

    orig = httpx.AsyncClient
    httpx.AsyncClient = _FakeClient  # type: ignore
    try:
        result = await _hs._real_push_upstream(
            "http://up.example.com/api/cb", "tk", "ideal", "https://cb.example.com"
        )
    finally:
        httpx.AsyncClient = orig  # type: ignore

    assert result["status"] == "success"
    assert result["code"] == 0


@pytest.mark.asyncio
async def test_push_fail_with_invalid_code(client: AsyncClient, auth_headers):
    """[修 Bug 1] 上游返回 code=1 message='token invalid' 仍应判失败，message 透传。"""
    from app.api import home_safety_v1 as _hs

    class _FakeResp:
        status_code = 200
        text = '{"code":1,"message":"token invalid"}'

        def json(self):
            return {"code": 1, "message": "token invalid"}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return _FakeResp()

    import httpx

    orig = httpx.AsyncClient
    httpx.AsyncClient = _FakeClient  # type: ignore
    try:
        result = await _hs._real_push_upstream(
            "http://up.example.com/api/cb", "bad", "fail-test", "https://cb.example.com"
        )
    finally:
        httpx.AsyncClient = orig  # type: ignore

    assert result["status"] == "fail", f"code=1 应判失败: {result}"
    assert result["code"] == 1, "上游返回码原样透传"
    assert "token invalid" in (result.get("message") or "")


@pytest.mark.asyncio
async def test_push_integration_status_passthrough(
    client: AsyncClient, auth_headers, monkeypatch
):
    """[修 Bug 1 集成] admin_push_upstream 必须把内部 status 字段透传到响应。"""
    from app.api import home_safety_v1 as _hs

    body = {
        "org_id": "integ-test",
        "auth_token": "tk",
        "upstream_base_url": "http://up.example.com",
        "upstream_path": "/api/cb",
        "callback_domain": "https://cb.example.com",
    }
    await client.put("/api/admin/home_safety/callback_config", json=body, headers=auth_headers)

    async def _fake_push(*a, **kw):
        return {
            "status": "success",
            "code": 200,
            "message": "success",
            "raw": '{"code":200,"message":"success"}',
            "judge_basis": "HTTP 200 + code=200 命中成功白名单",
        }

    monkeypatch.setattr(_hs, "_PUSH_UPSTREAM_OVERRIDE", _fake_push)

    r = await client.post(
        "/api/admin/home_safety/callback_config/push_upstream", headers=auth_headers
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("status") == "success", data
    assert data.get("code") == 200
    assert "judge_basis" in data


@pytest.mark.asyncio
async def test_push_non_json_response_fails(client: AsyncClient, auth_headers):
    """[修 Bug 1] 上游返回非 JSON → 失败 + 消息「上游响应解析失败」。"""
    from app.api import home_safety_v1 as _hs

    class _FakeResp:
        status_code = 200
        text = "<html>not json</html>"

        def json(self):
            raise ValueError("not json")

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return _FakeResp()

    import httpx

    orig = httpx.AsyncClient
    httpx.AsyncClient = _FakeClient  # type: ignore
    try:
        result = await _hs._real_push_upstream(
            "http://up.example.com/api/cb", "tk", "x", "https://cb.com"
        )
    finally:
        httpx.AsyncClient = orig  # type: ignore

    assert result["status"] == "fail"
    assert "解析失败" in (result.get("message") or "")


@pytest.mark.asyncio
async def test_push_judge_basis_persisted_in_get(client: AsyncClient, auth_headers, monkeypatch):
    """[修 Bug 1] judge_basis 在 GET callback_config 中应可持久化读出。"""
    from app.api import home_safety_v1 as _hs

    body = {
        "org_id": "judge-test",
        "auth_token": "tk",
        "upstream_base_url": "http://up.example.com",
        "upstream_path": "/api/cb",
        "callback_domain": "https://my.example.com",
    }
    await client.put("/api/admin/home_safety/callback_config", json=body, headers=auth_headers)

    async def _fake(full_url, auth_token, dept_id, callback_url):
        return {
            "status": "success",
            "code": 200,
            "message": "success",
            "raw": '{"code":200,"message":"success"}',
            "judge_basis": "HTTP 200 + code=200 命中成功白名单",
        }

    monkeypatch.setattr(_hs, "_PUSH_UPSTREAM_OVERRIDE", _fake)

    await client.post("/api/admin/home_safety/callback_config/push_upstream", headers=auth_headers)
    r = await client.get("/api/admin/home_safety/callback_config", headers=auth_headers)
    j = r.json()
    assert "last_push_judge_basis" in j
    assert "命中成功白名单" in (j.get("last_push_judge_basis") or "")


# ============== 修复 2：回调流水"先写 pending → 业务后 update" ==============
@pytest.mark.asyncio
async def test_callback_log_written_for_ok_path(client: AsyncClient, auth_headers):
    """[修 Bug 2] 正常报文：列表能查到，状态 ok。"""
    rb = await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 1, "gateway_sn": "GWLOGOK1", "emergency_phone": "13800001234", "remark": "测试备注", "device_sn": "LOGOK001"},
        headers=auth_headers,
    )
    assert rb.status_code == 200, rb.text
    r0 = await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "msgid-logok-001",
            "dataType": "call-msg",
            "param": {
                "devId": "LOGOK001",
                "devType": 1,
                "occurTime": 1740000000000,
                "gwId": "GWLOGOK00001",
            },
        },
    )
    assert r0.status_code == 200

    r_all = await client.get(
        "/api/admin/home_safety/callback_log", headers=auth_headers
    )
    assert r_all.status_code == 200, r_all.text
    all_items = r_all.json()["items"]

    r = await client.get(
        "/api/admin/home_safety/callback_log?parse_status=ok", headers=auth_headers
    )
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    hit = next((x for x in items if x.get("vendor_msg_id") == "msgid-logok-001"), None)
    assert hit is not None, f"成功路径必须落 ok 流水 / all_items={all_items}"
    assert hit["parse_status"] == "ok"
    assert hit["device_sn"] == "LOGOK001"


@pytest.mark.asyncio
async def test_callback_log_for_unsupported_type(client: AsyncClient, auth_headers):
    """[修 Bug 2] dataType=foo 应被记录为 unsupported_type。"""
    r0 = await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "msgid-unsup-001",
            "dataType": "foo",
            "param": {"devId": "FOODEV01", "devType": 1, "occurTime": 1740000000000},
        },
    )
    assert r0.status_code == 200

    r = await client.get(
        "/api/admin/home_safety/callback_log?parse_status=unsupported_type",
        headers=auth_headers,
    )
    items = r.json()["items"]
    hit = next((x for x in items if x.get("vendor_msg_id") == "msgid-unsup-001"), None)
    assert hit is not None
    assert hit["parse_status"] == "unsupported_type"
    assert "foo" in (hit["parse_fail_reason"] or "")


@pytest.mark.asyncio
async def test_callback_log_for_unbound_device(client: AsyncClient, auth_headers):
    """[修 Bug 2] 未绑定设备应被记录为 unbound。"""
    await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "msgid-unbound-001",
            "dataType": "call-msg",
            "param": {"devId": "NOBIND01", "devType": 1, "occurTime": 1740000000000},
        },
    )
    r = await client.get(
        "/api/admin/home_safety/callback_log?parse_status=unbound", headers=auth_headers
    )
    items = r.json()["items"]
    hit = next((x for x in items if x.get("vendor_msg_id") == "msgid-unbound-001"), None)
    assert hit is not None
    assert hit["parse_status"] == "unbound"
    assert hit["device_sn"] == "NOBIND01"


@pytest.mark.asyncio
async def test_callback_log_for_duplicate_msg(client: AsyncClient, auth_headers):
    """[修 Bug 2] 重复 msgId 应被记录为 duplicate。"""
    rb = await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 1, "gateway_sn": "GWDUPMS1", "emergency_phone": "13800001234", "remark": "测试备注", "device_sn": "DUPMSG01"},
        headers=auth_headers,
    )
    assert rb.status_code == 200, rb.text
    payload = {
        "msgId": "msgid-dup-001",
        "dataType": "call-msg",
        "param": {"devId": "DUPMSG01", "devType": 1, "occurTime": 1740000000000},
    }
    r1 = await client.post("/api/home_safety/callback/alarm", json=payload)
    r2 = await client.post("/api/home_safety/callback/alarm", json=payload)
    assert r1.status_code == 200 and r2.status_code == 200

    r = await client.get(
        "/api/admin/home_safety/callback_log?parse_status=duplicate", headers=auth_headers
    )
    items = r.json()["items"]
    dup_hits = [x for x in items if x.get("vendor_msg_id") == "msgid-dup-001"]
    assert dup_hits, "重复 msgId 必须有 duplicate 流水"
    assert dup_hits[0]["parse_status"] == "duplicate"


@pytest.mark.asyncio
async def test_callback_log_for_missing_field(client: AsyncClient, auth_headers):
    """[修 Bug 2] 缺失 devId 应被记录为 missing_field。"""
    await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "msgid-missing-001",
            "dataType": "call-msg",
            "param": {"devType": 1},
        },
    )
    r = await client.get(
        "/api/admin/home_safety/callback_log?parse_status=missing_field",
        headers=auth_headers,
    )
    items = r.json()["items"]
    hit = next((x for x in items if x.get("vendor_msg_id") == "msgid-missing-001"), None)
    assert hit is not None
    assert hit["parse_status"] == "missing_field"


@pytest.mark.asyncio
async def test_callback_log_detail_field_mapping(client: AsyncClient, auth_headers):
    """[修 Bug 2] 详情接口应返回完整 headers + body + 字段映射。"""
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 2, "gateway_sn": "GWMAP001", "emergency_phone": "13800001234", "remark": "测试备注", "device_sn": "MAP00001"},
        headers=auth_headers,
    )
    await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "msgid-mapping-001",
            "dataType": "call-msg",
            "param": {
                "devId": "MAP00001",
                "devType": 2,
                "occurTime": 1740000000000,
                "gwId": "GWMAP00000001",
                "devName": "厨房烟感",
                "callType": 0,
            },
        },
    )

    r = await client.get(
        "/api/admin/home_safety/callback_log?device_sn=MAP00001", headers=auth_headers
    )
    items = r.json()["items"]
    assert items
    log_id = items[0]["id"]

    rd = await client.get(
        f"/api/admin/home_safety/callback_log/{log_id}", headers=auth_headers
    )
    assert rd.status_code == 200, rd.text
    detail = rd.json()
    assert detail["request_method"] == "POST"
    assert "/api/home_safety/callback/alarm" in (detail["request_url"] or "")
    assert detail["device_sn"] == "MAP00001"
    assert detail["request_body_parsed"]["msgId"] == "msgid-mapping-001"
    # 字段映射对照存在
    fm = detail["field_mapping"]
    assert any(item["vendor"] == "param.devId" and item["value"] == "MAP00001" for item in fm)
    assert any(item["vendor"] == "param.devName" and item["value"] == "厨房烟感" for item in fm)


@pytest.mark.asyncio
async def test_callback_log_filters(client: AsyncClient, auth_headers):
    """[修 Bug 2] 列表筛选：device_sn / parse_status / keyword 均生效。"""
    # 准备数据
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 7, "gateway_sn": "GWFILT01", "emergency_phone": "13800001234", "remark": "测试备注", "device_sn": "FILTER01"},
        headers=auth_headers,
    )
    await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "msgId": "msgid-filter-1",
            "dataType": "call-msg",
            "param": {"devId": "FILTER01", "devType": 7, "occurTime": 1740000010000},
        },
    )

    # by device_sn
    r1 = await client.get(
        "/api/admin/home_safety/callback_log?device_sn=FILTER01", headers=auth_headers
    )
    assert r1.status_code == 200
    assert any(x["device_sn"] == "FILTER01" for x in r1.json()["items"])

    # by parse_status
    r2 = await client.get(
        "/api/admin/home_safety/callback_log?parse_status=ok", headers=auth_headers
    )
    assert r2.status_code == 200
    assert all(x["parse_status"] == "ok" for x in r2.json()["items"])

    # by keyword
    r3 = await client.get(
        "/api/admin/home_safety/callback_log?keyword=msgid-filter-1", headers=auth_headers
    )
    assert r3.status_code == 200
    assert any(x.get("vendor_msg_id") == "msgid-filter-1" for x in r3.json()["items"])


# ============== 修复 3：回调地址自检 ==============
@pytest.mark.asyncio
async def test_precheck_with_invalid_url(client: AsyncClient, auth_headers):
    """[修复 3] 非法 URL 应判 fail。"""
    r = await client.post(
        "/api/admin/home_safety/callback_config/precheck",
        json={"callback_url": "not-a-url"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    j = r.json()
    assert j["success"] is False
    assert j.get("blocked") is True
    assert any(c["name"] == "URL 格式合法" and c["status"] == "fail" for c in j["checks"])


@pytest.mark.asyncio
async def test_precheck_with_empty_url(client: AsyncClient, auth_headers):
    """[修复 3] 配置中无回调 URL，应自检失败但给出明确提示。"""
    # 确保配置中无 callback_domain
    r = await client.post(
        "/api/admin/home_safety/callback_config/precheck",
        json={"callback_url": ""},
        headers=auth_headers,
    )
    assert r.status_code == 200
    j = r.json()
    # success=False，因为 callback_url 既不在请求中也不在配置中
    if not j.get("callback_url"):
        assert j["success"] is False


@pytest.mark.asyncio
async def test_precheck_localhost_warns(client: AsyncClient, auth_headers, monkeypatch):
    """[修复 3] http://localhost 应至少给出 HTTPS warn。"""
    r = await client.post(
        "/api/admin/home_safety/callback_config/precheck",
        json={"callback_url": "http://localhost/api/cb"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    j = r.json()
    https_check = next(c for c in j["checks"] if c["name"] == "HTTPS 协议")
    assert https_check["status"] in ("warn", "fail")


@pytest.mark.asyncio
async def test_precheck_correct_https_url_format_pass(client: AsyncClient, auth_headers):
    """[修复 3] 合法 HTTPS URL 格式校验和 HTTPS 校验都应通过。"""
    r = await client.post(
        "/api/admin/home_safety/callback_config/precheck",
        json={
            "callback_url": "https://newbb.test.bangbangvip.com/autodev/abc/api/home_safety/callback/alarm"
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    j = r.json()
    fmt = next(c for c in j["checks"] if c["name"] == "URL 格式合法")
    https = next(c for c in j["checks"] if c["name"] == "HTTPS 协议")
    assert fmt["status"] == "pass"
    assert https["status"] == "pass"
    # 5 项检查全部存在
    names = [c["name"] for c in j["checks"]]
    for n in ["URL 格式合法", "HTTPS 协议", "域名可解析", "外网可达", "路由命中本项目"]:
        assert n in names, f"自检应包含「{n}」项"


@pytest.mark.asyncio
async def test_precheck_self_loop_payload_recognized(client: AsyncClient):
    """[修复 3 边界] 回调接口收到 dataType=__precheck__ 应识别并返回 matched_project=True。"""
    r = await client.post(
        "/api/home_safety/callback/alarm",
        json={
            "dataType": "__precheck__",
            "msgId": "selfloop-001",
            "param": {},
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("precheck") is True
    assert j.get("matched_project") is True


