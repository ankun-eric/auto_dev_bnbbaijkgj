"""[PRD-414 v1.1 2026-05-08] AI 对话页 v1.1 后端测试（ai_chat 模块）。

覆盖：
- T01 公共读取 /api/ai-home-config 返回 ai_chat 默认值（avatar/signature/profile_row_template 等）
- T02 admin PATCH /api/admin/ai-home-config/ai_chat 保存 emoji 头像 + 自定义署名
- T03 admin PATCH 保存 image 类型头像（合法 url）
- T04 校验：ai_chat.avatar.type 非法 → 400
- T05 校验：ai_chat.profile_row_template 缺失 {name} → 400
- T06 校验：ai_chat.signature 超过 10 字 → 400
- T07 校验：ai_chat.history_retention_days 越界 → 400
- T08 PATCH 保存的 ai_chat 配置在 GET 接口中可读回
"""
import pytest
from httpx import AsyncClient


# ─────────── T01 ───────────


@pytest.mark.asyncio
async def test_t01_public_get_ai_chat_default(client: AsyncClient):
    resp = await client.get("/api/ai-home-config")
    assert resp.status_code == 200, resp.text
    cfg = resp.json()["config"]
    assert "ai_chat" in cfg
    chat = cfg["ai_chat"]
    # 默认值
    assert chat["signature"] == "小康"
    assert chat["profile_row_enabled"] is True
    assert "{name}" in chat["profile_row_template"]
    assert chat["punchcard_draggable"] is True
    assert chat["scroll_to_bottom_button"] is True
    assert chat["sticky_topbar"] is True
    assert chat["history_retention_days"] == 0
    assert chat["avatar"]["type"] in ("emoji", "image")


# ─────────── T02 ───────────


@pytest.mark.asyncio
async def test_t02_patch_ai_chat_emoji(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "avatar": {"type": "emoji", "emoji": "🦊", "image_url": ""},
            "signature": "小康",
            "profile_row_enabled": True,
            "profile_row_template": "本次回答结合 {name} 的档案",
            "punchcard_draggable": True,
            "scroll_to_bottom_button": True,
            "sticky_topbar": True,
            "history_retention_days": 0,
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/ai_chat", json=body, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    cfg = resp.json()["config"]
    assert cfg["ai_chat"]["avatar"]["emoji"] == "🦊"
    assert cfg["ai_chat"]["signature"] == "小康"


# ─────────── T03 ───────────


@pytest.mark.asyncio
async def test_t03_patch_ai_chat_image(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "avatar": {
                "type": "image",
                "emoji": "",
                "image_url": "/uploads/ai_home_config/aih_xxx.png",
            },
            "signature": "康康",
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/ai_chat", json=body, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    chat = resp.json()["config"]["ai_chat"]
    assert chat["avatar"]["type"] == "image"
    assert chat["avatar"]["image_url"].startswith("/uploads/")
    assert chat["signature"] == "康康"


# ─────────── T04 ───────────


@pytest.mark.asyncio
async def test_t04_invalid_avatar_type(client: AsyncClient, admin_headers):
    body = {"data": {"avatar": {"type": "INVALID", "emoji": "", "image_url": ""}}}
    resp = await client.patch(
        "/api/admin/ai-home-config/ai_chat", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "ai_chat.avatar.type" in resp.text


# ─────────── T05 ───────────


@pytest.mark.asyncio
async def test_t05_template_without_name_placeholder(client: AsyncClient, admin_headers):
    body = {"data": {"profile_row_template": "本次回答仅供参考"}}
    resp = await client.patch(
        "/api/admin/ai-home-config/ai_chat", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "{name}" in resp.text


# ─────────── T06 ───────────


@pytest.mark.asyncio
async def test_t06_signature_too_long(client: AsyncClient, admin_headers):
    body = {"data": {"signature": "这是一个超过十字的非法AI署名内容"}}
    resp = await client.patch(
        "/api/admin/ai-home-config/ai_chat", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "signature" in resp.text


# ─────────── T07 ───────────


@pytest.mark.asyncio
async def test_t07_retention_out_of_range(client: AsyncClient, admin_headers):
    body = {"data": {"history_retention_days": -5}}
    resp = await client.patch(
        "/api/admin/ai-home-config/ai_chat", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "history_retention_days" in resp.text


# ─────────── T08 ───────────


@pytest.mark.asyncio
async def test_t08_patch_then_public_get(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "avatar": {"type": "emoji", "emoji": "🐼", "image_url": ""},
            "signature": "小康",
            "profile_row_enabled": False,
            "profile_row_template": "为 {name} 服务",
        }
    }
    p = await client.patch(
        "/api/admin/ai-home-config/ai_chat", json=body, headers=admin_headers
    )
    assert p.status_code == 200, p.text
    g = await client.get("/api/ai-home-config")
    assert g.status_code == 200
    chat = g.json()["config"]["ai_chat"]
    assert chat["avatar"]["emoji"] == "🐼"
    assert chat["profile_row_enabled"] is False
    assert chat["profile_row_template"] == "为 {name} 服务"
