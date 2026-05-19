"""[PRD-PAGE-NAVIGATE-EXTERNAL-URL-FIX-V1 2026-05-19] 页面跳转类型 external_url 保存丢失 Bug 回归测试

Bug 本质：管理后台 admin-web 在保存 payload 时，把 external_url 字段的写入条件错写成
"仅 button_type='external_link' 时才传值"，导致新主类型 page_navigate 的 external_url
在 PUT/POST 请求中被强制写成 null，DB 中 external_url 被覆盖为 NULL。

修复策略：放开 admin-web 端 external_url 的类型白名单，允许 page_navigate 与 external_link
两种类型都写入 external_url。后端校验逻辑保持不变（`_validate_navigate_url` 只校验非空时
格式合法性，允许 null 写入，避免老脏数据失败）。

本测试文件覆盖后端 API 行为是否正确，确保：
- TC-01：page_navigate + 内部路径 `/health-profile` 可被后端正确接收并写入
- TC-02：page_navigate + http 外链可被后端正确接收并写入
- TC-03：page_navigate + 先弹卡片=是 配合 external_url 可被正确写入
- TC-04：old external_link 类型不受影响（向后兼容）
- TC-05：保存往返一致性（POST 创建 + GET 读取，字段值不丢失）
- TC-06：PUT 更新 external_url 写入正确
- TC-07：page_navigate 类型 + 显式置 null 时，可清空 external_url（切类型场景）
- TC-08：page_navigate + 非法 external_url（既不是 http(s) 也不是 / 开头）时返回 400
"""
import pytest
from httpx import AsyncClient


def _navigate_btn_payload(name: str, external_url, **overrides):
    base = {
        "name": name,
        "icon": "🏠",
        "button_type": "page_navigate",
        "external_url": external_url,
        "sort_weight": 0,
        "is_enabled": True,
        "is_recommended": True,
        "is_capsule": False,
        "pre_card_for_navigate": False,
        "auto_user_message": "",
        "card_title": name,
    }
    base.update(overrides)
    return base


async def _fetch_admin_btn_by_id(client: AsyncClient, admin_headers, btn_id: int):
    """通过 admin 列表接口（GET /api/admin/function-buttons）回读单个按钮"""
    r = await client.get(
        "/api/admin/function-buttons",
        params={"page_size": 100},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items") if isinstance(body, dict) else body
    if items is None:
        items = body
    return next((b for b in items if b.get("id") == btn_id), None)


# ─────────────────── TC-01 ───────────────────
@pytest.mark.asyncio
async def test_page_navigate_internal_path_persisted(client: AsyncClient, admin_headers):
    """page_navigate + 内部路径 /health-profile 保存往返一致"""
    payload = _navigate_btn_payload("健康档案-TC01", "/health-profile")
    r = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    btn_id = r.json()["id"]
    # POST 创建接口直接返回 ChatFunctionButtonResponse
    created = r.json()
    assert created["external_url"] == "/health-profile", (
        f"POST 创建后返回值 external_url 已丢失={created.get('external_url')!r}"
    )

    data = await _fetch_admin_btn_by_id(client, admin_headers, btn_id)
    assert data is not None, "新建按钮在 admin 列表中找不到"
    assert data["button_type"] == "page_navigate"
    assert data["external_url"] == "/health-profile", (
        f"external_url 在保存后丢失！实际值={data.get('external_url')!r}（Bug 还原：之前会被擦成 null）"
    )


# ─────────────────── TC-02 ───────────────────
@pytest.mark.asyncio
async def test_page_navigate_external_http_url_persisted(client: AsyncClient, admin_headers):
    """page_navigate + http 外链保存往返一致"""
    payload = _navigate_btn_payload("外链-TC02", "https://example.com/health")
    r = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    btn_id = r.json()["id"]

    data = await _fetch_admin_btn_by_id(client, admin_headers, btn_id)
    assert data is not None
    assert data["external_url"] == "https://example.com/health"


# ─────────────────── TC-03 ───────────────────
@pytest.mark.asyncio
async def test_page_navigate_with_pre_card_enabled_persisted(client: AsyncClient, admin_headers):
    """page_navigate + 先弹卡片=true 仍能正确保存 external_url"""
    payload = _navigate_btn_payload(
        "弹卡片再跳-TC03", "/health-profile", pre_card_for_navigate=True
    )
    r = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    btn_id = r.json()["id"]

    data = await _fetch_admin_btn_by_id(client, admin_headers, btn_id)
    assert data is not None
    assert data["external_url"] == "/health-profile"
    assert data["pre_card_for_navigate"] is True


# ─────────────────── TC-04 ───────────────────
@pytest.mark.asyncio
async def test_old_external_link_type_not_affected(client: AsyncClient, admin_headers):
    """老 external_link 类型保存 external_url 行为保持不变"""
    payload = {
        "name": "老外链-TC04",
        "icon": "🔗",
        "button_type": "external_link",
        "external_url": "https://legacy.example.com",
        "sort_weight": 0,
        "is_enabled": True,
        "is_recommended": True,
        "is_capsule": False,
        "auto_user_message": "",
        "card_title": "老外链",
    }
    r = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    btn_id = r.json()["id"]

    data = await _fetch_admin_btn_by_id(client, admin_headers, btn_id)
    assert data is not None
    assert data["external_url"] == "https://legacy.example.com"


# ─────────────────── TC-05 ───────────────────
@pytest.mark.asyncio
async def test_public_function_buttons_api_returns_external_url(client: AsyncClient, admin_headers):
    """公开接口 /api/function-buttons 返回 page_navigate 按钮的 external_url"""
    payload = _navigate_btn_payload("公开TC05", "/health-profile")
    r = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert r.status_code == 200

    r2 = await client.get("/api/function-buttons", params={"position": "grid"})
    assert r2.status_code == 200, r2.text
    items = r2.json()
    if isinstance(items, dict) and "items" in items:
        items = items["items"]
    target = next((b for b in items if b.get("name") == "公开TC05"), None)
    assert target is not None, "在公开接口未找到 TC05 按钮"
    assert target.get("external_url") == "/health-profile", (
        f"公开接口未返回 external_url，H5 端会失去跳转目标。实际值={target.get('external_url')!r}"
    )


# ─────────────────── TC-06 ───────────────────
@pytest.mark.asyncio
async def test_page_navigate_update_external_url(client: AsyncClient, admin_headers):
    """PUT 更新 page_navigate 按钮的 external_url 写入正确"""
    payload = _navigate_btn_payload("更新TC06", "/old-path")
    r = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert r.status_code == 200
    btn_id = r.json()["id"]

    update_payload = dict(payload)
    update_payload["external_url"] = "/new-path"
    r2 = await client.put(
        f"/api/admin/function-buttons/{btn_id}", json=update_payload, headers=admin_headers
    )
    assert r2.status_code == 200, r2.text

    data = await _fetch_admin_btn_by_id(client, admin_headers, btn_id)
    assert data is not None
    assert data["external_url"] == "/new-path"


# ─────────────────── TC-07 ───────────────────
@pytest.mark.asyncio
async def test_switch_type_clears_external_url(client: AsyncClient, admin_headers):
    """切类型场景：page_navigate -> ai_function，external_url 显式置 null 允许"""
    payload = _navigate_btn_payload("切类型TC07", "/health-profile")
    r = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert r.status_code == 200
    btn_id = r.json()["id"]

    update_payload = {
        "name": "切类型TC07",
        "icon": "📌",
        "button_type": "ai_function",
        "ai_function_type": "quick_ask",
        "preset_prompt": "你好",
        "external_url": None,
        "sort_weight": 0,
        "is_enabled": True,
        "is_recommended": True,
        "is_capsule": False,
        "auto_user_message": "",
        "card_title": "切类型TC07",
    }
    r2 = await client.put(
        f"/api/admin/function-buttons/{btn_id}", json=update_payload, headers=admin_headers
    )
    assert r2.status_code == 200, r2.text

    data = await _fetch_admin_btn_by_id(client, admin_headers, btn_id)
    assert data is not None
    assert data["button_type"] == "ai_function"
    assert data["external_url"] in (None, ""), f"切类型后 external_url 应被清空，实际={data['external_url']!r}"


# ─────────────────── TC-08 ───────────────────
@pytest.mark.asyncio
async def test_page_navigate_invalid_external_url_returns_400(client: AsyncClient, admin_headers):
    """page_navigate + 非法 external_url（不是 http(s)/ 也不是 / 开头）返回 400"""
    payload = _navigate_btn_payload("非法URL-TC08", "javascript:alert(1)")
    r = await client.post("/api/admin/function-buttons", json=payload, headers=admin_headers)
    assert r.status_code in (400, 422), (
        f"非法 external_url 应被拒绝（400/422），实际状态码={r.status_code}, 响应={r.text}"
    )
