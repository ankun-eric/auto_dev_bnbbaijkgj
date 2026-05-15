"""[PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查功能单元测试。

测试覆盖：
- 部位字典 CRUD
- 问卷模板 CRUD
- 用户端 /api/health-self-check/dict 与 /api/health-self-check/template/{id}
- 健康自查 start 端点（mock AI 输出）
- 按钮类型 health_self_check 创建/绑定模板
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
def mock_ai_model(monkeypatch):
    """Mock AI 模型返回固定内容。"""

    async def _fake(messages, system_prompt="", db=None, return_usage=False):
        return "测试 AI 回答：建议多喝水多休息。\n本回答仅供健康参考，不构成诊疗依据，如不适请及时就医。"

    monkeypatch.setattr("app.api.health_self_check.call_ai_model", _fake)
    return _fake


@pytest.mark.asyncio
async def test_admin_create_body_part(client: AsyncClient, admin_headers):
    resp = await client.post("/api/admin/body-part-dict", json={
        "name": "测试头部",
        "icon": "🧠",
        "symptoms": ["头痛", "头晕"],
        "sort_order": 10,
        "enabled": True,
    }, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "测试头部"
    assert data["symptoms"] == ["头痛", "头晕"]
    assert data["symptom_count"] == 2


@pytest.mark.asyncio
async def test_admin_body_part_unique_name(client: AsyncClient, admin_headers):
    payload = {"name": "胸部测试", "icon": "🫁", "symptoms": ["胸闷"]}
    r1 = await client.post("/api/admin/body-part-dict", json=payload, headers=admin_headers)
    assert r1.status_code == 200
    r2 = await client.post("/api/admin/body-part-dict", json=payload, headers=admin_headers)
    assert r2.status_code == 400
    assert "已存在" in r2.text


@pytest.mark.asyncio
async def test_admin_body_part_list_and_update(client: AsyncClient, admin_headers):
    r = await client.post("/api/admin/body-part-dict", json={
        "name": "腹部测试", "icon": "🤰", "symptoms": ["腹痛"],
    }, headers=admin_headers)
    pid = r.json()["id"]
    # 列表
    list_resp = await client.get("/api/admin/body-part-dict", headers=admin_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(b["id"] == pid for b in items)
    # 更新
    upd = await client.put(f"/api/admin/body-part-dict/{pid}", json={
        "symptoms": ["腹痛", "腹胀"],
        "enabled": False,
    }, headers=admin_headers)
    assert upd.status_code == 200
    body = upd.json()
    assert body["symptoms"] == ["腹痛", "腹胀"]
    assert body["enabled"] is False


@pytest.mark.asyncio
async def test_admin_create_template(client: AsyncClient, admin_headers):
    # 先创建 2 个部位
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": "tpl-头", "icon": "🧠", "symptoms": ["头痛"],
    }, headers=admin_headers)).json()
    p2 = (await client.post("/api/admin/body-part-dict", json={
        "name": "tpl-胸", "icon": "🫁", "symptoms": ["胸闷"],
    }, headers=admin_headers)).json()
    resp = await client.post("/api/admin/health-check-templates", json={
        "name": "测试模板",
        "description": "单元测试用",
        "body_parts": [{"id": p1["id"], "sort": 1}, {"id": p2["id"], "sort": 2}],
        "duration_options": ["<1天", "1-3天", ">1周"],
        "default_prompt": "{档案信息} {部位} {症状列表} {持续时间}",
        "enabled": True,
    }, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "测试模板"
    assert len(body["body_parts"]) == 2


@pytest.mark.asyncio
async def test_admin_template_validation(client: AsyncClient, admin_headers):
    # 部位列表为空
    r = await client.post("/api/admin/health-check-templates", json={
        "name": "no parts", "body_parts": [], "duration_options": ["a", "b"],
        "default_prompt": "x",
    }, headers=admin_headers)
    assert r.status_code == 400
    # 持续时间不足
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": "x部", "icon": "🧠", "symptoms": ["s"],
    }, headers=admin_headers)).json()
    r2 = await client.post("/api/admin/health-check-templates", json={
        "name": "short dur", "body_parts": [{"id": p1["id"], "sort": 1}],
        "duration_options": ["x"], "default_prompt": "x",
    }, headers=admin_headers)
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_public_dict_endpoint(client: AsyncClient, admin_headers):
    await client.post("/api/admin/body-part-dict", json={
        "name": "pub头", "icon": "🧠", "symptoms": ["头痛"], "sort_order": 5,
    }, headers=admin_headers)
    await client.post("/api/admin/body-part-dict", json={
        "name": "pub胸-禁用", "icon": "🫁", "symptoms": ["胸闷"], "enabled": False,
    }, headers=admin_headers)
    r = await client.get("/api/health-self-check/dict")
    assert r.status_code == 200
    items = r.json()
    names = [it["name"] for it in items]
    assert "pub头" in names
    assert "pub胸-禁用" not in names


@pytest.mark.asyncio
async def test_public_template_detail(client: AsyncClient, admin_headers):
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": "td头", "icon": "🧠", "symptoms": ["头痛"],
    }, headers=admin_headers)).json()
    tpl = (await client.post("/api/admin/health-check-templates", json={
        "name": "td模板", "body_parts": [{"id": p1["id"], "sort": 1}],
        "duration_options": ["a", "b"],
        "default_prompt": "x",
    }, headers=admin_headers)).json()
    r = await client.get(f"/api/health-self-check/template/{tpl['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "td模板"
    assert len(body["body_parts_detail"]) == 1
    assert body["body_parts_detail"][0]["name"] == "td头"


@pytest.mark.asyncio
async def test_button_health_self_check_create(client: AsyncClient, admin_headers):
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": "btn头", "icon": "🧠", "symptoms": ["头痛"],
    }, headers=admin_headers)).json()
    tpl = (await client.post("/api/admin/health-check-templates", json={
        "name": "btn模板", "body_parts": [{"id": p1["id"], "sort": 1}],
        "duration_options": ["a", "b"], "default_prompt": "x",
    }, headers=admin_headers)).json()
    r = await client.post("/api/admin/function-buttons", json={
        "name": "测试自查按钮",
        "button_type": "health_self_check",
        "sort_weight": 100,
        "is_enabled": True,
        "icon": "🩺",
        "health_check_template_id": tpl["id"],
        "archive_missing_strategy": "use_default",
        "prompt_override_enabled": False,
    }, headers=admin_headers)
    assert r.status_code == 200, r.text
    btn = r.json()
    assert btn["button_type"] == "health_self_check"
    assert btn["health_check_template_id"] == tpl["id"]


@pytest.mark.asyncio
async def test_health_self_check_start(client: AsyncClient, admin_headers, auth_headers, mock_ai_model):
    # 准备：部位 + 模板 + 按钮
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": "start头", "icon": "🧠", "symptoms": ["头痛", "头晕"],
    }, headers=admin_headers)).json()
    tpl = (await client.post("/api/admin/health-check-templates", json={
        "name": "start模板", "body_parts": [{"id": p1["id"], "sort": 1}],
        "duration_options": ["<1天", "1-3天", "3-7天"],
        "default_prompt": "档案={档案信息} 部位={部位} 症状={症状列表} 时长={持续时间}",
    }, headers=admin_headers)).json()
    btn = (await client.post("/api/admin/function-buttons", json={
        "name": "start按钮", "button_type": "health_self_check",
        "sort_weight": 0, "is_enabled": True, "icon": "🩺",
        "health_check_template_id": tpl["id"],
        "archive_missing_strategy": "use_default",
    }, headers=admin_headers)).json()
    # 用户调用 start
    r = await client.post("/api/health-self-check/start", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "archive_id": None,
        "body_part_id": p1["id"],
        "symptoms": ["头痛"],
        "duration": "1-3天",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ai_message_id"] > 0
    assert "测试 AI 回答" in body["ai_content"]
    assert body["card_payload"]["body_part"]["name"] == "start头"
    assert body["card_payload"]["symptoms"] == ["头痛"]


@pytest.mark.asyncio
async def test_health_self_check_start_invalid_duration(client: AsyncClient, admin_headers, auth_headers, mock_ai_model):
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": "v头", "icon": "🧠", "symptoms": ["头痛"],
    }, headers=admin_headers)).json()
    tpl = (await client.post("/api/admin/health-check-templates", json={
        "name": "v模板", "body_parts": [{"id": p1["id"], "sort": 1}],
        "duration_options": ["a", "b"], "default_prompt": "x",
    }, headers=admin_headers)).json()
    btn = (await client.post("/api/admin/function-buttons", json={
        "name": "v按钮", "button_type": "health_self_check",
        "sort_weight": 0, "is_enabled": True, "icon": "🩺",
        "health_check_template_id": tpl["id"],
    }, headers=admin_headers)).json()
    r = await client.post("/api/health-self-check/start", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "body_part_id": p1["id"],
        "symptoms": ["头痛"],
        "duration": "不存在的档位",
    }, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_template_blocked_when_referenced(client: AsyncClient, admin_headers):
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": "del头", "icon": "🧠", "symptoms": ["头痛"],
    }, headers=admin_headers)).json()
    tpl = (await client.post("/api/admin/health-check-templates", json={
        "name": "del模板", "body_parts": [{"id": p1["id"], "sort": 1}],
        "duration_options": ["a", "b"], "default_prompt": "x",
    }, headers=admin_headers)).json()
    btn = (await client.post("/api/admin/function-buttons", json={
        "name": "del按钮", "button_type": "health_self_check",
        "sort_weight": 0, "is_enabled": True, "icon": "🩺",
        "health_check_template_id": tpl["id"],
    }, headers=admin_headers)).json()
    # 删除模板应当被拒
    r = await client.delete(f"/api/admin/health-check-templates/{tpl['id']}", headers=admin_headers)
    assert r.status_code == 400
    # 解除按钮引用后即可删
    await client.put(f"/api/admin/function-buttons/{btn['id']}", json={
        "health_check_template_id": None,
    }, headers=admin_headers)
    r2 = await client.delete(f"/api/admin/health-check-templates/{tpl['id']}", headers=admin_headers)
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_delete_body_part_blocked_when_referenced(client: AsyncClient, admin_headers):
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": "ref头", "icon": "🧠", "symptoms": ["头痛"],
    }, headers=admin_headers)).json()
    await client.post("/api/admin/health-check-templates", json={
        "name": "ref模板", "body_parts": [{"id": p1["id"], "sort": 1}],
        "duration_options": ["a", "b"], "default_prompt": "x",
    }, headers=admin_headers)
    r = await client.delete(f"/api/admin/body-part-dict/{p1['id']}", headers=admin_headers)
    assert r.status_code == 400
    assert "引用" in r.text
