"""[PRD-GLUCOSE-V1 2026-05-30] 血糖闭环模块测试。

覆盖：
- 五档判定函数（单测，纯函数）
- 高/低糖危象判定
- 录入合理范围拦截（API 层）
- 鉴权
- 端到端：录入正常 → 列表 / 统计 / AI 建议 / 报告 元数据 / 提醒配置 / 预警事件
  （端到端测试依赖临时 SQLite 建表）
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.api.glucose_v1 import (
    CRISIS_HIGH,
    CRISIS_LOW,
    CRISIS_NONE,
    LEVEL_HIGH,
    LEVEL_LOW,
    LEVEL_NORMAL,
    LEVEL_VERY_HIGH,
    LEVEL_VERY_LOW,
    SCENE_AFTER_MEAL,
    SCENE_BEDTIME,
    SCENE_FASTING,
    SCENE_RANDOM,
    judge_crisis,
    judge_level,
)

PREFIX = "/api/glucose-v1"


# ──────────────── 临时建表（在 SQLite 测试 DB 上） ────────────────

@pytest_asyncio.fixture(autouse=True)
async def _ensure_glucose_tables():
    from tests.conftest import test_engine  # 复用全局 engine

    async with test_engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS health_glucose_record ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " user_id INTEGER NOT NULL,"
            " value REAL NOT NULL,"
            " scene INTEGER NOT NULL,"
            " level INTEGER NOT NULL,"
            " is_crisis INTEGER NOT NULL DEFAULT 0,"
            " measure_time DATETIME NOT NULL,"
            " note VARCHAR(200),"
            " create_time DATETIME NOT NULL"
            ")"
        ))
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS health_glucose_alert ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " record_id INTEGER NOT NULL,"
            " user_id INTEGER NOT NULL,"
            " alert_type INTEGER NOT NULL,"
            " push_status INTEGER NOT NULL DEFAULT 0,"
            " guardian_confirmed INTEGER NOT NULL DEFAULT 0,"
            " message VARCHAR(512),"
            " guardian_ids VARCHAR(512),"
            " create_time DATETIME NOT NULL"
            ")"
        ))
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS health_glucose_reminder ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " user_id INTEGER NOT NULL UNIQUE,"
            " breakfast VARCHAR(8),"
            " lunch VARCHAR(8),"
            " dinner VARCHAR(8),"
            " enabled INTEGER NOT NULL DEFAULT 0,"
            " created_at DATETIME,"
            " updated_at DATETIME"
            ")"
        ))
        # 每个测试前清空
        await conn.execute(text("DELETE FROM health_glucose_record"))
        await conn.execute(text("DELETE FROM health_glucose_alert"))
        await conn.execute(text("DELETE FROM health_glucose_reminder"))
    yield


# ──────────────── 纯函数：五档判定 ────────────────

class TestJudgeLevelFasting:
    def test_very_low(self):
        assert judge_level(2.5, SCENE_FASTING) == LEVEL_VERY_LOW

    def test_low_boundary(self):
        # 2.8 起算偏低
        assert judge_level(2.8, SCENE_FASTING) == LEVEL_LOW
        assert judge_level(3.5, SCENE_FASTING) == LEVEL_LOW

    def test_normal_fasting(self):
        assert judge_level(3.9, SCENE_FASTING) == LEVEL_NORMAL
        assert judge_level(5.5, SCENE_FASTING) == LEVEL_NORMAL
        assert judge_level(6.0, SCENE_FASTING) == LEVEL_NORMAL

    def test_high_fasting(self):
        assert judge_level(6.1, SCENE_FASTING) == LEVEL_HIGH
        assert judge_level(6.9, SCENE_FASTING) == LEVEL_HIGH

    def test_very_high_fasting(self):
        assert judge_level(7.0, SCENE_FASTING) == LEVEL_VERY_HIGH
        assert judge_level(10.0, SCENE_FASTING) == LEVEL_VERY_HIGH


class TestJudgeLevelAfterMeal:
    def test_normal_after_meal(self):
        assert judge_level(6.5, SCENE_AFTER_MEAL) == LEVEL_NORMAL
        assert judge_level(7.7, SCENE_AFTER_MEAL) == LEVEL_NORMAL

    def test_high_after_meal(self):
        assert judge_level(7.8, SCENE_AFTER_MEAL) == LEVEL_HIGH
        assert judge_level(10.5, SCENE_AFTER_MEAL) == LEVEL_HIGH

    def test_very_high_after_meal(self):
        assert judge_level(11.1, SCENE_AFTER_MEAL) == LEVEL_VERY_HIGH
        assert judge_level(15.0, SCENE_AFTER_MEAL) == LEVEL_VERY_HIGH


class TestJudgeLevelRandomBedtime:
    def test_random_uses_after_meal_thresholds(self):
        # 随机/睡前简化为同餐后2h阈值
        assert judge_level(7.0, SCENE_RANDOM) == LEVEL_NORMAL
        assert judge_level(8.0, SCENE_RANDOM) == LEVEL_HIGH
        assert judge_level(7.0, SCENE_BEDTIME) == LEVEL_NORMAL
        assert judge_level(12.0, SCENE_BEDTIME) == LEVEL_VERY_HIGH


class TestJudgeCrisis:
    def test_high_crisis(self):
        assert judge_crisis(16.7) == CRISIS_HIGH
        assert judge_crisis(20.0) == CRISIS_HIGH

    def test_low_crisis(self):
        assert judge_crisis(2.7) == CRISIS_LOW
        assert judge_crisis(0.6) == CRISIS_LOW

    def test_normal(self):
        assert judge_crisis(5.0) == CRISIS_NONE
        assert judge_crisis(15.0) == CRISIS_NONE
        assert judge_crisis(2.8) == CRISIS_NONE  # 边界值不属于危象（≥2.8）


# ──────────────── 鉴权 ────────────────

@pytest.mark.asyncio
async def test_create_record_requires_auth(client: AsyncClient):
    r = await client.post(f"{PREFIX}/records", json={"value": 5.5, "scene": 1})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_records_requires_auth(client: AsyncClient):
    r = await client.get(f"{PREFIX}/records")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_stats_requires_auth(client: AsyncClient):
    r = await client.get(f"{PREFIX}/stats")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_alerts_requires_auth(client: AsyncClient):
    r = await client.get(f"{PREFIX}/alerts")
    assert r.status_code in (401, 403)


# ──────────────── 录入合法性 ────────────────

@pytest.mark.asyncio
async def test_create_invalid_scene(client: AsyncClient, auth_headers):
    r = await client.post(f"{PREFIX}/records", json={"value": 5.5, "scene": 99},
                          headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_value_out_of_range_low(client: AsyncClient, auth_headers):
    r = await client.post(f"{PREFIX}/records", json={"value": 0.3, "scene": 1},
                          headers=auth_headers)
    assert r.status_code == 400
    assert "范围" in r.json().get("detail", "")


@pytest.mark.asyncio
async def test_create_value_out_of_range_high(client: AsyncClient, auth_headers):
    """[AC-10] 录入 36 被拦截"""
    r = await client.post(f"{PREFIX}/records", json={"value": 36.0, "scene": 1},
                          headers=auth_headers)
    assert r.status_code == 400


# ──────────────── 端到端：录入路径 ────────────────

@pytest.mark.asyncio
async def test_create_normal_no_alert(client: AsyncClient, auth_headers):
    """[AC-01] 录入空腹 5.5，判定为正常，无任何推送"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 5.5, "scene": SCENE_FASTING},
                          headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["record"]["level"] == LEVEL_NORMAL
    assert data["record"]["is_crisis"] == CRISIS_NONE
    assert data["alert"] is None


@pytest.mark.asyncio
async def test_create_fasting_very_high(client: AsyncClient, auth_headers):
    """[AC-02] 录入空腹 7.5，判定为严重偏高，触发推送"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 7.5, "scene": SCENE_FASTING},
                          headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["record"]["level"] == LEVEL_VERY_HIGH
    assert data["record"]["is_crisis"] == CRISIS_NONE
    assert data["alert"] is not None
    assert data["alert"]["must_popup"] is False
    assert data["alert"]["alert_label"] == "严重偏高"


@pytest.mark.asyncio
async def test_create_high_glucose_crisis(client: AsyncClient, auth_headers):
    """[AC-03] 录入餐后 16.8，触发高糖危象，强提示 + 守护人推送"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 16.8, "scene": SCENE_AFTER_MEAL},
                          headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["record"]["is_crisis"] == CRISIS_HIGH
    assert data["alert"] is not None
    assert data["alert"]["must_popup"] is True
    assert data["alert"]["alert_label"] == "高糖危象"
    assert data["alert"]["guardian_notified"] is True


@pytest.mark.asyncio
async def test_create_low_glucose_crisis(client: AsyncClient, auth_headers):
    """[AC-04] 录入随机 2.5，触发低糖危象，强提示 + 守护人推送"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 2.5, "scene": SCENE_RANDOM},
                          headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["record"]["is_crisis"] == CRISIS_LOW
    assert data["alert"] is not None
    assert data["alert"]["must_popup"] is True
    assert data["alert"]["alert_label"] == "低糖危象"


# ──────────────── 列表 / 统计 ────────────────

@pytest.mark.asyncio
async def test_list_records_returns_inserted(client: AsyncClient, auth_headers):
    # 录入几条
    for v, sc in [(5.5, 1), (8.5, 2), (3.5, 3)]:
        await client.post(f"{PREFIX}/records",
                          json={"value": v, "scene": sc},
                          headers=auth_headers)
    r = await client.get(f"{PREFIX}/records", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    # 倒序：最近一条为 3.5
    assert data["items"][0]["value"] == 3.5


@pytest.mark.asyncio
async def test_list_records_filter_by_scene(client: AsyncClient, auth_headers):
    await client.post(f"{PREFIX}/records", json={"value": 5.5, "scene": 1}, headers=auth_headers)
    await client.post(f"{PREFIX}/records", json={"value": 8.5, "scene": 2}, headers=auth_headers)
    r = await client.get(f"{PREFIX}/records?scene=1", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert all(it["scene"] == 1 for it in data["items"])


@pytest.mark.asyncio
async def test_stats_returns_distribution(client: AsyncClient, auth_headers):
    await client.post(f"{PREFIX}/records", json={"value": 5.5, "scene": 1}, headers=auth_headers)
    await client.post(f"{PREFIX}/records", json={"value": 8.5, "scene": 2}, headers=auth_headers)
    r = await client.get(f"{PREFIX}/stats?days=7", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] == 2
    assert data["avg"] is not None
    assert "正常" in data["distribution"]
    assert "偏高" in data["distribution"]
    assert len(data["trend"]) == 7


# ──────────────── 预警事件 ────────────────

@pytest.mark.asyncio
async def test_alerts_list_after_crisis(client: AsyncClient, auth_headers):
    await client.post(f"{PREFIX}/records",
                      json={"value": 18.0, "scene": SCENE_AFTER_MEAL},
                      headers=auth_headers)
    r = await client.get(f"{PREFIX}/alerts", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["alert_label"] == "高糖危象"


@pytest.mark.asyncio
async def test_confirm_alert(client: AsyncClient, auth_headers):
    save = await client.post(f"{PREFIX}/records",
                             json={"value": 2.5, "scene": SCENE_RANDOM},
                             headers=auth_headers)
    alert_id = save.json()["alert"]["alert_id"]
    assert alert_id > 0
    r = await client.post(f"{PREFIX}/alerts/{alert_id}/confirm", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["confirmed"] is True


# ──────────────── AI 建议 + 报告 ────────────────

@pytest.mark.asyncio
async def test_ai_advice_disclaimer(client: AsyncClient, auth_headers):
    """[AC-08] AI 建议页显著标注「仅供参考」"""
    r = await client.get(f"{PREFIX}/ai-advice?days=30", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "仅供参考" in data["disclaimer"]
    assert isinstance(data["advice_lines"], list) and len(data["advice_lines"]) > 0


@pytest.mark.asyncio
async def test_report_meta(client: AsyncClient, auth_headers):
    r = await client.get(f"{PREFIX}/report?days=30", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "stats" in data
    assert "ai_advice" in data
    assert data["share_valid_days"] == 7


# ──────────────── 餐后提醒 ────────────────

@pytest.mark.asyncio
async def test_reminder_set_and_get(client: AsyncClient, auth_headers):
    """[AC-05] 设置餐后提醒"""
    body = {"breakfast": "07:00", "lunch": "12:30", "dinner": "19:00", "enabled": True}
    r = await client.put(f"{PREFIX}/reminder", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    r2 = await client.get(f"{PREFIX}/reminder", headers=auth_headers)
    assert r2.status_code == 200
    data = r2.json()
    assert data["breakfast"] == "07:00"
    assert data["dinner"] == "19:00"
    assert data["enabled"] is True


# ──────────────── 删除 ────────────────

@pytest.mark.asyncio
async def test_delete_own_record(client: AsyncClient, auth_headers):
    save = await client.post(f"{PREFIX}/records",
                             json={"value": 5.5, "scene": 1},
                             headers=auth_headers)
    rid = save.json()["record"]["id"]
    r = await client.delete(f"{PREFIX}/records/{rid}", headers=auth_headers)
    assert r.status_code == 200
    # 再次查询不应再有该条
    r2 = await client.get(f"{PREFIX}/records", headers=auth_headers)
    assert all(it["id"] != rid for it in r2.json()["items"])
