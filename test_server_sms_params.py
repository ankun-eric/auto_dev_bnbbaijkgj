"""Server-side integration tests for SMS template params feature."""

import json
import httpx
import pytest

BASE = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
ADMIN_CREDS = {"phone": "13800000000", "password": "admin123"}


@pytest.fixture(scope="module")
def admin_token():
    with httpx.Client(verify=False, timeout=15) as c:
        r = c.post(f"{BASE}/admin/login", json=ADMIN_CREDS)
        assert r.status_code == 200, f"Admin login failed: {r.text}"
        return r.json()["token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def client():
    with httpx.Client(verify=False, timeout=15) as c:
        yield c


# ───── Template CRUD with variables ─────


def test_create_template_with_variables(client, headers):
    variables = [
        {"name": "验证码", "description": "6位数字验证码", "default_value": "123456"},
        {"name": "有效时间", "description": "单位为分钟", "default_value": "5"},
    ]
    r = client.post(f"{BASE}/admin/sms/templates", json={
        "name": "服务器测试模板",
        "provider": "tencent",
        "template_id": "SVR_TPL_001",
        "content": "您的验证码为{1}，{2}分钟内有效。",
        "sign_name": "测试签名",
        "scene": "verification",
        "variables": variables,
    }, headers=headers)
    assert r.status_code == 200, f"Create template failed: {r.text}"
    data = r.json()
    assert data["name"] == "服务器测试模板"
    assert isinstance(data["variables"], list)
    assert len(data["variables"]) == 2
    assert data["variables"][0]["name"] == "验证码"
    assert data["variables"][0]["default_value"] == "123456"
    assert data["variables"][1]["name"] == "有效时间"


def test_create_template_without_variables(client, headers):
    r = client.post(f"{BASE}/admin/sms/templates", json={
        "name": "无变量模板",
        "provider": "tencent",
        "template_id": "SVR_TPL_002",
        "content": "通知：系统升级",
        "scene": "notification",
    }, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["variables"] is None


def test_update_template_variables(client, headers):
    r = client.post(f"{BASE}/admin/sms/templates", json={
        "name": "待更新模板",
        "provider": "tencent",
        "template_id": "SVR_TPL_003",
        "content": "您的验证码是{1}",
        "variables": [{"name": "code"}],
    }, headers=headers)
    assert r.status_code == 200
    tpl_id = r.json()["id"]

    new_vars = [
        {"name": "code", "description": "验证码", "default_value": "666666"},
        {"name": "expiry", "description": "过期时间", "default_value": "10"},
    ]
    r2 = client.put(f"{BASE}/admin/sms/templates/{tpl_id}", json={
        "variables": new_vars,
    }, headers=headers)
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["variables"]) == 2
    assert data["variables"][0]["default_value"] == "666666"
    assert data["variables"][1]["name"] == "expiry"


def test_list_templates_includes_variables(client, headers):
    r = client.get(f"{BASE}/admin/sms/templates", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    found = [t for t in data["items"] if t["template_id"] == "SVR_TPL_001"]
    assert len(found) >= 1
    tpl = found[0]
    assert isinstance(tpl["variables"], list)
    assert len(tpl["variables"]) == 2


def test_list_templates_null_variables_shows(client, headers):
    r = client.get(f"{BASE}/admin/sms/templates", headers=headers)
    assert r.status_code == 200
    data = r.json()
    found = [t for t in data["items"] if t["template_id"] == "SVR_TPL_002"]
    assert len(found) >= 1
    assert found[0]["variables"] is None


# ───── Test send with custom params ─────


def test_send_with_template_params(client, headers):
    r = client.post(f"{BASE}/admin/sms/test", json={
        "phone": "13800200001",
        "template_id": "SVR_TPL_001",
        "template_params": ["888888", "10"],
    }, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["params_used"] == ["888888", "10"]
    assert data["preview_content"] == "您的验证码为888888，10分钟内有效。"


def test_send_without_template_params(client, headers):
    r = client.post(f"{BASE}/admin/sms/test", json={
        "phone": "13800200002",
        "template_id": "SVR_TPL_001",
    }, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["params_used"], list)
    assert len(data["params_used"]) == 1
    code = data["params_used"][0]
    assert code.isdigit() and len(code) == 6


def test_send_response_has_preview_content(client, headers):
    r = client.post(f"{BASE}/admin/sms/test", json={
        "phone": "13800200003",
        "template_id": "SVR_TPL_001",
        "template_params": ["654321", "3"],
    }, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "preview_content" in data
    assert data["preview_content"] is not None
    assert "654321" in data["preview_content"]
    assert "3" in data["preview_content"]


def test_send_requires_admin(client):
    r = client.post(f"{BASE}/admin/sms/test", json={
        "phone": "13800200004",
        "template_id": "SVR_TPL_001",
    })
    assert r.status_code in (401, 403)


# ───── Log records ─────


def test_log_records_template_params(client, headers):
    r = client.get(f"{BASE}/admin/sms/logs", params={"page_size": 50}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    matched = [l for l in data["items"] if l.get("template_params")]
    if matched:
        params = json.loads(matched[0]["template_params"])
        assert isinstance(params, list)


# ───── Delete test templates ─────


def test_delete_test_templates(client, headers):
    r = client.get(f"{BASE}/admin/sms/templates", params={"page_size": 100}, headers=headers)
    assert r.status_code == 200
    for tpl in r.json()["items"]:
        if tpl["template_id"].startswith("SVR_TPL_"):
            dr = client.delete(f"{BASE}/admin/sms/templates/{tpl['id']}", headers=headers)
            assert dr.status_code == 200
