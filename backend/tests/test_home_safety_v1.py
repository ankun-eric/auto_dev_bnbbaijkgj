"""[PRD-HOME-SAFETY-V1 2026-05-27] 智能硬件绑定 · 居家安全设备 v1.0 测试套件

覆盖：
- 设备绑定/解绑/列表
- 紧急联系人配置（含主守护人锁定）
- 上游报警回调（含 5 分钟去重）
- 报警记录读/处置
- 管理后台：字典/绑定流水/报警流水/回调配置（保存/测试）
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


# ────────── 公共辅助 ──────────
async def _register_user(client: AsyncClient, phone: str, nickname: str) -> str:
    await client.post("/api/auth/register", json={"phone": phone, "password": "pw123456", "nickname": nickname})
    rsp = await client.post("/api/auth/login", json={"phone": phone, "password": "pw123456"})
    return rsp.json()["access_token"]


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


# ============== 1. 字典 ==============
@pytest.mark.asyncio
async def test_dict_device_types(client: AsyncClient, auth_headers):
    rsp = await client.get("/api/admin/home_safety/dict/device_types", headers=auth_headers)
    assert rsp.status_code == 200, rsp.text
    items = rsp.json()["items"]
    assert len(items) == 3
    types = sorted(i["device_type"] for i in items)
    assert types == [1, 2, 7]
    # 颜色三类差异化
    colors = {i["device_type"]: i["color"] for i in items}
    assert colors == {1: "red", 2: "orange", 7: "yellow"}


# ============== 2. 设备绑定/解绑/列表 ==============
@pytest.mark.asyncio
async def test_bind_unbind_devices(client: AsyncClient, auth_headers):
    rsp = await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 1, "gateway_sn": "GW1234567890", "device_sn": "DEV12345"},
        headers=auth_headers,
    )
    assert rsp.status_code == 200, rsp.text
    bid = rsp.json()["id"]
    assert bid > 0

    rsp = await client.get("/api/home_safety/devices", headers=auth_headers)
    assert rsp.status_code == 200
    groups = rsp.json()["groups"]
    em = next(g for g in groups if g["device_type"] == 1)
    assert em["count"] == 1
    assert em["items"][0]["gateway_sn_mask"].startswith("GW12")

    # 解绑
    rsp = await client.post(f"/api/home_safety/devices/{bid}/unbind", headers=auth_headers)
    assert rsp.status_code == 200
    rsp = await client.get("/api/home_safety/devices", headers=auth_headers)
    em = next(g for g in rsp.json()["groups"] if g["device_type"] == 1)
    assert em["count"] == 0


@pytest.mark.asyncio
async def test_bind_returns_iso_with_z_suffix(client: AsyncClient, auth_headers):
    """[PRD-HOME-SAFETY-V1 BUGFIX 2026-05-27 · Bug 2 时间字段]
    bound_at 在 /api/home_safety/devices 与 /api/admin/home_safety/bindings 中必须以 'Z' 结尾，明示 UTC，
    避免前端按本地时区误解析（北京时间显示需 +8h）。"""
    rsp = await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 1, "gateway_sn": "GWZSUFFIX001", "device_sn": "ZSUFFIX1"},
        headers=auth_headers,
    )
    assert rsp.status_code == 200, rsp.text

    r1 = await client.get("/api/home_safety/devices", headers=auth_headers)
    assert r1.status_code == 200
    groups = r1.json()["groups"]
    em = next(g for g in groups if g["device_type"] == 1)
    items = em["items"]
    assert any(it["device_sn"] == "ZSUFFIX1" for it in items)
    target = next(it for it in items if it["device_sn"] == "ZSUFFIX1")
    assert target["bound_at"] is not None
    assert target["bound_at"].endswith("Z"), f"bound_at 应带 'Z' UTC 后缀: {target['bound_at']}"

    r2 = await client.get("/api/admin/home_safety/bindings", headers=auth_headers)
    assert r2.status_code == 200
    bitems = r2.json()["items"]
    assert any(b["device_sn"] == "ZSUFFIX1" and (b["bound_at"] or "").endswith("Z") for b in bitems)


@pytest.mark.asyncio
async def test_admin_alarms_time_fields_with_z_suffix(client: AsyncClient, auth_headers):
    """[BUGFIX · Bug 2] 管理后台报警流水的 alarm_at / received_at 必须以 'Z' 结尾。"""
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 2, "gateway_sn": "GWTIMEZ00001", "device_sn": "TIMEZ001"},
        headers=auth_headers,
    )
    await client.post(
        "/callback/home_safety/alarm",
        json={"device_sn": "TIMEZ001", "type": 2, "alarm_time": "2026-05-27T22:00:00"},
    )
    rsp = await client.get("/api/admin/home_safety/alarms", headers=auth_headers)
    assert rsp.status_code == 200
    items = rsp.json()["items"]
    hits = [x for x in items if x["device_sn"] == "TIMEZ001"]
    assert hits, "应能查询到 TIMEZ001 的报警"
    a = hits[0]
    assert (a["alarm_at"] or "").endswith("Z"), f"alarm_at 应带 Z 后缀: {a['alarm_at']}"
    assert (a["received_at"] or "").endswith("Z"), f"received_at 应带 Z 后缀: {a['received_at']}"


@pytest.mark.asyncio
async def test_callback_config_time_fields_with_z_suffix(client: AsyncClient, auth_headers):
    """[BUGFIX · Bug 2] 回调配置的 updated_at / last_pushed_at / last_test_at 都必须以 'Z' 结尾。"""
    body = {
        "org_id": "platform-z",
        "callback_url": "https://example.com/cb-z",
        "auth_token": "tk",
        "upstream_base_url": "https://up.example.com",
    }
    await client.put("/api/admin/home_safety/callback_config", json=body, headers=auth_headers)
    await client.post("/api/admin/home_safety/callback_config/test", headers=auth_headers)
    await client.post("/api/admin/home_safety/callback_config/push_upstream", headers=auth_headers)
    r = await client.get("/api/admin/home_safety/callback_config", headers=auth_headers)
    j = r.json()
    assert (j.get("last_test_at") or "").endswith("Z"), f"last_test_at 应带 Z: {j.get('last_test_at')}"
    assert (j.get("last_pushed_at") or "").endswith("Z"), f"last_pushed_at 应带 Z: {j.get('last_pushed_at')}"
    assert (j.get("updated_at") or "").endswith("Z"), f"updated_at 应带 Z: {j.get('updated_at')}"


@pytest.mark.asyncio
async def test_bind_invalid_sn_rejected(client: AsyncClient, auth_headers):
    rsp = await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 1, "gateway_sn": "short", "device_sn": "DEV12345"},
        headers=auth_headers,
    )
    assert rsp.status_code == 400


@pytest.mark.asyncio
async def test_bind_duplicate_rejected(client: AsyncClient, auth_headers):
    body = {"device_type": 2, "gateway_sn": "GW2222222222", "device_sn": "SMOKE001"}
    r1 = await client.post("/api/home_safety/devices/bind", json=body, headers=auth_headers)
    assert r1.status_code == 200
    r2 = await client.post("/api/home_safety/devices/bind", json=body, headers=auth_headers)
    assert r2.status_code == 409


# ============== 3. 上游报警回调 + 去重 ==============
@pytest.mark.asyncio
async def test_upstream_alarm_callback_and_dedupe(client: AsyncClient, auth_headers):
    # 先绑设备
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 7, "gateway_sn": "GWWATER00001", "device_sn": "WATER001"},
        headers=auth_headers,
    )
    # 上游推送（用网关友好的 /api 前缀路径）
    r1 = await client.post(
        "/api/home_safety/callback/alarm",
        json={"device_sn": "WATER001", "type": 7, "alarm_time": "2026-05-27T18:30:00"},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["created"] == 1
    # 5 分钟内重复 → 合并，不生成新记录
    r2 = await client.post(
        "/callback/home_safety/alarm",
        json={"device_sn": "WATER001", "type": 7, "alarm_time": "2026-05-27T18:32:00"},
    )
    assert r2.status_code == 200
    assert r2.json()["created"] == 0
    assert r2.json()["dedup_skipped"] == 1

    # 用户侧报警列表应该有 1 条且 dedupe_count=2
    rsp = await client.get("/api/home_safety/alarms?device_type=7", headers=auth_headers)
    items = rsp.json()["items"]
    assert len(items) == 1
    assert items[0]["dedupe_count"] == 2


@pytest.mark.asyncio
async def test_upstream_alarm_unknown_device_returns_200(client: AsyncClient):
    rsp = await client.post(
        "/callback/home_safety/alarm",
        json={"device_sn": "NOBODY99", "type": 1, "alarm_time": "2026-05-27T18:30:00"},
    )
    assert rsp.status_code == 200
    assert rsp.json()["matched"] == 0


@pytest.mark.asyncio
async def test_ai_call_callback_no_error(client: AsyncClient):
    rsp = await client.post(
        "/callback/home_safety/ai_call_result",
        json={"request_id": "rid001", "status": "success"},
    )
    assert rsp.status_code == 200
    assert rsp.json()["received"] is True


# ============== 4. 报警处置 ==============
@pytest.mark.asyncio
async def test_alarm_read_and_handle(client: AsyncClient, auth_headers):
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 1, "gateway_sn": "GWEMERG0001A", "device_sn": "EMERG001"},
        headers=auth_headers,
    )
    await client.post(
        "/callback/home_safety/alarm",
        json={"device_sn": "EMERG001", "type": 1, "alarm_time": "2026-05-27T19:00:00"},
    )
    rsp = await client.get("/api/home_safety/alarms", headers=auth_headers)
    alarm_id = rsp.json()["items"][0]["id"]

    r1 = await client.post(f"/api/home_safety/alarms/{alarm_id}/read", headers=auth_headers)
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/home_safety/alarms/{alarm_id}/handle",
        json={"note": "已联系本人，确认无恙"},
        headers=auth_headers,
    )
    assert r2.status_code == 200

    rsp = await client.get("/api/home_safety/alarms", headers=auth_headers)
    item = rsp.json()["items"][0]
    assert item["read_status"] == 1
    assert item["handle_status"] == 1
    assert "无恙" in (item["handle_note"] or "")


# ============== 5. 紧急联系人（无守护人场景）==============
@pytest.mark.asyncio
async def test_emergency_contacts_no_guardian(client: AsyncClient, auth_headers):
    rsp = await client.get("/api/home_safety/emergency_contacts", headers=auth_headers)
    assert rsp.status_code == 200
    data = rsp.json()
    assert data["max_other_selectable"] == 2
    # 无守护人 → contacts 为空
    assert isinstance(data["contacts"], list)


@pytest.mark.asyncio
async def test_emergency_contacts_save_empty(client: AsyncClient, auth_headers):
    rsp = await client.post(
        "/api/home_safety/emergency_contacts",
        json={"guardian_ids": []},
        headers=auth_headers,
    )
    assert rsp.status_code == 200
    assert rsp.json()["success"] is True


# ============== 6. 管理后台：绑定与报警流水 ==============
@pytest.mark.asyncio
async def test_admin_bindings_and_alarms(client: AsyncClient, auth_headers):
    # 绑一台、报一次警
    await client.post(
        "/api/home_safety/devices/bind",
        json={"device_type": 2, "gateway_sn": "GWSMOKE00001", "device_sn": "SMOK0001"},
        headers=auth_headers,
    )
    await client.post(
        "/callback/home_safety/alarm",
        json={"device_sn": "SMOK0001", "type": 2, "alarm_time": "2026-05-27T20:00:00"},
    )
    r1 = await client.get("/api/admin/home_safety/bindings", headers=auth_headers)
    assert r1.status_code == 200
    assert len(r1.json()["items"]) >= 1
    r2 = await client.get("/api/admin/home_safety/alarms", headers=auth_headers)
    assert r2.status_code == 200
    assert len(r2.json()["items"]) >= 1


# ============== 7. 管理后台：回调配置 ==============
@pytest.mark.asyncio
async def test_admin_callback_config(client: AsyncClient, auth_headers, monkeypatch):
    # 初始为空
    r0 = await client.get("/api/admin/home_safety/callback_config", headers=auth_headers)
    assert r0.status_code == 200
    assert r0.json()["callback_url"] is None

    # 保存
    body = {
        "org_id": "platform",
        "callback_url": "https://example.com/callback",
        "auth_token": "token-xyz",
        "upstream_base_url": "https://upstream.example.com",
    }
    r1 = await client.put("/api/admin/home_safety/callback_config", json=body, headers=auth_headers)
    assert r1.status_code == 200

    # 读回
    r2 = await client.get("/api/admin/home_safety/callback_config", headers=auth_headers)
    assert r2.json()["org_id"] == "platform"
    assert r2.json()["callback_url"] == "https://example.com/callback"

    # 连通性测试（URL 格式合法）
    r3 = await client.post("/api/admin/home_safety/callback_config/test", headers=auth_headers)
    assert r3.status_code == 200
    assert r3.json()["success"] is True

    # [PRD-HOME-SAFETY-V2 2026-05-27] push_upstream 现在是真实 HTTP 调用
    # 测试期注入 mock 以避免外网依赖
    from app.api import home_safety_v1 as _hs

    async def _fake_push(full_url, auth_token, dept_id, callback_url):
        return {"status": "success", "code": 0, "message": "ok", "raw": '{"code":0,"message":"ok"}'}

    monkeypatch.setattr(_hs, "_PUSH_UPSTREAM_OVERRIDE", _fake_push)

    # v2 还需要 upstream_path 和 callback_domain，先补齐
    await client.put(
        "/api/admin/home_safety/callback_config",
        json={"upstream_path": "/api/cb", "callback_domain": "https://example.com"},
        headers=auth_headers,
    )
    r4 = await client.post("/api/admin/home_safety/callback_config/push_upstream", headers=auth_headers)
    assert r4.status_code == 200
    assert r4.json()["success"] is True
    monkeypatch.setattr(_hs, "_PUSH_UPSTREAM_OVERRIDE", None)
