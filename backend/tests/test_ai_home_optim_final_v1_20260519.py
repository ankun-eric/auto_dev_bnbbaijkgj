"""[PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] ai-home 首页优化 - 后端同源接口测试

覆盖用例：
1. /api/medication/today 返回 PRD §5.1 规范结构（hasTodayMedication / items / summary）
2. /api/medication/today 无任何计划时 hasTodayMedication=False
3. /api/medication/today 创建计划后 hasTodayMedication=True 且 items 数量正确
4. /api/medication/today 按 consultant_id 维度筛选生效
5. /api/medication/plans/exists 查询不存在的药品返回 exists=False
6. /api/medication/plans/exists 查询已加入的药品返回 exists=True 并带 planId
7. 同源接口对未登录用户返回 401
8. /api/medication/today 接受 patient_id 作为 consultant_id 的别名（向后兼容）
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


def _plan_payload(name: str = "测试药品阿司匹林", patient_id=None, **overrides) -> dict:
    body = {
        "drug_name": name,
        "dosage": "1 片",
        "schedule": ["08:00", "20:00"],
        "note": None,
        "enabled": True,
    }
    if patient_id is not None:
        body["patient_id"] = patient_id
    body.update(overrides)
    return body


# ─────────────────── /api/medication/today ───────────────────


@pytest.mark.asyncio
async def test_today_no_plans_returns_false(client: AsyncClient, auth_headers):
    """无用药计划时 hasTodayMedication=False。"""
    r = await client.get("/api/medication/today", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["hasTodayMedication"] is False
    assert data["items"] == []
    assert data["summary"]["total"] == 0
    assert data["summary"]["done"] == 0
    assert data["summary"]["remaining"] == 0


@pytest.mark.asyncio
async def test_today_with_plans_returns_true(client: AsyncClient, auth_headers):
    """加入用药计划后 hasTodayMedication=True 且 items 数量等于 schedule 数。"""
    cr = await client.post(
        "/api/medication-reminder/plans",
        json=_plan_payload("布洛芬"),
        headers=auth_headers,
    )
    assert cr.status_code == 200, cr.text

    r = await client.get("/api/medication/today", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    data = body["data"]
    assert data["hasTodayMedication"] is True
    assert len(data["items"]) == 2  # schedule 中有 2 个时间点
    # PRD 字段规范
    item = data["items"][0]
    for k in ("planId", "medName", "time", "dose", "status"):
        assert k in item, f"item missing key {k}"
    assert item["status"] in ("done", "pending")
    assert data["summary"]["total"] == 2
    assert data["summary"]["done"] == 0
    assert data["summary"]["remaining"] == 2


@pytest.mark.asyncio
async def test_today_consultant_id_filter(client: AsyncClient, auth_headers):
    """同时存在两条计划：本人 + 某咨询人；按 consultant_id 筛选只返回对应咨询人。"""
    # 本人计划
    await client.post(
        "/api/medication-reminder/plans",
        json=_plan_payload("本人药品"),
        headers=auth_headers,
    )
    # 咨询人 999 计划
    await client.post(
        "/api/medication-reminder/plans",
        json=_plan_payload("家人药品", patient_id=999),
        headers=auth_headers,
    )
    # 仅本人
    r1 = await client.get(
        "/api/medication/today?consultant_id=0",
        headers=auth_headers,
    )
    assert r1.status_code == 200
    items1 = r1.json()["data"]["items"]
    names1 = {it["medName"] for it in items1}
    assert "本人药品" in names1
    # consultant_id=999
    r2 = await client.get(
        "/api/medication/today?consultant_id=999",
        headers=auth_headers,
    )
    assert r2.status_code == 200
    items2 = r2.json()["data"]["items"]
    names2 = {it["medName"] for it in items2}
    assert names2 == {"家人药品"}, f"expected only 家人药品 but got {names2}"


@pytest.mark.asyncio
async def test_today_patient_id_backward_compat(client: AsyncClient, auth_headers):
    """patient_id 与 consultant_id 等价（向后兼容）。"""
    await client.post(
        "/api/medication-reminder/plans",
        json=_plan_payload("兼容测试药", patient_id=888),
        headers=auth_headers,
    )
    r = await client.get(
        "/api/medication/today?patient_id=888",
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["hasTodayMedication"] is True
    names = {it["medName"] for it in body["data"]["items"]}
    assert "兼容测试药" in names


@pytest.mark.asyncio
async def test_today_requires_auth(client: AsyncClient):
    """未登录调用应 401。"""
    r = await client.get("/api/medication/today")
    assert r.status_code in (401, 403), r.text


# ─────────────────── /api/medication/plans/exists ───────────────────


@pytest.mark.asyncio
async def test_plans_exists_not_found(client: AsyncClient, auth_headers):
    """未加入用药计划的药品返回 exists=False。"""
    r = await client.get(
        "/api/medication/plans/exists?medName=完全不存在的药品名XYZ",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["exists"] is False
    assert body["data"]["planId"] is None


@pytest.mark.asyncio
async def test_plans_exists_found(client: AsyncClient, auth_headers):
    """加入用药计划后再查询应 exists=True 且 planId 非空。"""
    cr = await client.post(
        "/api/medication-reminder/plans",
        json=_plan_payload("阿莫西林胶囊"),
        headers=auth_headers,
    )
    assert cr.status_code == 200, cr.text
    plan_id = cr.json()["id"]

    r = await client.get(
        "/api/medication/plans/exists?medName=阿莫西林胶囊",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["exists"] is True
    assert body["data"]["planId"] == plan_id


@pytest.mark.asyncio
async def test_plans_exists_per_consultant(client: AsyncClient, auth_headers):
    """exists 按 consultant_id 维度判定：本人加入的药品对其他咨询人应返回 False。"""
    # 本人加入
    await client.post(
        "/api/medication-reminder/plans",
        json=_plan_payload("VC片"),
        headers=auth_headers,
    )
    # 本人维度 → exists=True
    r1 = await client.get(
        "/api/medication/plans/exists?medName=VC片&consultant_id=0",
        headers=auth_headers,
    )
    assert r1.json()["data"]["exists"] is True
    # 咨询人 999 维度 → exists=False
    r2 = await client.get(
        "/api/medication/plans/exists?medName=VC片&consultant_id=999",
        headers=auth_headers,
    )
    assert r2.json()["data"]["exists"] is False


# ─────────────────── 内部一致性：与 /api/medication-reminder/today 同源 ───────────────────


@pytest.mark.asyncio
async def test_today_same_source_as_reminder(client: AsyncClient, auth_headers):
    """/api/medication/today 与 /api/medication-reminder/today 应基于同一数据源。

    PRD §5.1 要求"此接口同时供 ai-home / 健康档案 Hero / 抽屉渲染"，
    即两个接口对同一份数据返回应一致（条目数相同）。
    """
    await client.post(
        "/api/medication-reminder/plans",
        json=_plan_payload("同源测试药"),
        headers=auth_headers,
    )

    r1 = await client.get("/api/medication/today", headers=auth_headers)
    r2 = await client.get("/api/medication-reminder/today", headers=auth_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200

    items_new = r1.json()["data"]["items"]
    items_old = r2.json()
    if isinstance(items_old, dict):
        items_old = items_old.get("data", items_old)

    assert len(items_new) == len(items_old), (
        f"new={len(items_new)} old={len(items_old)} 不同源"
    )


def test_router_imports():
    """API module 可被 import；router 注册到 app 上。"""
    from app.api import medication_today_v1
    from app.main import app

    routes = [getattr(r, "path", "") for r in app.routes]
    assert "/api/medication/today" in routes
    assert "/api/medication/plans/exists" in routes
