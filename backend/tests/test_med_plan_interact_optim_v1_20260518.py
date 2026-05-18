"""[PRD-MED-PLAN-INTERACT-OPTIM-V1 2026-05-18] 用药计划交互优化 后端验收测试

覆盖用例：
1. check-duplicate（健康计划路径）— 本人维度未命中
2. check-duplicate — 本人维度命中并返回 plan_id
3. check-duplicate — 大小写 / 前后空白宽容匹配
4. check-duplicate — 家庭成员维度隔离（本人态命中，家庭成员态不命中）
5. check-duplicate（/api/medication-plan 别名路径）— 与原路径行为一致
6. 备注 notes 超过 200 字 → 422 校验失败
7. 备注 notes 200 字以内可正常保存
8. POST /medications 创建时同名 + 同服用人 → 409 重复
9. POST /medications 同药品名 + 不同服用人 → 不重复（允许两条）
10. PUT /medications 编辑保存：原记录 UPDATE，记录 id 不变
"""
from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient


def _payload(name: str, **overrides) -> dict:
    body = {
        "medicine_name": name,
        "dosage": "1 片",
        "dosage_value": "1",
        "dosage_unit": "片",
        "remind_time": "08:00",
        "frequency_per_day": 1,
        "custom_times": ["08:00"],
        "long_term": True,
        "start_date": date.today().isoformat(),
        "duration_days": None,
        "guidance": "饭后",
        "reminder_enabled": True,
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_check_duplicate_self_miss(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/health-plan/medications/check-duplicate",
        json={"drug_name": "完全不存在的药品名"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["exists"] is False
    assert data["plan_id"] is None


@pytest.mark.asyncio
async def test_check_duplicate_self_hit(client: AsyncClient, auth_headers):
    cr = await client.post(
        "/api/health-plan/medications", json=_payload("阿莫西林胶囊"), headers=auth_headers
    )
    assert cr.status_code == 200, cr.text
    plan_id = cr.json()["id"]

    r = await client.post(
        "/api/health-plan/medications/check-duplicate",
        json={"drug_name": "阿莫西林胶囊"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["exists"] is True
    assert data["plan_id"] == plan_id
    assert data["existing_name"] == "阿莫西林胶囊"


@pytest.mark.asyncio
async def test_check_duplicate_case_and_trim(client: AsyncClient, auth_headers):
    cr = await client.post(
        "/api/health-plan/medications",
        json=_payload("Vitamin C"),
        headers=auth_headers,
    )
    assert cr.status_code == 200

    r = await client.post(
        "/api/health-plan/medications/check-duplicate",
        json={"drug_name": "  vitamin c  "},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["data"]["exists"] is True


@pytest.mark.asyncio
async def test_check_duplicate_consultant_isolation(client: AsyncClient, auth_headers):
    """药品名相同但服用人不同 → 不算重复。"""
    cr = await client.post(
        "/api/health-plan/medications",
        json=_payload("孟鲁司特"),
        headers=auth_headers,
    )
    assert cr.status_code == 200

    # 假定服用人 family_member_id=99
    r = await client.post(
        "/api/health-plan/medications/check-duplicate",
        json={"drug_name": "孟鲁司特", "taker_id": 99},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["data"]["exists"] is False

    # 显式 0 = 本人 → 命中
    r2 = await client.post(
        "/api/health-plan/medications/check-duplicate",
        json={"drug_name": "孟鲁司特", "taker_id": 0},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["exists"] is True


@pytest.mark.asyncio
async def test_check_duplicate_alias_route(client: AsyncClient, auth_headers):
    cr = await client.post(
        "/api/health-plan/medications",
        json=_payload("布洛芬缓释胶囊"),
        headers=auth_headers,
    )
    assert cr.status_code == 200

    r = await client.post(
        "/api/medication-plan/check-duplicate",
        json={"drug_name": "布洛芬缓释胶囊"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["exists"] is True


@pytest.mark.asyncio
async def test_notes_max_length_200_reject(client: AsyncClient, auth_headers):
    long_notes = "饭后" * 101  # 202 字
    body = _payload("XYZ-201", notes=long_notes)
    r = await client.post("/api/health-plan/medications", json=body, headers=auth_headers)
    # Pydantic v2 校验失败 → 422
    assert r.status_code in (400, 422), r.text


@pytest.mark.asyncio
async def test_notes_max_length_200_accept(client: AsyncClient, auth_headers):
    body = _payload("XYZ-200", notes="备" * 200)
    r = await client.post("/api/health-plan/medications", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["medicine_name"] == "XYZ-200"
    assert data["notes"] == "备" * 200


@pytest.mark.asyncio
async def test_create_duplicate_same_taker(client: AsyncClient, auth_headers):
    body = _payload("二甲双胍片")
    r1 = await client.post("/api/health-plan/medications", json=body, headers=auth_headers)
    assert r1.status_code == 200

    r2 = await client.post("/api/health-plan/medications", json=body, headers=auth_headers)
    assert r2.status_code == 409, r2.text
    detail = r2.json()["detail"]
    assert isinstance(detail, dict)
    assert detail.get("code") == "MEDICATION_DUPLICATE_ACTIVE"
    assert detail.get("existing_id") is not None


@pytest.mark.asyncio
async def test_create_same_name_different_taker(client: AsyncClient, auth_headers):
    """同药品名 + 不同服用人 → 不重复。"""
    r1 = await client.post(
        "/api/health-plan/medications",
        json=_payload("钙片"),
        headers=auth_headers,
    )
    assert r1.status_code == 200

    r2 = await client.post(
        "/api/health-plan/medications",
        json=_payload("钙片", family_member_id=88),
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_edit_update_keeps_id(client: AsyncClient, auth_headers):
    """编辑保存：UPDATE 同一条记录，不新增。"""
    r1 = await client.post(
        "/api/health-plan/medications",
        json=_payload("辛伐他汀"),
        headers=auth_headers,
    )
    assert r1.status_code == 200
    plan_id = r1.json()["id"]

    r2 = await client.put(
        f"/api/health-plan/medications/{plan_id}",
        json={"notes": "编辑后的备注", "dosage_value": "2"},
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["id"] == plan_id
    assert r2.json()["notes"] == "编辑后的备注"
    assert r2.json()["dosage_value"] == "2"

    # 列表中仍然只有一条
    r3 = await client.get(
        "/api/health-plan/medications/list?tab=in_progress",
        headers=auth_headers,
    )
    assert r3.status_code == 200
    items = r3.json()["items"]
    same = [it for it in items if it.get("medicine_name") == "辛伐他汀"]
    assert len(same) == 1
    assert same[0]["id"] == plan_id
