"""[PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] AI 对话识药结果加入/查看用药计划

测试用例覆盖：
1. 批量检查接口——本人态命中（家庭成员=None）
2. 批量检查接口——未命中
3. 批量检查接口——咨询人态（family_member_id 隔离）
4. 批量检查接口——通用名(generic_name) 命中宽松匹配
5. 批量检查接口——已过期/long_term=False 用药计划不算「已加入」
6. 批量检查接口——空药名参数返回空 data
7. 创建用药计划：family_member_id + generic_name 字段持久化
8. 列表接口按 consultant_id 过滤本人 vs 家庭成员
9. 列表接口返回 family_member_id + generic_name 字段
10. 接口需鉴权（无 token 返回 401）
"""
from __future__ import annotations

from datetime import date, timedelta

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
async def test_check_batch_self_hit(client: AsyncClient, auth_headers):
    """1. 本人态：medicine_name 命中。"""
    r = await client.post("/api/health-plan/medications", json=_payload("阿莫西林胶囊"), headers=auth_headers)
    assert r.status_code == 200, r.text

    r2 = await client.get(
        "/api/health-plan/medications/check-batch?drug_names=阿莫西林,布洛芬",
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()["data"]
    assert data["阿莫西林"] is True
    assert data["布洛芬"] is False


@pytest.mark.asyncio
async def test_check_batch_miss(client: AsyncClient, auth_headers):
    """2. 全部未命中（无任何用药计划）。"""
    r = await client.get(
        "/api/health-plan/medications/check-batch?drug_names=阿莫西林,布洛芬",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["data"] == {"阿莫西林": False, "布洛芬": False}


@pytest.mark.asyncio
async def test_check_batch_consultant_isolation(client: AsyncClient, auth_headers):
    """3. 咨询人态：本人药品不应被命中为咨询人的「已加入」。"""
    # 本人加入「阿莫西林」
    r = await client.post("/api/health-plan/medications", json=_payload("阿莫西林"), headers=auth_headers)
    assert r.status_code == 200

    # 假定 family_member_id=99（不存在也没关系，按字段过滤）
    r2 = await client.get(
        "/api/health-plan/medications/check-batch?drug_names=阿莫西林&consultant_id=99",
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["阿莫西林"] is False

    # 显式 0 = 本人
    r3 = await client.get(
        "/api/health-plan/medications/check-batch?drug_names=阿莫西林&consultant_id=0",
        headers=auth_headers,
    )
    assert r3.status_code == 200
    assert r3.json()["data"]["阿莫西林"] is True


@pytest.mark.asyncio
async def test_check_batch_generic_name_match(client: AsyncClient, auth_headers):
    """4. generic_name 宽松匹配命中。"""
    body = _payload("泰诺", generic_name="对乙酰氨基酚")
    r = await client.post("/api/health-plan/medications", json=body, headers=auth_headers)
    assert r.status_code == 200
    assert r.json().get("generic_name") == "对乙酰氨基酚"

    r2 = await client.get(
        "/api/health-plan/medications/check-batch?drug_names=对乙酰氨基酚",
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["对乙酰氨基酚"] is True


@pytest.mark.asyncio
async def test_check_batch_expired_not_counted(client: AsyncClient, auth_headers):
    """5. 已过期（end_date < today 且非 long_term）的用药计划不应计入「已加入」。"""
    yesterday = (date.today() - timedelta(days=5)).isoformat()
    end = (date.today() - timedelta(days=1)).isoformat()
    body = _payload("头孢克肟", long_term=False, start_date=yesterday, end_date=end, duration_days=4)
    r = await client.post("/api/health-plan/medications", json=body, headers=auth_headers)
    assert r.status_code == 200

    r2 = await client.get(
        "/api/health-plan/medications/check-batch?drug_names=头孢克肟",
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["头孢克肟"] is False


@pytest.mark.asyncio
async def test_check_batch_empty_input(client: AsyncClient, auth_headers):
    """6. drug_names 为空时返回空 data 不报错。"""
    r = await client.get(
        "/api/health-plan/medications/check-batch?drug_names=",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["data"] == {}


@pytest.mark.asyncio
async def test_create_persists_family_and_generic(client: AsyncClient, auth_headers):
    """7. 创建用药计划：family_member_id + generic_name 字段被正确持久化与回显。"""
    body = _payload("布洛芬缓释胶囊", family_member_id=88, generic_name="布洛芬")
    r = await client.post("/api/health-plan/medications", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["family_member_id"] == 88
    assert j["generic_name"] == "布洛芬"


@pytest.mark.asyncio
async def test_list_filter_by_consultant(client: AsyncClient, auth_headers):
    """8. 列表接口按 consultant_id 过滤；本人(0) 与家庭成员(123) 互不可见。"""
    # 本人 1 条
    await client.post("/api/health-plan/medications", json=_payload("药A"), headers=auth_headers)
    # 家庭成员 1 条
    await client.post(
        "/api/health-plan/medications",
        json=_payload("药B", family_member_id=123),
        headers=auth_headers,
    )

    r_self = await client.get(
        "/api/health-plan/medications/list?tab=in_progress&consultant_id=0",
        headers=auth_headers,
    )
    assert r_self.status_code == 200
    names_self = {x["medicine_name"] for x in r_self.json()["items"]}
    assert "药A" in names_self
    assert "药B" not in names_self

    r_fm = await client.get(
        "/api/health-plan/medications/list?tab=in_progress&consultant_id=123",
        headers=auth_headers,
    )
    assert r_fm.status_code == 200
    names_fm = {x["medicine_name"] for x in r_fm.json()["items"]}
    assert "药B" in names_fm
    assert "药A" not in names_fm


@pytest.mark.asyncio
async def test_list_returns_new_fields(client: AsyncClient, auth_headers):
    """9. 列表接口返回 family_member_id + generic_name 字段。"""
    await client.post(
        "/api/health-plan/medications",
        json=_payload("阿莫西林克拉维酸钾", generic_name="阿莫西林", family_member_id=5),
        headers=auth_headers,
    )
    r = await client.get(
        "/api/health-plan/medications/list?tab=in_progress&consultant_id=5",
        headers=auth_headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(
        it["family_member_id"] == 5 and it["generic_name"] == "阿莫西林"
        for it in items
    )


@pytest.mark.asyncio
async def test_check_batch_requires_auth(client: AsyncClient):
    """10. 接口需鉴权。"""
    r = await client.get("/api/health-plan/medications/check-batch?drug_names=阿莫西林")
    assert r.status_code in (401, 403)
