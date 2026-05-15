"""[PRD-AICHAT-HOME-GRID-V1 2026-05-16] AI 对话首页功能宫格与胶囊条优化 非UI 自动化测试

覆盖：
  N1. ChatFunctionButton 模型可正常持久化 is_recommended / is_capsule 两个新字段
  N2. /api/admin/function-buttons 创建按钮时未显式指定两开关，默认两者都为 False
  N3. /api/admin/function-buttons 创建时可单独指定 is_recommended=True / is_capsule=True
  N4. /api/admin/function-buttons/{id}/toggle-recommended PATCH 接口能切换 is_recommended
  N5. /api/admin/function-buttons/{id}/toggle-capsule PATCH 接口能切换 is_capsule
  N6. 公开接口 /api/function-buttons?position=grid 仅返回 is_recommended=true 的按钮
  N7. 公开接口 /api/function-buttons?position=capsule 仅返回 is_capsule=true 的按钮
  N8. 公开接口 /api/function-buttons（不传 position）返回 is_recommended OR is_capsule 为 true 的按钮
  N9. 两个开关都为 False 的按钮，在任何 position 下都不会出现在公开返回中
  N10. ChatFunctionButtonResponse Schema 含 is_recommended / is_capsule 两个字段
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import ChatFunctionButton


# ─────────────────── N1 ───────────────────
@pytest.mark.asyncio
async def test_chat_function_button_model_has_two_switches(db_session):
    """ChatFunctionButton 可持久化 is_recommended / is_capsule 字段。"""
    b = ChatFunctionButton(
        name="自查按钮",
        button_type="health_self_check",
        sort_weight=0,
        is_enabled=True,
        is_recommended=True,
        is_capsule=False,
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    assert b.is_recommended is True
    assert b.is_capsule is False

    # 读出来再校验一次
    res = await db_session.execute(select(ChatFunctionButton).where(ChatFunctionButton.id == b.id))
    fetched = res.scalar_one()
    assert fetched.is_recommended is True
    assert fetched.is_capsule is False


# ─────────────────── N2 ───────────────────
@pytest.mark.asyncio
async def test_admin_create_button_defaults_two_switches_off(admin_client: AsyncClient):
    """新建按钮未指定两开关时，两者默认都是 False（强制管理员显式选择）。"""
    payload = {
        "name": "默认开关按钮",
        "icon": "📌",
        "button_type": "quick_ask",
        "sort_weight": 5,
        "is_enabled": True,
        "preset_prompt": "你好",
        "auto_user_message": "你好",
        "card_title": "你好",
    }
    r = await admin_client.post("/api/admin/function-buttons", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_recommended"] is False
    assert body["is_capsule"] is False


# ─────────────────── N3 ───────────────────
@pytest.mark.asyncio
async def test_admin_create_button_can_set_two_switches(admin_client: AsyncClient):
    """新建按钮时可独立指定 is_recommended / is_capsule。"""
    payload = {
        "name": "推荐按钮",
        "icon": "🔥",
        "button_type": "quick_ask",
        "sort_weight": 1,
        "is_enabled": True,
        "is_recommended": True,
        "is_capsule": False,
        "preset_prompt": "p",
        "auto_user_message": "p",
        "card_title": "p",
    }
    r = await admin_client.post("/api/admin/function-buttons", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_recommended"] is True
    assert body["is_capsule"] is False


# ─────────────────── N4 ───────────────────
@pytest.mark.asyncio
async def test_toggle_recommended_endpoint(admin_client: AsyncClient, db_session):
    """PATCH /toggle-recommended 切换 is_recommended。"""
    b = ChatFunctionButton(
        name="切推荐",
        button_type="quick_ask",
        sort_weight=0,
        is_enabled=True,
        is_recommended=False,
        is_capsule=False,
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)

    r = await admin_client.patch(
        f"/api/admin/function-buttons/{b.id}/toggle-recommended",
        json={"value": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_recommended"] is True

    r2 = await admin_client.patch(
        f"/api/admin/function-buttons/{b.id}/toggle-recommended",
        json={"value": False},
    )
    assert r2.status_code == 200
    assert r2.json()["is_recommended"] is False


# ─────────────────── N5 ───────────────────
@pytest.mark.asyncio
async def test_toggle_capsule_endpoint(admin_client: AsyncClient, db_session):
    """PATCH /toggle-capsule 切换 is_capsule。"""
    b = ChatFunctionButton(
        name="切胶囊",
        button_type="quick_ask",
        sort_weight=0,
        is_enabled=True,
        is_recommended=False,
        is_capsule=False,
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)

    r = await admin_client.patch(
        f"/api/admin/function-buttons/{b.id}/toggle-capsule",
        json={"value": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_capsule"] is True


# ─────────────────── N6 ───────────────────
@pytest.mark.asyncio
async def test_public_buttons_position_grid(client: AsyncClient, db_session):
    """position=grid 仅返回 is_recommended=true 的按钮。"""
    rec_btn = ChatFunctionButton(
        name="仅推荐",
        button_type="quick_ask",
        sort_weight=0,
        is_enabled=True,
        is_recommended=True,
        is_capsule=False,
    )
    cap_btn = ChatFunctionButton(
        name="仅胶囊",
        button_type="quick_ask",
        sort_weight=1,
        is_enabled=True,
        is_recommended=False,
        is_capsule=True,
    )
    both_btn = ChatFunctionButton(
        name="都开",
        button_type="quick_ask",
        sort_weight=2,
        is_enabled=True,
        is_recommended=True,
        is_capsule=True,
    )
    db_session.add_all([rec_btn, cap_btn, both_btn])
    await db_session.commit()

    r = await client.get("/api/function-buttons?position=grid")
    assert r.status_code == 200
    names = [b["name"] for b in r.json()]
    assert "仅推荐" in names
    assert "都开" in names
    assert "仅胶囊" not in names


# ─────────────────── N7 ───────────────────
@pytest.mark.asyncio
async def test_public_buttons_position_capsule(client: AsyncClient, db_session):
    """position=capsule 仅返回 is_capsule=true 的按钮。"""
    rec = ChatFunctionButton(
        name="A_推", button_type="quick_ask",
        is_enabled=True, is_recommended=True, is_capsule=False,
    )
    cap = ChatFunctionButton(
        name="B_胶", button_type="quick_ask",
        is_enabled=True, is_recommended=False, is_capsule=True,
    )
    db_session.add_all([rec, cap])
    await db_session.commit()

    r = await client.get("/api/function-buttons?position=capsule")
    assert r.status_code == 200
    names = [b["name"] for b in r.json()]
    assert "B_胶" in names
    assert "A_推" not in names


# ─────────────────── N8 ───────────────────
@pytest.mark.asyncio
async def test_public_buttons_no_position_returns_union(client: AsyncClient, db_session):
    """不传 position 时返回 is_recommended OR is_capsule 为 true 的全部按钮。"""
    a = ChatFunctionButton(
        name="U_仅推", button_type="quick_ask",
        is_enabled=True, is_recommended=True, is_capsule=False,
    )
    b = ChatFunctionButton(
        name="U_仅胶", button_type="quick_ask",
        is_enabled=True, is_recommended=False, is_capsule=True,
    )
    c = ChatFunctionButton(
        name="U_都关", button_type="quick_ask",
        is_enabled=True, is_recommended=False, is_capsule=False,
    )
    db_session.add_all([a, b, c])
    await db_session.commit()

    r = await client.get("/api/function-buttons")
    assert r.status_code == 200
    names = [x["name"] for x in r.json()]
    assert "U_仅推" in names
    assert "U_仅胶" in names
    assert "U_都关" not in names


# ─────────────────── N9 ───────────────────
@pytest.mark.asyncio
async def test_public_buttons_excludes_all_off(client: AsyncClient, db_session):
    """两个开关都为 False 的按钮，任何 position 下都不返回。"""
    off = ChatFunctionButton(
        name="EXCL_OFF", button_type="quick_ask",
        is_enabled=True, is_recommended=False, is_capsule=False,
    )
    db_session.add(off)
    await db_session.commit()

    for url in ["/api/function-buttons", "/api/function-buttons?position=grid", "/api/function-buttons?position=capsule"]:
        r = await client.get(url)
        assert r.status_code == 200
        names = [b["name"] for b in r.json()]
        assert "EXCL_OFF" not in names, f"按钮在 {url} 中出现了，但两个开关都关闭"


# ─────────────────── N10 ───────────────────
@pytest.mark.asyncio
async def test_response_schema_contains_two_switch_fields(admin_client: AsyncClient, db_session):
    """ChatFunctionButtonResponse 中含 is_recommended / is_capsule 字段。"""
    b = ChatFunctionButton(
        name="SCHEMA_CHECK",
        button_type="quick_ask",
        is_enabled=True,
        is_recommended=True,
        is_capsule=True,
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)

    r = await admin_client.get("/api/admin/function-buttons?page=1&page_size=100")
    assert r.status_code == 200
    items = r.json().get("items", [])
    found = next((it for it in items if it["id"] == b.id), None)
    assert found is not None
    assert "is_recommended" in found
    assert "is_capsule" in found
    assert found["is_recommended"] is True
    assert found["is_capsule"] is True
