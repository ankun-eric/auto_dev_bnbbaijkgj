"""[PRD-MED-PLAN-ADD-OPTIM-V1 2026-05-17] 添加用药计划页面优化 — 非UI自动化测试。

覆盖药品名称联想接口 GET /api/medication-library/suggest 的关键场景：
 1. q < 2 字符 → 返回空 items
 2. q >= 2 字符 → 命中模糊匹配
 3. 未登录 → 401
 4. limit 默认 6 / 自定义上限
 5. 返回结构字段完整（id / name / generic_name / spec / manufacturer）
 6. 空关键词 → 空 items
 7. 无匹配 → 空 items 但 200
 8. 同名重复药品 → 仅出现一次
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import MedicationLibrary


async def _seed_drug(db_session, **kw):
    rec = MedicationLibrary(
        name=kw.get("name", "测试药品A"),
        generic_name=kw.get("generic_name", "Test Drug A"),
        spec=kw.get("spec", "100mg*30片"),
        manufacturer=kw.get("manufacturer", "测试药企"),
        approval_no=kw.get("approval_no"),
        category=kw.get("category"),
        rx_type=kw.get("rx_type"),
        disease_tags=kw.get("disease_tags", []),
        is_active=kw.get("is_active", True),
    )
    db_session.add(rec)
    await db_session.commit()
    return rec


# ─────────── 1) q 长度 < 2 直接返回空 ───────────


@pytest.mark.asyncio
async def test_suggest_q_too_short(client: AsyncClient, auth_headers, db_session):
    await _seed_drug(db_session, name="布洛芬缓释胶囊")
    r = await client.get(
        "/api/medication-library/suggest", params={"q": "布"}, headers=auth_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["q"] == "布"


# ─────────── 2) q 长度 >= 2 命中 ───────────


@pytest.mark.asyncio
async def test_suggest_match_basic(client: AsyncClient, auth_headers, db_session):
    await _seed_drug(db_session, name="布洛芬缓释胶囊", generic_name="Ibuprofen")
    r = await client.get(
        "/api/medication-library/suggest", params={"q": "布洛"}, headers=auth_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) >= 1
    found = [it for it in body["items"] if it["name"] == "布洛芬缓释胶囊"]
    assert found, body


# ─────────── 3) 未登录 → 401 ───────────


@pytest.mark.asyncio
async def test_suggest_unauth(client: AsyncClient):
    r = await client.get("/api/medication-library/suggest", params={"q": "布洛"})
    assert r.status_code in (401, 403)


# ─────────── 4) limit 默认 6 / 上限 6 ───────────


@pytest.mark.asyncio
async def test_suggest_limit_default_six(client: AsyncClient, auth_headers, db_session):
    for i in range(10):
        await _seed_drug(db_session, name=f"阿莫西林胶囊{i:02d}", generic_name=f"Amoxicillin{i}")
    r = await client.get(
        "/api/medication-library/suggest", params={"q": "阿莫"}, headers=auth_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 6


# ─────────── 5) 返回结构字段完整 ───────────


@pytest.mark.asyncio
async def test_suggest_response_schema(client: AsyncClient, auth_headers, db_session):
    await _seed_drug(
        db_session,
        name="二甲双胍片",
        generic_name="Metformin",
        spec="0.5g*60片",
        manufacturer="某药企",
    )
    r = await client.get(
        "/api/medication-library/suggest", params={"q": "二甲"}, headers=auth_headers
    )
    body = r.json()
    assert body["items"], body
    it = body["items"][0]
    for k in ("id", "name", "generic_name", "spec", "manufacturer"):
        assert k in it


# ─────────── 6) 空关键词 → 空 items ───────────


@pytest.mark.asyncio
async def test_suggest_empty_q(client: AsyncClient, auth_headers):
    r = await client.get(
        "/api/medication-library/suggest", params={"q": ""}, headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


# ─────────── 7) 无匹配 → 空 items 但 200 ───────────


@pytest.mark.asyncio
async def test_suggest_no_match(client: AsyncClient, auth_headers):
    r = await client.get(
        "/api/medication-library/suggest",
        params={"q": "不存在的药品名XYZ"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


# ─────────── 8) 同一记录不会重复返回 ───────────


@pytest.mark.asyncio
async def test_suggest_no_duplicate(client: AsyncClient, auth_headers, db_session):
    # name 与 generic_name 都包含关键词 → 不应重复
    await _seed_drug(db_session, name="头孢克肟分散片", generic_name="头孢克肟")
    r = await client.get(
        "/api/medication-library/suggest", params={"q": "头孢"}, headers=auth_headers
    )
    body = r.json()
    ids = [it["id"] for it in body["items"]]
    assert len(ids) == len(set(ids))
