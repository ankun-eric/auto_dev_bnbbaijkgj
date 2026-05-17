"""[PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] AI 咨询配置-功能按钮管理 优化 非UI 自动化测试

覆盖：
  N1. ChatFunctionButton 模型新字段持久化（grid_sort/capsule_sort/ai_function_type/ai_opening/pre_card_for_navigate）
  N2. /api/admin/function-buttons 列表接口支持 view_type=grid / capsule 切换
  N3. POST /api/admin/function-buttons/sort-action 置顶/上移/下移 在 grid 视图正确工作
  N4. POST /api/admin/function-buttons/sort-action 在 capsule 视图独立工作（与 grid 互不影响）
  N5. button_type=ai_function 缺失 ai_function_type 时报 400
  N6. button_type=ai_function ai_function_type 取值不合法时报 400
  N7. button_type=page_navigate external_url 非法（既不是 http(s) 也不是 / 开头）时报 400
  N8. button_type=page_navigate 默认 pre_card_for_navigate=False
  N9. 公开接口 /api/function-buttons?position=grid 按 grid_sort 升序
  N10. 公开接口 /api/function-buttons?position=capsule 按 capsule_sort 升序
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import ChatFunctionButton


def _btn_payload(name: str, **overrides):
    base = {
        "name": name,
        "icon": "📌",
        "button_type": "ai_function",
        "ai_function_type": "ai_dialog_trigger",
        "sort_weight": 0,
        "is_enabled": True,
        "is_recommended": True,
        "is_capsule": True,
        "auto_user_message": "你好",
        "card_title": name,
    }
    base.update(overrides)
    return base


# ─────────────────── N1 ───────────────────
@pytest.mark.asyncio
async def test_funcbtn_optim_model_new_fields(db_session):
    b = ChatFunctionButton(
        name="N1 按钮",
        button_type="ai_function",
        ai_function_type="medicine_recognize",
        sort_weight=0,
        grid_sort=3,
        capsule_sort=7,
        ai_opening="你好，准备开始",
        pre_card_for_navigate=False,
        is_enabled=True,
        is_recommended=True,
        is_capsule=True,
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    assert b.grid_sort == 3
    assert b.capsule_sort == 7
    assert b.ai_function_type == "medicine_recognize"
    assert b.ai_opening == "你好，准备开始"
    assert b.pre_card_for_navigate is False


# ─────────────────── N2 ───────────────────
@pytest.mark.asyncio
async def test_admin_list_supports_view_type(client: AsyncClient, admin_headers):
    p1 = _btn_payload("仅胶囊", is_recommended=False, is_capsule=True)
    p2 = _btn_payload("仅宫格", is_recommended=True, is_capsule=False)
    p3 = _btn_payload("两端都开", is_recommended=True, is_capsule=True)
    for p in (p1, p2, p3):
        r = await client.post("/api/admin/function-buttons", json=p, headers=admin_headers)
        assert r.status_code == 200, r.text

    r_grid = await client.get(
        "/api/admin/function-buttons",
        params={"view_type": "grid", "page_size": 100},
        headers=admin_headers,
    )
    assert r_grid.status_code == 200, r_grid.text
    grid_names = [it["name"] for it in r_grid.json()["items"]]
    assert "仅宫格" in grid_names
    assert "两端都开" in grid_names
    assert "仅胶囊" not in grid_names

    r_caps = await client.get(
        "/api/admin/function-buttons",
        params={"view_type": "capsule", "page_size": 100},
        headers=admin_headers,
    )
    assert r_caps.status_code == 200, r_caps.text
    caps_names = [it["name"] for it in r_caps.json()["items"]]
    assert "仅胶囊" in caps_names
    assert "两端都开" in caps_names
    assert "仅宫格" not in caps_names


# ─────────────────── N3 ───────────────────
@pytest.mark.asyncio
async def test_sort_action_in_grid_view(client: AsyncClient, admin_headers):
    ids = []
    for n in ("G-A", "G-B", "G-C"):
        r = await client.post("/api/admin/function-buttons", json=_btn_payload(n, is_capsule=False), headers=admin_headers)
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])

    # 把第三个置顶
    r2 = await client.post(
        "/api/admin/function-buttons/sort-action",
        json={"id": ids[2], "view_type": "grid", "action": "top"},
        headers=admin_headers,
    )
    assert r2.status_code == 200, r2.text
    ordered = r2.json()["ordered_ids"]
    pos = {bid: idx for idx, bid in enumerate(ordered)}
    assert pos[ids[2]] < pos[ids[0]] and pos[ids[2]] < pos[ids[1]]

    # 上移到顶后再次上移应报错（已经第一）
    r3 = await client.post(
        "/api/admin/function-buttons/sort-action",
        json={"id": ids[2], "view_type": "grid", "action": "up"},
        headers=admin_headers,
    )
    assert r3.status_code == 400, r3.text


# ─────────────────── N4 ───────────────────
@pytest.mark.asyncio
async def test_sort_action_capsule_view_independent(client: AsyncClient, admin_headers):
    ids = []
    for n in ("C-A", "C-B"):
        r = await client.post("/api/admin/function-buttons", json=_btn_payload(n, is_recommended=False), headers=admin_headers)
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    r = await client.post(
        "/api/admin/function-buttons/sort-action",
        json={"id": ids[1], "view_type": "capsule", "action": "top"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    ordered = r.json()["ordered_ids"]
    pos = {bid: idx for idx, bid in enumerate(ordered)}
    assert pos[ids[1]] < pos[ids[0]]


# ─────────────────── N5 ───────────────────
@pytest.mark.asyncio
async def test_ai_function_requires_subtype(client: AsyncClient, admin_headers):
    p = _btn_payload("缺子类型", ai_function_type=None)
    r = await client.post("/api/admin/function-buttons", json=p, headers=admin_headers)
    assert r.status_code == 400, r.text


# ─────────────────── N6 ───────────────────
@pytest.mark.asyncio
async def test_ai_function_subtype_invalid(client: AsyncClient, admin_headers):
    p = _btn_payload("非法子类型", ai_function_type="not_exist_xxx")
    r = await client.post("/api/admin/function-buttons", json=p, headers=admin_headers)
    assert r.status_code == 400, r.text


# ─────────────────── N7 ───────────────────
@pytest.mark.asyncio
async def test_page_navigate_url_invalid(client: AsyncClient, admin_headers):
    p = _btn_payload(
        "非法跳转地址",
        button_type="page_navigate",
        ai_function_type=None,
        external_url="ftp://invalid.example",
    )
    r = await client.post("/api/admin/function-buttons", json=p, headers=admin_headers)
    assert r.status_code == 400, r.text


# ─────────────────── N8 ───────────────────
@pytest.mark.asyncio
async def test_page_navigate_default_pre_card_off(client: AsyncClient, admin_headers):
    p = _btn_payload(
        "page_navigate 默认",
        button_type="page_navigate",
        ai_function_type=None,
        external_url="https://example.com",
    )
    r = await client.post("/api/admin/function-buttons", json=p, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("pre_card_for_navigate") in (False, None)


# ─────────────────── N9 / N10 ───────────────────
@pytest.mark.asyncio
async def test_public_function_buttons_grid_capsule_sort(client: AsyncClient, admin_headers):
    payloads = [
        _btn_payload("S1", grid_sort=3, capsule_sort=1),
        _btn_payload("S2", grid_sort=1, capsule_sort=3),
        _btn_payload("S3", grid_sort=2, capsule_sort=2),
    ]
    for p in payloads:
        r = await client.post("/api/admin/function-buttons", json=p, headers=admin_headers)
        assert r.status_code == 200, r.text

    # grid 升序：S2(1) < S3(2) < S1(3)
    r_grid = await client.get("/api/function-buttons", params={"position": "grid"})
    assert r_grid.status_code == 200, r_grid.text
    names_grid = [it["name"] for it in r_grid.json() if it["name"] in {"S1", "S2", "S3"}]
    assert names_grid == ["S2", "S3", "S1"], names_grid

    # capsule 升序：S1(1) < S3(2) < S2(3)
    r_caps = await client.get("/api/function-buttons", params={"position": "capsule"})
    assert r_caps.status_code == 200, r_caps.text
    names_caps = [it["name"] for it in r_caps.json() if it["name"] in {"S1", "S2", "S3"}]
    assert names_caps == ["S1", "S3", "S2"], names_caps
