"""Tests for SMS template params feature: template CRUD with variables, test-send with custom params, and log recording."""

import json

import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import SmsConfig, User, UserRole
from app.services.sms_service import encrypt_secret_key

TEMPLATES_URL = "/api/admin/sms/templates"
TEST_URL = "/api/admin/sms/test"
LOGS_URL = "/api/admin/sms/logs"


async def _admin_headers(client: AsyncClient, db_session) -> dict:
    db_session.add(User(
        phone="13800100001",
        password_hash=get_password_hash("admin123"),
        nickname="SMS测试管理员",
        role=UserRole.admin,
    ))
    await db_session.commit()
    resp = await client.post("/api/admin/login", json={
        "phone": "13800100001",
        "password": "admin123",
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# ──────── Template CRUD ────────


@pytest.mark.asyncio
async def test_tc01_create_template_with_variables(client: AsyncClient, db_session):
    """TC-01: variables should be stored and returned correctly."""
    headers = await _admin_headers(client, db_session)
    variables = [
        {"name": "code", "description": "验证码", "example": "123456"},
        {"name": "minutes", "description": "有效时间", "example": "5"},
    ]
    resp = await client.post(TEMPLATES_URL, json={
        "name": "验证码模板",
        "provider": "tencent",
        "template_id": "TPL_001",
        "content": "您的验证码是{1}，有效期{2}分钟。",
        "sign_name": "测试签名",
        "scene": "verification",
        "variables": variables,
    }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "验证码模板"
    assert data["template_id"] == "TPL_001"
    assert isinstance(data["variables"], list)
    assert len(data["variables"]) == 2
    assert data["variables"][0]["name"] == "code"
    assert data["variables"][1]["name"] == "minutes"
    assert data["variables"][1]["example"] == "5"


@pytest.mark.asyncio
async def test_tc02_create_template_without_variables(client: AsyncClient, db_session):
    """TC-02: template without variables should be backward-compatible."""
    headers = await _admin_headers(client, db_session)
    resp = await client.post(TEMPLATES_URL, json={
        "name": "通知模板",
        "provider": "tencent",
        "template_id": "TPL_002",
        "content": "您有一条新消息",
        "scene": "notification",
    }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "通知模板"
    assert data["variables"] is None
    assert data["status"] is True


@pytest.mark.asyncio
async def test_tc03_update_template_variables(client: AsyncClient, db_session):
    """TC-03: updating variables returns correct new values."""
    headers = await _admin_headers(client, db_session)

    create_resp = await client.post(TEMPLATES_URL, json={
        "name": "待更新模板",
        "provider": "tencent",
        "template_id": "TPL_003",
        "content": "您的验证码是{1}",
        "variables": [{"name": "code", "description": "验证码"}],
    }, headers=headers)
    assert create_resp.status_code == 200
    tpl_id = create_resp.json()["id"]

    new_vars = [
        {"name": "code", "description": "验证码", "example": "666666"},
        {"name": "expiry", "description": "过期时间", "example": "10"},
    ]
    update_resp = await client.put(f"{TEMPLATES_URL}/{tpl_id}", json={
        "variables": new_vars,
    }, headers=headers)

    assert update_resp.status_code == 200
    data = update_resp.json()
    assert len(data["variables"]) == 2
    assert data["variables"][0]["example"] == "666666"
    assert data["variables"][1]["name"] == "expiry"


@pytest.mark.asyncio
async def test_tc04_list_templates_variables_format(client: AsyncClient, db_session):
    """TC-04: list endpoint returns variables as list[dict]."""
    headers = await _admin_headers(client, db_session)
    variables = [{"name": "amount", "description": "金额"}]
    await client.post(TEMPLATES_URL, json={
        "name": "列表测试模板",
        "provider": "tencent",
        "template_id": "TPL_004",
        "content": "消费{1}元",
        "variables": variables,
    }, headers=headers)

    resp = await client.get(TEMPLATES_URL, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1

    found = [i for i in data["items"] if i["template_id"] == "TPL_004"]
    assert len(found) == 1
    tpl = found[0]
    assert isinstance(tpl["variables"], list)
    assert tpl["variables"][0]["name"] == "amount"


# ──────── Test Send ────────


@pytest.mark.asyncio
async def test_tc05_test_send_with_template_params(client: AsyncClient, db_session):
    """TC-05: passing template_params returns correct params_used and preview_content."""
    headers = await _admin_headers(client, db_session)
    await client.post(TEMPLATES_URL, json={
        "name": "参数测试模板",
        "provider": "tencent",
        "template_id": "TPL_005",
        "content": "验证码{1}，{2}分钟有效",
    }, headers=headers)

    resp = await client.post(TEST_URL, json={
        "phone": "13800200001",
        "template_id": "TPL_005",
        "template_params": ["888888", "10"],
    }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["params_used"] == ["888888", "10"]
    assert data["preview_content"] == "验证码888888，10分钟有效"


@pytest.mark.asyncio
async def test_tc06_test_send_without_template_params(client: AsyncClient, db_session):
    """TC-06: omitting template_params falls back to random 6-digit code."""
    headers = await _admin_headers(client, db_session)
    await client.post(TEMPLATES_URL, json={
        "name": "回退测试模板",
        "provider": "tencent",
        "template_id": "TPL_006",
        "content": "验证码{1}",
    }, headers=headers)

    resp = await client.post(TEST_URL, json={
        "phone": "13800200002",
        "template_id": "TPL_006",
    }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["params_used"], list)
    assert len(data["params_used"]) == 1
    code = data["params_used"][0]
    assert code.isdigit() and len(code) == 6
    assert code in data["preview_content"]


@pytest.mark.asyncio
async def test_tc07_test_send_invalid_phone(client: AsyncClient, db_session):
    """TC-07: invalid phone still returns a well-formed error response."""
    headers = await _admin_headers(client, db_session)
    resp = await client.post(TEST_URL, json={
        "phone": "abc",
        "template_id": "TPL_007",
    }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "params_used" in data
    assert isinstance(data["message"], str) and len(data["message"]) > 0


@pytest.mark.asyncio
async def test_tc08_test_send_requires_admin(client: AsyncClient):
    """TC-08: test-send without admin token should be rejected."""
    resp = await client.post(TEST_URL, json={
        "phone": "13800200003",
        "template_id": "TPL_008",
    })
    assert resp.status_code in (401, 403)


# ──────── Log Recording ────────


@pytest.mark.asyncio
async def test_tc09_log_records_template_params(client: AsyncClient, db_session, monkeypatch):
    """TC-09: SMS log should persist template_params after a test send."""
    headers = await _admin_headers(client, db_session)

    db_session.add(SmsConfig(
        provider="tencent",
        secret_id="fake_id",
        secret_key_encrypted=encrypt_secret_key("fake_key"),
        sdk_app_id="1400000000",
        sign_name="测试",
        template_id="TPL_DEFAULT",
        is_active=True,
    ))
    await db_session.commit()

    async def _noop_tencent(*args, **kwargs):
        pass

    monkeypatch.setattr("app.services.sms_service._send_via_tencent", _noop_tencent)

    params = ["999999", "5"]
    resp = await client.post(TEST_URL, json={
        "phone": "13800200009",
        "template_id": "TPL_009",
        "template_params": params,
    }, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["success"] is True

    logs_resp = await client.get(LOGS_URL, headers=headers)
    assert logs_resp.status_code == 200
    logs_data = logs_resp.json()
    assert logs_data["total"] >= 1

    matched = [
        log for log in logs_data["items"]
        if log["template_id"] == "TPL_009" and log["is_test"]
    ]
    assert matched, "expected a log entry for TPL_009"
    log_params = json.loads(matched[0]["template_params"])
    assert log_params == params
