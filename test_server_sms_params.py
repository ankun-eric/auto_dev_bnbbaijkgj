"""
Server-side API tests for SMS template custom params feature.
Target: https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857
"""

import httpx
import pytest
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_BASE = f"{BASE_URL}/api"
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"

TEMPLATE_DATA = {
    "name": "服务器测试模板",
    "provider": "tencent",
    "template_id": "test_server_001",
    "content": "您的验证码为{1}，{2}分钟内有效。",
    "sign_name": "测试签名",
    "scene": "verification",
    "variables": [
        {"name": "验证码", "description": "6位数字验证码", "default_value": "123456"},
        {"name": "有效时间", "description": "单位为分钟", "default_value": "5"},
    ],
}

created_template_id: int | None = None


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=API_BASE, verify=False, timeout=30) as c:
        yield c


@pytest.fixture(scope="module")
def admin_headers(client: httpx.Client):
    resp = client.post("/admin/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    token = resp.json().get("token")
    assert token, f"No token in response: {resp.json()}"
    return {"Authorization": f"Bearer {token}"}


# ──────── TC-01: Create template with variables ────────

class TestTC01CreateTemplate:
    def test_create_template_with_variables(self, client: httpx.Client, admin_headers: dict):
        global created_template_id
        resp = client.post("/admin/sms/templates", json=TEMPLATE_DATA, headers=admin_headers)
        assert resp.status_code in (200, 201), f"Create failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "id" in data
        created_template_id = data["id"]

        variables = data.get("variables")
        assert isinstance(variables, list), f"variables should be list, got {type(variables)}"
        assert len(variables) == 2
        assert all(isinstance(v, dict) for v in variables)
        assert variables[0]["name"] == "验证码"
        assert variables[1]["default_value"] == "5"


# ──────── TC-02: List templates, verify variables format ────────

class TestTC02ListTemplates:
    def test_list_templates_variables_format(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/admin/sms/templates", headers=admin_headers)
        assert resp.status_code == 200, f"List failed: {resp.status_code} {resp.text}"
        items = resp.json().get("items", [])
        matched = [t for t in items if t.get("id") == created_template_id]
        assert matched, "Created template not found in list"
        tpl = matched[0]
        variables = tpl.get("variables")
        assert isinstance(variables, list), f"variables should be list, got {type(variables)}: {variables}"
        assert all(isinstance(v, dict) for v in variables)


# ──────── TC-03: Update template variables ────────

class TestTC03UpdateTemplate:
    def test_update_template_variables(self, client: httpx.Client, admin_headers: dict):
        assert created_template_id is not None, "TC-01 must pass first"
        updated_variables = [
            {"name": "验证码", "description": "6位数字验证码", "default_value": "654321"},
            {"name": "有效时间", "description": "单位为分钟", "default_value": "10"},
            {"name": "应用名", "description": "应用名称", "default_value": "测试App"},
        ]
        resp = client.put(
            f"/admin/sms/templates/{created_template_id}",
            json={"variables": updated_variables},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Update failed: {resp.status_code} {resp.text}"
        data = resp.json()
        variables = data.get("variables")
        assert isinstance(variables, list)
        assert len(variables) == 3
        assert variables[0]["default_value"] == "654321"
        assert variables[2]["name"] == "应用名"


# ──────── TC-04: Test send with custom template_params ────────

class TestTC04TestSendWithCustomParams:
    def test_send_with_custom_template_params(self, client: httpx.Client, admin_headers: dict):
        resp = client.post(
            "/admin/sms/test",
            json={
                "phone": "13800138000",
                "provider": "tencent",
                "template_id": "test_server_001",
                "template_params": ["888888", "10"],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200, (
            f"BUG: POST /admin/sms/test returned {resp.status_code} instead of 200. "
            f"Body: {resp.text[:300]}. "
            f"Likely cause: sms_logs.template_params column missing in DB "
            f"(SQLAlchemy create_all does not add columns to existing tables)."
        )
        data = resp.json()
        assert "params_used" in data, f"Missing params_used in response: {data}"
        assert "preview_content" in data, f"Missing preview_content in response: {data}"
        assert data["params_used"] == ["888888", "10"]


# ──────── TC-05: Test send without template_params ────────

class TestTC05TestSendWithoutParams:
    def test_send_without_template_params(self, client: httpx.Client, admin_headers: dict):
        resp = client.post(
            "/admin/sms/test",
            json={
                "phone": "13800138000",
                "provider": "tencent",
                "template_id": "test_server_001",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200, (
            f"BUG: POST /admin/sms/test (no params) returned {resp.status_code}. "
            f"Body: {resp.text[:300]}. "
            f"Likely cause: sms_logs.template_params column missing in DB."
        )
        data = resp.json()
        assert "params_used" in data, f"Missing params_used: {data}"
        params = data["params_used"]
        assert isinstance(params, list) and len(params) >= 1
        assert params[0].isdigit() and len(params[0]) == 6, \
            f"Auto-generated code should be 6-digit, got: {params[0]}"


# ──────── TC-06: Preview content replacement ────────

class TestTC06PreviewContentReplacement:
    def test_preview_content_replaced_correctly(self, client: httpx.Client, admin_headers: dict):
        resp = client.post(
            "/admin/sms/test",
            json={
                "phone": "13800138000",
                "provider": "tencent",
                "template_id": "test_server_001",
                "template_params": ["888888", "10"],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200, (
            f"BUG: POST /admin/sms/test returned {resp.status_code}. "
            f"Body: {resp.text[:300]}. "
            f"Cannot verify preview_content due to server error."
        )
        data = resp.json()
        preview = data.get("preview_content")
        assert preview is not None, f"preview_content is None: {data}"
        assert "888888" in preview, f"preview_content should contain 888888: {preview}"
        assert "10" in preview, f"preview_content should contain 10: {preview}"
        assert "{1}" not in preview, f"preview_content still has unreplaced {{1}}: {preview}"
        assert "{2}" not in preview, f"preview_content still has unreplaced {{2}}: {preview}"


# ──────── TC-07: Unauthorized access ────────

class TestTC07UnauthorizedAccess:
    def test_unauthorized_test_send(self, client: httpx.Client):
        resp = client.post(
            "/admin/sms/test",
            json={
                "phone": "13800138000",
                "provider": "tencent",
                "template_id": "test_server_001",
            },
        )
        assert resp.status_code == 401, f"Expected 401 without token, got {resp.status_code}: {resp.text}"


# ──────── TC-08: Logs contain template_params field ────────

class TestTC08LogsContainTemplateParams:
    def test_logs_have_template_params(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/admin/sms/logs", params={"page": 1, "page_size": 5}, headers=admin_headers)
        assert resp.status_code == 200, (
            f"BUG: GET /admin/sms/logs returned {resp.status_code}. "
            f"Body: {resp.text[:300]}. "
            f"Likely cause: sms_logs.template_params column missing in DB."
        )
        items = resp.json().get("items", [])
        assert len(items) > 0, "No SMS logs found"
        has_template_params = any("template_params" in log for log in items)
        assert has_template_params, f"No log entry has template_params field: {items[:2]}"


# ──────── TC-09: Cleanup test data ────────

class TestTC09Cleanup:
    def test_delete_test_template(self, client: httpx.Client, admin_headers: dict):
        assert created_template_id is not None, "TC-01 must pass first"
        resp = client.delete(f"/admin/sms/templates/{created_template_id}", headers=admin_headers)
        assert resp.status_code == 200, f"Delete failed: {resp.status_code} {resp.text}"
        verify_resp = client.get("/admin/sms/templates", headers=admin_headers)
        items = verify_resp.json().get("items", [])
        assert not any(t.get("id") == created_template_id for t in items), "Template still exists after delete"
