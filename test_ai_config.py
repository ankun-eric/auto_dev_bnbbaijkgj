"""
Non-UI automated tests for AI Model Config & Template management APIs.
Uses pytest + httpx (async) against the deployed server.
"""

import httpx
import pytest
import pytest_asyncio

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
TIMEOUT = 30


async def get_admin_token() -> str | None:
    credentials_list = [
        {"phone": "13800138000", "password": "admin123"},
        {"phone": "13800000000", "password": "admin123"},
    ]
    async with httpx.AsyncClient(verify=False, timeout=TIMEOUT) as client:
        for creds in credentials_list:
            try:
                resp = await client.post(f"{BASE_URL}/admin/login", json=creds)
                if resp.status_code == 200:
                    token = resp.json().get("token")
                    if token:
                        return token
            except Exception:
                continue
    return None


async def get_user_token() -> str | None:
    """Register or login as a normal user and return the access_token."""
    async with httpx.AsyncClient(verify=False, timeout=TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/auth/register", json={
            "phone": "13900990099",
            "password": "user1234",
            "nickname": "普通测试用户",
        })
        if resp.status_code == 200:
            return resp.json().get("access_token")
        resp = await client.post(f"{BASE_URL}/auth/login", json={
            "phone": "13900990099",
            "password": "user1234",
        })
        if resp.status_code == 200:
            return resp.json().get("access_token")
    return None


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def admin_token():
    token = await get_admin_token()
    assert token is not None, "Failed to obtain admin token"
    return token


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def user_token_value():
    return await get_user_token()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def user_headers(user_token_value):
    if user_token_value is None:
        pytest.skip("Could not obtain normal user token")
    return {"Authorization": f"Bearer {user_token_value}"}


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client():
    async with httpx.AsyncClient(verify=False, timeout=TIMEOUT) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: cleanup templates and configs created during tests
# ---------------------------------------------------------------------------

created_template_ids: list[int] = []
created_config_ids: list[int] = []


@pytest_asyncio.fixture(scope="module", autouse=True, loop_scope="module")
async def cleanup(admin_headers):
    yield
    async with httpx.AsyncClient(verify=False, timeout=TIMEOUT) as c:
        for cid in reversed(created_config_ids):
            await c.delete(f"{BASE_URL}/admin/ai-config/{cid}", headers=admin_headers)
        for tid in reversed(created_template_ids):
            await c.delete(f"{BASE_URL}/admin/ai-model-templates/{tid}", headers=admin_headers)


# ═══════════════════════════════════════════════════════════════════════════
# Template Management API
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="module")
async def test_tc01_get_template_icons(client, admin_headers):
    """TC-01: GET /admin/ai-model-templates/icons → 200, returns 10 icons."""
    resp = await client.get(f"{BASE_URL}/admin/ai-model-templates/icons", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    items = data["items"]
    assert isinstance(items, list)
    assert len(items) == 10
    for icon in items:
        assert "key" in icon
        assert "label" in icon
        assert "color" in icon


@pytest.mark.asyncio(loop_scope="module")
async def test_tc02_create_template(client, admin_headers):
    """TC-02: POST /admin/ai-model-templates → successful creation."""
    payload = {
        "name": "AutoTest-DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model_name": "deepseek-chat",
        "icon": "deepseek",
        "description": "自动化测试模板",
    }
    resp = await client.post(f"{BASE_URL}/admin/ai-model-templates", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["name"] == payload["name"]
    assert data["base_url"] == payload["base_url"]
    assert data["model_name"] == payload["model_name"]
    assert data["icon"] == payload["icon"]
    assert data["status"] == 1
    created_template_ids.append(data["id"])


@pytest.mark.asyncio(loop_scope="module")
async def test_tc03_list_templates(client, admin_headers):
    """TC-03: GET /admin/ai-model-templates → returns template list."""
    resp = await client.get(f"{BASE_URL}/admin/ai-model-templates", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if created_template_ids:
        ids_in_list = [t["id"] for t in data["items"]]
        assert created_template_ids[-1] in ids_in_list


@pytest.mark.asyncio(loop_scope="module")
async def test_tc04_update_template(client, admin_headers):
    """TC-04: PUT /admin/ai-model-templates/{id} → update success."""
    assert created_template_ids, "No template created to update"
    tid = created_template_ids[-1]
    payload = {
        "name": "AutoTest-DeepSeek-Updated",
        "description": "更新后的描述",
    }
    resp = await client.put(f"{BASE_URL}/admin/ai-model-templates/{tid}", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "AutoTest-DeepSeek-Updated"
    assert data["description"] == "更新后的描述"
    assert data["id"] == tid


@pytest.mark.asyncio(loop_scope="module")
async def test_tc05_disable_template(client, admin_headers):
    """TC-05: PATCH /admin/ai-model-templates/{id}/status → disable (status=0)."""
    assert created_template_ids, "No template created to disable"
    tid = created_template_ids[-1]
    resp = await client.patch(
        f"{BASE_URL}/admin/ai-model-templates/{tid}/status",
        json={"status": 0},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == 0
    assert data["id"] == tid


@pytest.mark.asyncio(loop_scope="module")
async def test_tc06_enable_template(client, admin_headers):
    """TC-06: PATCH /admin/ai-model-templates/{id}/status → enable (status=1)."""
    assert created_template_ids, "No template created to enable"
    tid = created_template_ids[-1]
    resp = await client.patch(
        f"{BASE_URL}/admin/ai-model-templates/{tid}/status",
        json={"status": 1},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == 1
    assert data["id"] == tid


@pytest.mark.asyncio(loop_scope="module")
async def test_tc07_delete_unlinked_template(client, admin_headers):
    """TC-07: DELETE /admin/ai-model-templates/{id} → delete unlinked template."""
    payload = {
        "name": "AutoTest-ToDelete",
        "base_url": "https://api.example.com/v1",
        "model_name": "to-delete-model",
        "icon": "custom",
        "description": "即将删除的模板",
    }
    resp = await client.post(f"{BASE_URL}/admin/ai-model-templates", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    delete_tid = resp.json()["id"]

    resp = await client.delete(f"{BASE_URL}/admin/ai-model-templates/{delete_tid}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("message") == "删除成功"

    resp = await client.get(f"{BASE_URL}/admin/ai-model-templates", headers=admin_headers)
    assert resp.status_code == 200
    ids_in_list = [t["id"] for t in resp.json()["items"]]
    assert delete_tid not in ids_in_list


@pytest.mark.asyncio(loop_scope="module")
async def test_tc08_filter_templates_by_status(client, admin_headers):
    """TC-08: GET /admin/ai-model-templates?status=1 → only enabled templates."""
    disabled_payload = {
        "name": "AutoTest-Disabled-Filter",
        "base_url": "https://api.disabled.com/v1",
        "model_name": "disabled-model",
        "icon": "custom",
        "description": "停用筛选测试",
    }
    resp = await client.post(f"{BASE_URL}/admin/ai-model-templates", json=disabled_payload, headers=admin_headers)
    assert resp.status_code == 200
    disabled_tid = resp.json()["id"]
    created_template_ids.append(disabled_tid)

    await client.patch(
        f"{BASE_URL}/admin/ai-model-templates/{disabled_tid}/status",
        json={"status": 0},
        headers=admin_headers,
    )

    resp = await client.get(f"{BASE_URL}/admin/ai-model-templates", params={"status": 1}, headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert item["status"] == 1, f"Template {item['id']} has status {item['status']}, expected 1"


# ═══════════════════════════════════════════════════════════════════════════
# Config Management API
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="module")
async def test_tc09_create_config_from_template(client, admin_headers):
    """TC-09: POST /admin/ai-config with template_id → creates config linked to template."""
    assert created_template_ids, "No template available"
    tid = created_template_ids[0]
    payload = {
        "provider_name": "AutoTest-TemplateConfig",
        "base_url": "https://api.deepseek.com/v1",
        "model_name": "deepseek-chat",
        "api_key": "sk-autotest-template-key",
        "is_active": False,
        "max_tokens": 4096,
        "temperature": 0.7,
        "template_id": tid,
    }
    resp = await client.post(f"{BASE_URL}/admin/ai-config", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["template_id"] == tid
    assert data["template_synced_at"] is not None
    assert data["provider_name"] == payload["provider_name"]
    created_config_ids.append(data["id"])


@pytest.mark.asyncio(loop_scope="module")
async def test_tc10_create_custom_config(client, admin_headers):
    """TC-10: POST /admin/ai-config without template_id → creates custom config."""
    payload = {
        "provider_name": "AutoTest-CustomProvider",
        "base_url": "https://api.custom.com/v1",
        "model_name": "custom-model",
        "api_key": "sk-autotest-custom-key",
        "is_active": False,
        "max_tokens": 2048,
        "temperature": 0.5,
    }
    resp = await client.post(f"{BASE_URL}/admin/ai-config", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data.get("template_id") is None
    assert data.get("template_synced_at") is None
    assert data["provider_name"] == "AutoTest-CustomProvider"
    assert data["max_tokens"] == 2048
    assert data["temperature"] == 0.5
    created_config_ids.append(data["id"])


@pytest.mark.asyncio(loop_scope="module")
async def test_tc11_activate_config(client, admin_headers):
    """TC-11: PATCH /admin/ai-config/{id}/activate → activates config, others become inactive."""
    assert len(created_config_ids) >= 2, "Need at least 2 configs"
    target_id = created_config_ids[-1]

    resp = await client.patch(f"{BASE_URL}/admin/ai-config/{target_id}/activate", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == target_id
    assert data["is_active"] is True

    list_resp = await client.get(f"{BASE_URL}/admin/ai-config", headers=admin_headers)
    assert list_resp.status_code == 200
    for item in list_resp.json()["items"]:
        if item["id"] == target_id:
            assert item["is_active"] is True
        else:
            assert item["is_active"] is False, f"Config {item['id']} should be inactive"


@pytest.mark.asyncio(loop_scope="module")
async def test_tc12_get_active_config(client, admin_headers):
    """TC-12: GET /admin/ai-config/active → returns the active config."""
    resp = await client.get(f"{BASE_URL}/admin/ai-config/active", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is True
    assert "id" in data
    assert "provider_name" in data
    assert "base_url" in data
    assert "model_name" in data


@pytest.mark.asyncio(loop_scope="module")
async def test_tc13_sync_check(client, admin_headers):
    """TC-13: GET /admin/ai-config/sync-check → returns sync status."""
    resp = await client.get(f"{BASE_URL}/admin/ai-config/sync-check", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "need_sync" in data
    assert "count" in data
    assert isinstance(data["need_sync"], list)
    assert isinstance(data["count"], int)
    assert data["count"] == len(data["need_sync"])


@pytest.mark.asyncio(loop_scope="module")
async def test_tc14_confirm_sync(client, admin_headers):
    """TC-14: POST /admin/ai-config/sync → syncs template updates to configs."""
    if not created_template_ids or not created_config_ids:
        pytest.skip("No template-linked config to sync")

    tid = created_template_ids[0]
    await client.put(
        f"{BASE_URL}/admin/ai-model-templates/{tid}",
        json={"name": "AutoTest-DeepSeek-Synced", "model_name": "deepseek-chat-v2"},
        headers=admin_headers,
    )

    resp = await client.post(f"{BASE_URL}/admin/ai-config/sync", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "synced" in data
    assert isinstance(data["synced"], int)
    assert "message" in data


@pytest.mark.asyncio(loop_scope="module")
async def test_tc15_delete_template_with_linked_config(client, admin_headers):
    """TC-15: DELETE /admin/ai-model-templates/{id} with linked config → 400."""
    assert created_template_ids, "No template to test deletion constraint"
    tid = created_template_ids[0]

    resp = await client.delete(f"{BASE_URL}/admin/ai-model-templates/{tid}", headers=admin_headers)
    assert resp.status_code == 400
    data = resp.json()
    assert "关联配置" in data.get("detail", "")


# ═══════════════════════════════════════════════════════════════════════════
# Permission Tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="module")
async def test_tc16_unauthenticated_access(client):
    """TC-16: Unauthenticated access to admin endpoints → 401."""
    endpoints = [
        ("GET", f"{BASE_URL}/admin/ai-model-templates"),
        ("GET", f"{BASE_URL}/admin/ai-model-templates/icons"),
        ("POST", f"{BASE_URL}/admin/ai-model-templates"),
        ("GET", f"{BASE_URL}/admin/ai-config"),
        ("POST", f"{BASE_URL}/admin/ai-config"),
        ("GET", f"{BASE_URL}/admin/ai-config/sync-check"),
    ]
    for method, url in endpoints:
        if method == "GET":
            resp = await client.get(url)
        else:
            resp = await client.post(url, json={})
        assert resp.status_code in (401, 403, 422), (
            f"{method} {url} returned {resp.status_code}, expected 401/403"
        )


@pytest.mark.asyncio(loop_scope="module")
async def test_tc17_normal_user_get_active_config(client, user_headers):
    """TC-17: Normal user can access GET /admin/ai-config/active (uses get_current_user, not admin_dep)."""
    resp = await client.get(f"{BASE_URL}/admin/ai-config/active", headers=user_headers)
    assert resp.status_code in (200, 404), (
        f"Expected 200 or 404 (no active config), got {resp.status_code}"
    )
    if resp.status_code == 200:
        data = resp.json()
        assert "id" in data
        assert "provider_name" in data
