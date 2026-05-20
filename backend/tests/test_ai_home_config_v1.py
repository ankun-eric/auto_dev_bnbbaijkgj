"""[PRD-405 v1.0 2026-05-08] AI 对话模式首页配置 v1.0 测试。

覆盖 v1.0 新字段：
- T11 v1.0 公共读取返回新模块默认值（health_tips/empty_placeholder/global_switches/func_grid.items）
- T12 admin 保存 func_grid.items 7 字段
- T13 校验：func_grid.items 数量超过 6 报 400
- T14 校验：func_grid.items[*].main_text 超过 8 字报 400
- T15 校验：func_grid.items[*].gradient_start 非合法 HEX 报 400
- T16 校验：input.family_consult.template 不含 {name} 报 400
- T17 校验：session.strategy.max_answer_chars 越界报 400
- T18 admin 保存 global_switches 9 个开关
- T19 admin 保存 health_tips 间隔 3~5
- T20 admin 保存 empty_placeholder
- T21 校验：recommended_questions[*].title 超过 8 字报 400
- T22 校验：welcome.main_title 超过 30 字报 400
"""
import pytest
from httpx import AsyncClient


# ─────────── T11 ───────────


@pytest.mark.asyncio
async def test_t11_public_get_v1_default(client: AsyncClient):
    resp = await client.get("/api/ai-home-config")
    assert resp.status_code == 200, resp.text
    cfg = resp.json()["config"]
    # v1.0 新模块都有默认值
    assert "health_tips" in cfg
    assert cfg["health_tips"]["interval_seconds"] == 4
    assert cfg["health_tips"]["show_indicator"] is True
    assert "empty_placeholder" in cfg
    assert cfg["empty_placeholder"]["icon"] == "💬"
    assert "global_switches" in cfg
    assert cfg["global_switches"]["welcome_visible"] is True
    assert cfg["global_switches"]["floating_button_visible"] is True
    # func_grid.items 默认 3 项
    items = cfg["func_grid"]["items"]
    assert len(items) >= 3
    assert items[0]["main_text"] == "AI诊室"
    # welcome v1.0 主副标题
    assert "main_title" in cfg["welcome"]
    assert "{昵称}" in cfg["welcome"]["main_title"]
    # input.family_consult
    assert cfg["input"]["family_consult"]["enabled"] is True
    assert "{name}" in cfg["input"]["family_consult"]["template"]
    # session.strategy
    assert cfg["session"]["strategy"]["max_answer_chars"] == 1000
    assert cfg["session"]["strategy"]["context_memory_rounds"] == 5


# ─────────── T12 ───────────


@pytest.mark.asyncio
async def test_t12_save_func_grid_items(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "visible": True,
            "columns": 3,
            "max_count": 6,
            "items": [
                {
                    "main_text": "AI诊室",
                    "sub_text": "智能问诊",
                    "target_path": "/ai-doctor",
                    "icon": "🩺",
                    "gradient_start": "#5B6CFF",
                    "gradient_end": "#8B9AFF",
                    "badge": "NEW",
                    "enabled": True,
                    "sort": 1,
                },
                {
                    "main_text": "看报告",
                    "sub_text": "解读体检",
                    "target_path": "/checkup",
                    "icon": "📋",
                    "gradient_start": "#FF7E5F",
                    "gradient_end": "#FEB47B",
                    "enabled": True,
                    "sort": 2,
                },
            ],
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/func_grid", json=body, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    cfg = resp.json()["config"]
    items = cfg["func_grid"]["items"]
    assert len(items) == 2
    assert items[0]["main_text"] == "AI诊室"
    assert items[0]["badge"] == "NEW"
    # id 自动生成
    assert items[0]["id"]
    assert items[1]["id"]


# ─────────── T13 ───────────


@pytest.mark.asyncio
async def test_t13_func_grid_items_too_many(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "items": [
                {
                    "main_text": f"项{i}",
                    "sub_text": "副",
                    "target_path": "/x",
                    "icon": "📌",
                    "gradient_start": "#5B6CFF",
                    "gradient_end": "#8B9AFF",
                    "enabled": True,
                    "sort": i,
                }
                for i in range(7)  # 7 项超过 6
            ]
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/func_grid", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "1~6" in resp.json()["detail"]


# ─────────── T14 ───────────


@pytest.mark.asyncio
async def test_t14_func_grid_main_text_too_long(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "items": [
                {
                    "main_text": "这是一个超过八个字的主文案",  # 13 字
                    "sub_text": "副",
                    "target_path": "/x",
                    "icon": "📌",
                    "gradient_start": "#5B6CFF",
                    "gradient_end": "#8B9AFF",
                    "enabled": True,
                    "sort": 1,
                }
            ]
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/func_grid", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "main_text" in resp.json()["detail"]


# ─────────── T15 ───────────


@pytest.mark.asyncio
async def test_t15_func_grid_invalid_hex(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "items": [
                {
                    "main_text": "AI诊室",
                    "sub_text": "智能问诊",
                    "target_path": "/x",
                    "icon": "📌",
                    "gradient_start": "not-a-color",  # 非法
                    "gradient_end": "#8B9AFF",
                    "enabled": True,
                    "sort": 1,
                }
            ]
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/func_grid", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "HEX" in resp.json()["detail"]


# ─────────── T16 ───────────


@pytest.mark.asyncio
async def test_t16_family_consult_template_no_placeholder(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "placeholder": "发消息...",
            "enable_voice": True,
            "enable_tts": True,
            "tts_provider": "auto",
            "family_consult": {
                "enabled": True,
                "template": "为本人咨询",  # 缺 {name} 占位符
                "show_archive_link": True,
                "archive_path": "/health-profile",
            },
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/input", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "{name}" in resp.json()["detail"]


# ─────────── T17 ───────────


@pytest.mark.asyncio
async def test_t17_strategy_max_chars_out_of_range(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "idle_timeout_minutes": 30,
            "auto_new_session": True,
            "empty_session_welcome": {"enabled": False, "messages": []},
            "strategy": {
                "max_answer_chars": 50,  # 越界 < 100
                "show_loading": True,
                "daily_free_quota": 50,
                "answer_style": "friendly",
                "sensitive_filter": True,
                "context_memory_rounds": 5,
                "disclaimer": "test",
            },
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/session", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "max_answer_chars" in resp.json()["detail"]


# ─────────── T18 ───────────


@pytest.mark.asyncio
async def test_t18_save_global_switches(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "welcome_visible": False,
            "health_tips_visible": True,
            "func_grid_visible": True,
            "recommended_visible": False,
            "empty_placeholder_visible": True,
            "family_pill_visible": False,
            "archive_link_visible": True,
            "voice_input_visible": False,
            "floating_button_visible": True,
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/global_switches", json=body, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    sw = resp.json()["config"]["global_switches"]
    assert sw["welcome_visible"] is False
    assert sw["recommended_visible"] is False
    assert sw["family_pill_visible"] is False
    assert sw["voice_input_visible"] is False


# ─────────── T19 ───────────


@pytest.mark.asyncio
async def test_t19_health_tips_interval(client: AsyncClient, admin_headers):
    # 合法值 5
    body_ok = {"data": {"visible": True, "interval_seconds": 5, "show_indicator": True}}
    r1 = await client.patch(
        "/api/admin/ai-home-config/health_tips", json=body_ok, headers=admin_headers
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["config"]["health_tips"]["interval_seconds"] == 5

    # 越界 6 → 400
    body_bad = {"data": {"visible": True, "interval_seconds": 6, "show_indicator": True}}
    r2 = await client.patch(
        "/api/admin/ai-home-config/health_tips", json=body_bad, headers=admin_headers
    )
    assert r2.status_code == 400
    assert "3~5" in r2.json()["detail"]


# ─────────── T20 ───────────


@pytest.mark.asyncio
async def test_t20_save_empty_placeholder(client: AsyncClient, admin_headers):
    body = {"data": {"icon": "🌟", "main_title": "暂无对话"}}
    resp = await client.patch(
        "/api/admin/ai-home-config/empty_placeholder", json=body, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    cfg = resp.json()["config"]
    assert cfg["empty_placeholder"]["icon"] == "🌟"
    assert cfg["empty_placeholder"]["main_title"] == "暂无对话"


# ─────────── T21 ───────────


@pytest.mark.asyncio
async def test_t21_recommended_title_too_long(client: AsyncClient, admin_headers):
    body = {
        "data": [
            {"icon": "📋", "title": "这是一个超过八个字的标题", "question": "问题"},  # 13 字
        ]
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/recommended_questions", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "title" in resp.json()["detail"]


# ─────────── T22 ───────────


@pytest.mark.asyncio
async def test_t22_welcome_main_title_too_long(client: AsyncClient, admin_headers):
    body = {
        "data": {
            "main_title": "x" * 31,  # 超过 30 字
            "sub_title": "副",
            "greetings": {
                "morning": ["早上好"],
                "afternoon": ["下午好"],
                "evening": ["晚上好"],
            },
            "subtitles": ["你好"],
            "show_nickname": True,
            "avatar": {"type": "emoji", "emoji": "🌿"},
        }
    }
    resp = await client.patch(
        "/api/admin/ai-home-config/welcome", json=body, headers=admin_headers
    )
    assert resp.status_code == 400
    assert "main_title" in resp.json()["detail"]
