"""[PRD-405 2026-05-07] AI 对话模式首页配置 测试。

覆盖：
- T01 公共读取接口（无鉴权）返回默认配置
- T02 admin 整体保存
- T03 admin 按模块（welcome）保存
- T04 校验：问候语数组为空报 400
- T05 校验：浮动按钮 target_path 必须以 / 开头
- T06 操作日志：保存后写入日志
- T07 操作日志：内容未变化不写日志
- T08 推荐问 id 自动生成
- T09 idle_timeout 同步到 chat_idle_timeout_minutes
- T10 上传图片接口（无效 MIME）拒绝
"""
import io

import pytest
from httpx import AsyncClient


# ─────────── T01 ───────────


@pytest.mark.asyncio
async def test_t01_public_get_default(client: AsyncClient):
    resp = await client.get("/api/ai-home-config")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "config" in data
    cfg = data["config"]
    assert cfg["welcome"]["avatar"]["type"] == "emoji"
    assert cfg["topbar"]["title"]
    assert isinstance(cfg["recommended_questions"], list)


# ─────────── T02 ───────────


@pytest.mark.asyncio
async def test_t02_admin_put_full(client: AsyncClient, admin_headers):
    payload = {
        "welcome": {
            "avatar": {"type": "emoji", "emoji": "🩺"},
            "greetings": {
                "morning": ["早上好"],
                "afternoon": ["下午好"],
                "evening": ["晚上好"],
            },
            "subtitles": ["有什么健康问题想问我?"],
            "show_nickname": True,
        },
        "topbar": {
            "title": "AI 健康助手 V2",
            "logo": {"type": "emoji", "emoji": "🌿"},
            "show_sidebar": True,
            "show_more_menu": True,
            "show_share": False,
        },
        "input": {"placeholder": "问问吧..."},
        "session": {"idle_timeout_minutes": 60},
        "floating_button": {"target_path": "/health-check-in"},
        "banner": {"visible": True},
        "func_grid": {"columns": 3, "max_count": 6},
        "quick_tags": {"max_count": 8},
        "recommended_questions": [
            {"icon": "🩺", "title": "健康咨询", "question": "我最近经常头疼?"},
        ],
    }
    resp = await client.put("/api/admin/ai-home-config", json=payload, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    cfg = resp.json()["config"]
    assert cfg["topbar"]["title"] == "AI 健康助手 V2"
    assert cfg["topbar"]["show_share"] is False
    assert len(cfg["recommended_questions"]) == 1
    assert cfg["recommended_questions"][0]["id"]  # 自动补 id


# ─────────── T03 ───────────


@pytest.mark.asyncio
async def test_t03_admin_patch_module(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "title": "新标题",
            "show_share": False,
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/topbar", json=body, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    cfg = resp.json()["config"]
    assert cfg["topbar"]["title"] == "新标题"
    assert cfg["topbar"]["show_share"] is False


# ─────────── T04 ───────────


@pytest.mark.asyncio
async def test_t04_validate_greetings_empty(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "greetings": {"morning": [], "afternoon": ["下午好"], "evening": ["晚上好"]},
            "subtitles": ["你好"],
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/welcome", json=body, headers=admin_headers
    )
    assert resp.status_code == 400, resp.text
    assert "至少 1 条" in resp.json()["detail"]


# ─────────── T05 ───────────


@pytest.mark.asyncio
async def test_t05_validate_floating_target_path(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "enabled": True,
            "icon": "✅",
            "target_path": "https://evil.com/x",
            "position": "right_bottom",
            "show_label": False,
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/floating_button", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "/ 开头" in resp.json()["detail"]


# ─────────── T06 ───────────


@pytest.mark.asyncio
async def test_t06_log_written_on_change(client: AsyncClient, admin_headers):
    body = {"data": {"title": "Title-A"}}
    r1 = await client.patch(
        "/api/admin/ai-home-config/topbar", json=body, headers=admin_headers
    )
    assert r1.status_code == 200
    body2 = {"data": {"title": "Title-B"}}
    r2 = await client.patch(
        "/api/admin/ai-home-config/topbar", json=body2, headers=admin_headers
    )
    assert r2.status_code == 200
    logs = await client.get("/api/admin/ai-home-config/logs", headers=admin_headers)
    assert logs.status_code == 200, logs.text
    data = logs.json()
    assert data["total"] >= 2
    titles = [item["module"] for item in data["items"]]
    assert "topbar" in titles


# ─────────── T07 ───────────


@pytest.mark.asyncio
async def test_t07_no_log_when_no_change(client: AsyncClient, admin_headers):
    body = {"data": {"title": "Same-Title"}}
    await client.patch(
        "/api/admin/ai-home-config/topbar", json=body, headers=admin_headers
    )
    logs1 = (await client.get("/api/admin/ai-home-config/logs", headers=admin_headers)).json()
    cnt1 = logs1["total"]
    # 再 PATCH 一次完全相同的内容
    await client.patch(
        "/api/admin/ai-home-config/topbar", json=body, headers=admin_headers
    )
    logs2 = (await client.get("/api/admin/ai-home-config/logs", headers=admin_headers)).json()
    assert logs2["total"] == cnt1


# ─────────── T08 ───────────


@pytest.mark.asyncio
async def test_t08_recommended_question_id_auto(client: AsyncClient, admin_headers):
    body = {
        "data": [
            {"icon": "🩺", "title": "健康", "question": "Q1"},
            {"icon": "💊", "title": "用药", "question": "Q2", "id": "fixed-id-x"},
        ]
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/recommended_questions", json=body, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["config"]["recommended_questions"]
    assert items[0]["id"]
    assert items[1]["id"] == "fixed-id-x"


# ─────────── T09 ───────────


@pytest.mark.asyncio
async def test_t09_idle_timeout_sync(client: AsyncClient, admin_headers):
    body = {"data": {"idle_timeout_minutes": 60, "auto_new_session": True}}
    resp = await client.patch(
        "/api/admin/ai-home-config/session", json=body, headers=admin_headers
    )
    assert resp.status_code == 200
    # 通过 chat-idle-timeout 接口验证已同步
    sync_resp = await client.get("/api/app-settings/chat-idle-timeout")
    assert sync_resp.status_code == 200
    assert sync_resp.json()["data"]["timeout_minutes"] == 60


# ─────────── T10 ───────────


@pytest.mark.asyncio
async def test_t10_upload_invalid_mime(client: AsyncClient, admin_headers):
    files = {"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")}
    resp = await client.post(
        "/api/admin/ai-home-config/upload-image", files=files, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "PNG" in resp.json()["detail"] or "格式" in resp.json()["detail"]
