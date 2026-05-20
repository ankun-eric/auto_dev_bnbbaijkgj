"""[PRD-411 2026-05-08] AI 对话首页配置 - 6 Tab 化改造 后端契约验证。

PRD-411 把 admin 页面从"伪 Tab 锚点滚动"升级为"真 Tab 切换 + 每 Tab 独立保存"，
本次需求**不改后端 schema/路由**，仅依赖现有 PATCH /api/admin/ai-home-config/{module} 即可。

本测试聚焦验证：在前端 Tab 化改造后，前端会按 6 个 Tab 维度分别调用模块化 PATCH，
后端必须为每个 Tab 涉及的所有模块都提供独立、互不影响的保存能力，且不会因为
"只保存一个 Tab"而把其他 Tab 的内容一并清空（独立保存语义 R-01/R-04）。

| Tab | 涉及模块（前端会按顺序 PATCH） |
|---|---|
| 1 欢迎区 | welcome |
| 2 首屏内容 | health_tips, empty_placeholder, recommended_questions |
| 3 功能宫格 | func_grid |
| 4 输入栏 | input |
| 5 会话策略 | session |
| 6 全局开关 | global_switches, floating_button, topbar |

用例清单：
- TAB01 Tab 1 仅保存 welcome 不影响 input/session/topbar
- TAB02 Tab 2 顺序保存 health_tips + empty_placeholder + recommended_questions 三模块
- TAB03 Tab 3 保存 func_grid 不影响 health_tips
- TAB04 Tab 4 保存 input 不影响 welcome/session
- TAB05 Tab 5 保存 session 不影响 input/welcome
- TAB06 Tab 6 顺序保存 global_switches + floating_button + topbar 三模块
- TAB07 6 个 Tab 全部交叉保存后，所有字段最终值均符合最后一次保存
- TAB08 PATCH 失败（如 func_grid items 数量超 6）时不污染其他模块
"""
import pytest
from httpx import AsyncClient


PATCH_BASE = "/api/admin/ai-home-config"


async def _patch(client: AsyncClient, headers: dict, mod: str, data) -> dict:
    """便捷封装：PATCH 单模块，返回最新整体 config dict。"""
    resp = await client.patch(f"{PATCH_BASE}/{mod}", json={"data": data}, headers=headers)
    assert resp.status_code == 200, f"PATCH {mod} 失败: {resp.status_code} {resp.text}"
    return resp.json()["config"]


async def _get(client: AsyncClient, headers: dict) -> dict:
    resp = await client.get(PATCH_BASE, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["config"]


# ─────────── TAB01 ───────────


@pytest.mark.asyncio
async def test_tab01_welcome_only_isolation(client: AsyncClient, admin_headers):
    """Tab 1 保存 welcome，topbar/input/session 字段不受影响。"""
    before = await _get(client, admin_headers)
    topbar_title_before = before["topbar"]["title"]
    input_placeholder_before = before["input"]["placeholder"]

    new_welcome = {
        "avatar": {"type": "emoji", "emoji": "🌞"},
        "greetings": {
            "morning": ["TAB01-早上好"],
            "afternoon": ["TAB01-午安"],
            "evening": ["TAB01-晚上好"],
        },
        "subtitles": ["TAB01 副标题"],
        "show_nickname": True,
        "main_title": "TAB01 主标题，{昵称}！",
        "sub_title": "TAB01 副标题",
    }
    cfg = await _patch(client, admin_headers, "welcome", new_welcome)
    assert cfg["welcome"]["main_title"] == "TAB01 主标题，{昵称}！"
    # 其他模块保持
    assert cfg["topbar"]["title"] == topbar_title_before
    assert cfg["input"]["placeholder"] == input_placeholder_before


# ─────────── TAB02 ───────────


@pytest.mark.asyncio
async def test_tab02_first_screen_three_modules(client: AsyncClient, admin_headers):
    """Tab 2 按顺序 PATCH health_tips + empty_placeholder + recommended_questions。"""
    cfg = await _patch(client, admin_headers, "health_tips", {
        "visible": True,
        "interval_seconds": 5,
        "show_indicator": False,
    })
    assert cfg["health_tips"]["interval_seconds"] == 5
    assert cfg["health_tips"]["show_indicator"] is False

    cfg = await _patch(client, admin_headers, "empty_placeholder", {
        "icon": "🌱",
        "main_title": "TAB02 空对话",
    })
    assert cfg["empty_placeholder"]["main_title"] == "TAB02 空对话"
    # 上一次的 health_tips 保留
    assert cfg["health_tips"]["interval_seconds"] == 5

    cfg = await _patch(client, admin_headers, "recommended_questions", [
        {"id": "tab02_r1", "icon": "📋", "title": "TAB02 问1", "question": "TAB02 提问1", "enabled": True, "sort": 1},
        {"id": "tab02_r2", "icon": "💊", "title": "TAB02 问2", "question": "TAB02 提问2", "enabled": True, "sort": 2},
    ])
    assert len(cfg["recommended_questions"]) == 2
    assert cfg["recommended_questions"][0]["title"] == "TAB02 问1"
    # 上两次保存仍在
    assert cfg["empty_placeholder"]["main_title"] == "TAB02 空对话"
    assert cfg["health_tips"]["show_indicator"] is False


# ─────────── TAB03 ───────────


@pytest.mark.asyncio
async def test_tab03_func_grid_isolation(client: AsyncClient, admin_headers):
    """Tab 3 保存 func_grid 后，Tab 2 的 health_tips 字段不被影响。"""
    # 先记录 health_tips 当前值
    cfg_before = await _get(client, admin_headers)
    ht_before = cfg_before["health_tips"]

    new_grid = {
        "visible": True,
        "columns": 4,
        "max_count": 6,
        "items": [
            {
                "id": f"tab03_g{i}",
                "main_text": f"宫{i}",
                "sub_text": f"说明{i}",
                "target_path": f"/p{i}",
                "icon": "✨",
                "gradient_start": "#5B6CFF",
                "gradient_end": "#8B9AFF",
                "badge": "",
                "enabled": True,
                "sort": i,
            }
            for i in range(1, 5)
        ],
    }
    cfg = await _patch(client, admin_headers, "func_grid", new_grid)
    assert len(cfg["func_grid"]["items"]) == 4
    assert cfg["func_grid"]["columns"] == 4
    # health_tips 没变
    assert cfg["health_tips"]["interval_seconds"] == ht_before["interval_seconds"]


# ─────────── TAB04 ───────────


@pytest.mark.asyncio
async def test_tab04_input_isolation(client: AsyncClient, admin_headers):
    """Tab 4 保存 input 不影响 welcome/session。"""
    cfg_before = await _get(client, admin_headers)
    welcome_main_before = cfg_before["welcome"]["main_title"]
    session_disclaimer_before = cfg_before["session"]["strategy"]["disclaimer"]

    new_input = {
        "placeholder": "TAB04 占位符",
        "enable_voice": False,
        "enable_tts": True,
        "tts_provider": "cloud",
        "family_consult": {
            "enabled": True,
            "template": "为({name})咨询 - TAB04",
            "show_archive_link": False,
            "archive_path": "/health-profile",
        },
    }
    cfg = await _patch(client, admin_headers, "input", new_input)
    assert cfg["input"]["placeholder"] == "TAB04 占位符"
    assert cfg["input"]["enable_voice"] is False
    assert cfg["input"]["family_consult"]["template"] == "为({name})咨询 - TAB04"
    assert cfg["welcome"]["main_title"] == welcome_main_before
    assert cfg["session"]["strategy"]["disclaimer"] == session_disclaimer_before


# ─────────── TAB05 ───────────


@pytest.mark.asyncio
async def test_tab05_session_isolation(client: AsyncClient, admin_headers):
    """Tab 5 保存 session 不影响 input/welcome。"""
    cfg_before = await _get(client, admin_headers)
    input_ph_before = cfg_before["input"]["placeholder"]

    new_session = {
        "idle_timeout_minutes": 45,
        "auto_new_session": False,
        "empty_session_welcome": {
            "enabled": True,
            "messages": ["TAB05 欢迎语"],
        },
        "strategy": {
            "max_answer_chars": 2000,
            "show_loading": False,
            "daily_free_quota": 100,
            "answer_style": "professional",
            "sensitive_filter": True,
            "context_memory_rounds": 10,
            "disclaimer": "TAB05 免责声明",
        },
    }
    cfg = await _patch(client, admin_headers, "session", new_session)
    assert cfg["session"]["idle_timeout_minutes"] == 45
    assert cfg["session"]["strategy"]["max_answer_chars"] == 2000
    assert cfg["session"]["strategy"]["context_memory_rounds"] == 10
    assert cfg["input"]["placeholder"] == input_ph_before


# ─────────── TAB06 ───────────


@pytest.mark.asyncio
async def test_tab06_global_three_modules(client: AsyncClient, admin_headers):
    """Tab 6 顺序 PATCH global_switches + floating_button + topbar。"""
    cfg = await _patch(client, admin_headers, "global_switches", {
        "welcome_visible": False,
        "health_tips_visible": True,
        "func_grid_visible": True,
        "recommended_visible": True,
        "empty_placeholder_visible": True,
        "family_pill_visible": False,
        "archive_link_visible": True,
        "voice_input_visible": False,
        "floating_button_visible": True,
    })
    assert cfg["global_switches"]["welcome_visible"] is False
    assert cfg["global_switches"]["voice_input_visible"] is False

    cfg = await _patch(client, admin_headers, "floating_button", {
        "enabled": True,
        "icon": "🏃",
        "label": "TAB06 打卡",
        "show_label": True,
        "target_path": "/health-checkin",
        "position": "left_bottom",
    })
    assert cfg["floating_button"]["icon"] == "🏃"
    assert cfg["floating_button"]["position"] == "left_bottom"
    # 上一次 global_switches 保留
    assert cfg["global_switches"]["welcome_visible"] is False

    cfg = await _patch(client, admin_headers, "topbar", {
        "title": "TAB06 顶栏",
        "logo": {"type": "emoji", "emoji": "🌿"},
        "show_sidebar": True,
        "show_more_menu": True,
        "show_share": False,
        "visible": True,
    })
    assert cfg["topbar"]["title"] == "TAB06 顶栏"
    assert cfg["topbar"]["visible"] is True
    # 前两次保留
    assert cfg["floating_button"]["icon"] == "🏃"
    assert cfg["global_switches"]["welcome_visible"] is False


# ─────────── TAB07 ───────────


@pytest.mark.asyncio
async def test_tab07_cross_tab_save_finalstate(client: AsyncClient, admin_headers):
    """6 Tab 全部交叉保存后，最终配置整体一致符合最后一次写入值。"""
    # Tab 1 → welcome
    await _patch(client, admin_headers, "welcome", {
        "avatar": {"type": "emoji", "emoji": "🌞"},
        "greetings": {"morning": ["m"], "afternoon": ["a"], "evening": ["e"]},
        "subtitles": ["s"],
        "show_nickname": True,
        "main_title": "TAB07 主标题",
        "sub_title": "TAB07 副标题",
    })
    # Tab 2 → health_tips + empty_placeholder + recommended_questions
    await _patch(client, admin_headers, "health_tips", {"visible": True, "interval_seconds": 3, "show_indicator": True})
    await _patch(client, admin_headers, "empty_placeholder", {"icon": "💬", "main_title": "TAB07 空"})
    await _patch(client, admin_headers, "recommended_questions", [
        {"id": "x1", "icon": "📋", "title": "TAB07 问", "question": "Q", "enabled": True, "sort": 1},
    ])
    # Tab 3 → func_grid
    await _patch(client, admin_headers, "func_grid", {
        "visible": True,
        "columns": 2,
        "max_count": 6,
        "items": [
            {"id": "g1", "main_text": "TAB07宫", "sub_text": "x", "target_path": "/x", "icon": "✨",
             "gradient_start": "#5B6CFF", "gradient_end": "#8B9AFF", "badge": "", "enabled": True, "sort": 1},
        ],
    })
    # Tab 4 → input
    await _patch(client, admin_headers, "input", {
        "placeholder": "TAB07 输入",
        "enable_voice": True,
        "enable_tts": True,
        "tts_provider": "auto",
        "family_consult": {"enabled": True, "template": "为({name})咨询", "show_archive_link": True, "archive_path": "/health-profile"},
    })
    # Tab 5 → session
    await _patch(client, admin_headers, "session", {
        "idle_timeout_minutes": 30,
        "auto_new_session": True,
        "empty_session_welcome": {"enabled": False, "messages": []},
        "strategy": {
            "max_answer_chars": 1500,
            "show_loading": True,
            "daily_free_quota": 60,
            "answer_style": "easy",
            "sensitive_filter": True,
            "context_memory_rounds": 5,
            "disclaimer": "TAB07 免责",
        },
    })
    # Tab 6 → global_switches + floating_button + topbar
    await _patch(client, admin_headers, "global_switches", {
        "welcome_visible": True, "health_tips_visible": True, "func_grid_visible": True,
        "recommended_visible": True, "empty_placeholder_visible": True, "family_pill_visible": True,
        "archive_link_visible": True, "voice_input_visible": True, "floating_button_visible": False,
    })
    await _patch(client, admin_headers, "floating_button", {
        "enabled": False, "icon": "✅", "label": "off", "show_label": False,
        "target_path": "/health-plan", "position": "right_bottom",
    })
    await _patch(client, admin_headers, "topbar", {
        "title": "TAB07 顶栏",
        "logo": {"type": "emoji", "emoji": "🌿"},
        "show_sidebar": True, "show_more_menu": True, "show_share": True, "visible": False,
    })

    # 最终读取所有字段都符合最后一次写入
    cfg = await _get(client, admin_headers)
    assert cfg["welcome"]["main_title"] == "TAB07 主标题"
    assert cfg["health_tips"]["interval_seconds"] == 3
    assert cfg["empty_placeholder"]["main_title"] == "TAB07 空"
    assert len(cfg["recommended_questions"]) == 1
    assert cfg["recommended_questions"][0]["title"] == "TAB07 问"
    assert cfg["func_grid"]["columns"] == 2
    assert cfg["input"]["placeholder"] == "TAB07 输入"
    assert cfg["session"]["strategy"]["max_answer_chars"] == 1500
    assert cfg["global_switches"]["floating_button_visible"] is False
    assert cfg["floating_button"]["enabled"] is False
    assert cfg["topbar"]["title"] == "TAB07 顶栏"


# ─────────── TAB08 ───────────


@pytest.mark.asyncio
async def test_tab08_failed_patch_does_not_pollute(client: AsyncClient, admin_headers):
    """func_grid items 数量超过 6 时返回 400，且其他模块字段未被任何写入。"""
    # 先用一个良好已知值保存 welcome 作为基准
    cfg_before = await _patch(client, admin_headers, "welcome", {
        "avatar": {"type": "emoji", "emoji": "🌿"},
        "greetings": {"morning": ["A"], "afternoon": ["B"], "evening": ["C"]},
        "subtitles": ["S"],
        "show_nickname": True,
        "main_title": "TAB08-基准主标题",
        "sub_title": "TAB08-基准副标题",
    })
    welcome_baseline = cfg_before["welcome"]["main_title"]

    # 故意构造非法 func_grid（7 项超出上限）
    bad_grid = {
        "visible": True,
        "columns": 3,
        "max_count": 6,
        "items": [
            {"id": f"bad{i}", "main_text": f"M{i}", "sub_text": "x", "target_path": "/x", "icon": "✨",
             "gradient_start": "#5B6CFF", "gradient_end": "#8B9AFF", "badge": "", "enabled": True, "sort": i}
            for i in range(1, 8)
        ],
    }
    resp = await client.patch(f"{PATCH_BASE}/func_grid", json={"data": bad_grid}, headers=admin_headers)
    assert resp.status_code == 400, f"应当返回 400，实际：{resp.status_code} {resp.text}"

    # welcome 字段未被污染
    cfg_after = await _get(client, admin_headers)
    assert cfg_after["welcome"]["main_title"] == welcome_baseline
