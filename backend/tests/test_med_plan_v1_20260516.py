"""[PRD-MED-PLAN-V1 2026-05-16] 用药计划模块优化 - 非UI自动化测试

覆盖范围：
- 1) 全局开关：/api/prd469/medication-ai-call GET/PUT 默认 false / 写入后读取 / 持久化
- 2) 共管模块同源：/api/prd469/care/medication-ai-call GET/PUT 与上方共用同一份数据
- 3) reminder-setting 也透出 medication_ai_call_enabled 字段
- 4) 创建用药计划：dosage_value / dosage_unit / duration_days / guidance 全部入库并能被列表读取
- 5) 列表 ai_call_enabled / ai_call_badge：开关关闭 → 全部 false；开关开启 + 进行中 → true
- 6) 同名药品「进行中」去重：第二次创建相同药名（区分大小写、忽略前后空白）→ 409 + 错误码
- 7) 同名校验：历史/已结束计划不阻拦 → 已归档 + 同名 → 创建成功
- 8) end_date 自动归档：end_date < TODAY 且非长期 → 列表请求时自动转 archived
- 9) PUT 修改 medicine_name 撞同名 → 409
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient


def _payload(name: str, **overrides) -> dict:
    """[PRD-MED-PLAN-V1] 用药计划创建载荷（默认值贴近 PRD 默认配置）。"""
    body = {
        "medicine_name": name,
        "dosage": "1 片",
        "dosage_value": "1",
        "dosage_unit": "片",
        "time_period": "custom",
        "remind_time": "08:00",
        "frequency_per_day": 3,
        "custom_times": ["08:00", "12:00", "20:00"],
        "long_term": False,
        "start_date": date.today().isoformat(),
        "duration_days": 5,
        "guidance": "餐后",
        "notes": "",
        "reminder_enabled": True,
    }
    body.update(overrides)
    return body


# ─────────────────── 全局开关 ───────────────────


@pytest.mark.asyncio
async def test_aicall_global_default_false(client: AsyncClient, auth_headers):
    res = await client.get("/api/prd469/medication-ai-call", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["enabled"] is False


@pytest.mark.asyncio
async def test_aicall_global_put_then_get(client: AsyncClient, auth_headers):
    put_res = await client.put(
        "/api/prd469/medication-ai-call", json={"enabled": True}, headers=auth_headers
    )
    assert put_res.status_code == 200
    assert put_res.json()["enabled"] is True

    get_res = await client.get("/api/prd469/medication-ai-call", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["enabled"] is True


@pytest.mark.asyncio
async def test_aicall_care_endpoint_same_source(client: AsyncClient, auth_headers):
    # 在「共管」入口写入 → 在「健康提醒」入口读到同样结果
    put_res = await client.put(
        "/api/prd469/care/medication-ai-call",
        json={"enabled": True},
        headers=auth_headers,
    )
    assert put_res.status_code == 200
    a = await client.get("/api/prd469/medication-ai-call", headers=auth_headers)
    b = await client.get("/api/prd469/care/medication-ai-call", headers=auth_headers)
    assert a.json()["enabled"] is True and b.json()["enabled"] is True

    # 在「健康提醒」入口写关闭 → 共管也读到关闭
    await client.put(
        "/api/prd469/medication-ai-call", json={"enabled": False}, headers=auth_headers
    )
    a2 = await client.get("/api/prd469/medication-ai-call", headers=auth_headers)
    b2 = await client.get("/api/prd469/care/medication-ai-call", headers=auth_headers)
    assert a2.json()["enabled"] is False and b2.json()["enabled"] is False


@pytest.mark.asyncio
async def test_reminder_setting_returns_aicall_field(client: AsyncClient, auth_headers):
    """reminder-setting 也包含 medication_ai_call_enabled 字段（同源）。"""
    res = await client.get("/api/prd469/reminder-setting", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "medication_ai_call_enabled" in data
    assert data["medication_ai_call_enabled"] is False


# ─────────────────── 用药计划字段持久化 ───────────────────


@pytest.mark.asyncio
async def test_create_with_structured_fields(client: AsyncClient, auth_headers):
    res = await client.post(
        "/api/health-plan/medications",
        json=_payload(
            "阿司匹林肠溶片",
            dosage_value="1/2",
            dosage_unit="片",
            duration_days=7,
            guidance="睡前",
            custom_times=["08:00", "20:00"],
            frequency_per_day=2,
        ),
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dosage_value"] == "1/2"
    assert body["dosage_unit"] == "片"
    assert body["duration_days"] == 7
    assert body["guidance"] == "睡前"

    list_res = await client.get(
        "/api/health-plan/medications/list", headers=auth_headers
    )
    items = list_res.json()["items"]
    assert items[0]["dosage_value"] == "1/2"
    assert items[0]["guidance"] == "睡前"


@pytest.mark.asyncio
async def test_list_returns_ai_call_flags(client: AsyncClient, auth_headers):
    # 创建一条进行中
    r = await client.post(
        "/api/health-plan/medications",
        json=_payload("布洛芬"),
        headers=auth_headers,
    )
    assert r.status_code == 200

    # 默认开关关 → ai_call_enabled=False，每条 ai_call_badge=False
    res1 = await client.get(
        "/api/health-plan/medications/list", headers=auth_headers
    )
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["ai_call_enabled"] is False
    assert all(it.get("ai_call_badge") is False for it in body1["items"])

    # 打开开关 → ai_call_enabled=True，进行中卡片 ai_call_badge=True
    await client.put(
        "/api/prd469/medication-ai-call", json={"enabled": True}, headers=auth_headers
    )
    res2 = await client.get(
        "/api/health-plan/medications/list", headers=auth_headers
    )
    body2 = res2.json()
    assert body2["ai_call_enabled"] is True
    assert all(it.get("ai_call_badge") is True for it in body2["items"])


# ─────────────────── 同名药去重 ───────────────────


@pytest.mark.asyncio
async def test_duplicate_active_drug_blocked(client: AsyncClient, auth_headers):
    r1 = await client.post(
        "/api/health-plan/medications",
        json=_payload("二甲双胍"),
        headers=auth_headers,
    )
    assert r1.status_code == 200

    # 完全同名 → 409
    r2 = await client.post(
        "/api/health-plan/medications",
        json=_payload("二甲双胍"),
        headers=auth_headers,
    )
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    # FastAPI 会把 detail dict 直接返回
    assert detail.get("code") == "MEDICATION_DUPLICATE_ACTIVE"


@pytest.mark.asyncio
async def test_duplicate_with_whitespace_and_case(client: AsyncClient, auth_headers):
    r1 = await client.post(
        "/api/health-plan/medications",
        json=_payload("Vitamin C"),
        headers=auth_headers,
    )
    assert r1.status_code == 200

    # 大小写 + 前后空白差异 → 仍视为同名 → 409
    r2 = await client.post(
        "/api/health-plan/medications",
        json=_payload("  vitamin c "),
        headers=auth_headers,
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_archived_same_name_can_be_created(client: AsyncClient, auth_headers):
    """已归档/已结束的计划不阻拦同名新计划。"""
    # 1. 创建一条 end_date 在过去的计划（端点自带 end_date 自动计算，所以手动传过去日期）
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    res = await client.post(
        "/api/health-plan/medications",
        json=_payload(
            "感冒灵",
            start_date=week_ago,
            duration_days=1,
            end_date=yesterday,
        ),
        headers=auth_headers,
    )
    assert res.status_code == 200

    # 2. 触发列表请求，会自动归档过期计划
    list_res = await client.get(
        "/api/health-plan/medications/list", headers=auth_headers
    )
    assert list_res.status_code == 200
    # 进行中列表不应包含「感冒灵」
    assert all(it["medicine_name"] != "感冒灵" for it in list_res.json()["items"])

    # 3. 再次创建同名计划 → 应该成功
    res2 = await client.post(
        "/api/health-plan/medications",
        json=_payload("感冒灵"),
        headers=auth_headers,
    )
    assert res2.status_code == 200, res2.text


@pytest.mark.asyncio
async def test_update_to_duplicate_name_blocked(client: AsyncClient, auth_headers):
    a = await client.post(
        "/api/health-plan/medications",
        json=_payload("药A"),
        headers=auth_headers,
    )
    b = await client.post(
        "/api/health-plan/medications",
        json=_payload("药B"),
        headers=auth_headers,
    )
    assert a.status_code == 200 and b.status_code == 200
    bid = b.json()["id"]
    # 把 B 改名为 A → 应该 409
    res = await client.put(
        f"/api/health-plan/medications/{bid}",
        json={"medicine_name": "药A"},
        headers=auth_headers,
    )
    assert res.status_code == 409


# ─────────────────── 自动归档 ───────────────────


@pytest.mark.asyncio
async def test_auto_archive_expired(client: AsyncClient, auth_headers):
    # 创建一条 end_date 在过去的计划
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    r = await client.post(
        "/api/health-plan/medications",
        json=_payload(
            "已过期药",
            start_date=week_ago,
            duration_days=1,
            end_date=yesterday,
        ),
        headers=auth_headers,
    )
    assert r.status_code == 200

    # 列表请求应该自动归档
    res = await client.get(
        "/api/health-plan/medications/list", headers=auth_headers
    )
    items = res.json()["items"]
    assert all(it["medicine_name"] != "已过期药" for it in items)

    # 历史列表能查到该条
    archived = await client.get(
        "/api/health-plan/medications/list?segment=archived",
        headers=auth_headers,
    )
    assert any(it["medicine_name"] == "已过期药" for it in archived.json()["items"])


# ─────────────────── 默认值/计算 ───────────────────


@pytest.mark.asyncio
async def test_default_5_days_when_not_provided(client: AsyncClient, auth_headers):
    """不传 duration_days 时默认 5 天，并自动计算 end_date = today + 4 天。"""
    today = date.today()
    payload = _payload("默认5天药")
    payload.pop("duration_days", None)
    payload.pop("end_date", None)
    r = await client.post(
        "/api/health-plan/medications", json=payload, headers=auth_headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["duration_days"] == 5
    expected_end = (today + timedelta(days=4)).isoformat()
    assert data["end_date"] == expected_end
