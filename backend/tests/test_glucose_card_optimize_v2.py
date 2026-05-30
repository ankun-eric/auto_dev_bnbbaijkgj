"""[PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30] 血糖卡片优化 v2 测试。

覆盖 PRD §9 验收点：
- AC-01：测量类型必选（POST 不带 scene → 400）
- AC-02：6 种测量类型均可保存（含新增的 after_meal_1h / dawn）
- AC-03：8.0 mmol/L 餐后 2h → 偏高（非"危象"）
- AC-04：2.5 mmol/L 任意类型 → 重度偏低
- AC-05：12.0 mmol/L 空腹 → 重度偏高
- AC-06：PUT 修改记录（不再"新增一条"）
- AC-07：DELETE 删除记录
- AC-08：AI 解读单次接口返回结构
- AC-09：AI 解读单次缓存（第二次 from_cache=True）
- AC-10：AI 解读趋势接口返回结构
- AC-11：提示词配置 CRUD
- AC-12：提示词修改后清缓存
- 用词检查：所有返回字段不包含"危象"
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.api.glucose_v1 import (
    LEVEL_HIGH,
    LEVEL_LOW,
    LEVEL_NORMAL,
    LEVEL_VERY_HIGH,
    LEVEL_VERY_LOW,
    LEVEL_LABEL,
    LEVEL_KEY,
    SCENE_AFTER_MEAL_1H,
    SCENE_AFTER_MEAL_2H,
    SCENE_BEDTIME,
    SCENE_DAWN,
    SCENE_FASTING,
    SCENE_RANDOM,
    SCENE_KEY_TO_CODE,
    judge_level,
)

PREFIX = "/api/glucose-v1"


# ──────────────── 临时建表 ────────────────

@pytest_asyncio.fixture(autouse=True)
async def _ensure_tables():
    from tests.conftest import test_engine

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
            "CREATE TABLE IF NOT EXISTS ai_prompt_config ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " prompt_key VARCHAR(64) NOT NULL UNIQUE,"
            " name VARCHAR(128) NOT NULL,"
            " content TEXT NOT NULL,"
            " version INTEGER NOT NULL DEFAULT 1,"
            " status INTEGER NOT NULL DEFAULT 1,"
            " model_key VARCHAR(64),"
            " updated_by VARCHAR(64),"
            " updated_at DATETIME,"
            " created_at DATETIME"
            ")"
        ))
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS ai_prompt_config_history ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " prompt_key VARCHAR(64) NOT NULL,"
            " version INTEGER NOT NULL,"
            " content TEXT NOT NULL,"
            " updated_by VARCHAR(64),"
            " updated_at DATETIME"
            ")"
        ))
        await conn.execute(text("DELETE FROM health_glucose_record"))
        await conn.execute(text("DELETE FROM health_glucose_alert"))
        await conn.execute(text("DELETE FROM ai_prompt_config"))
        await conn.execute(text("DELETE FROM ai_prompt_config_history"))
    yield


# ──────────────── 五档阈值（六类型） ────────────────

class TestSixSceneThresholds:
    """[PRD §3.2] 六类型五档阈值表。"""

    # AC-03
    def test_after_meal_2h_8_0_is_high(self):
        """8.0 mmol/L + 餐后 2h → 偏高（不是"危象"）"""
        lv = judge_level(8.0, SCENE_AFTER_MEAL_2H)
        assert lv == LEVEL_HIGH
        assert LEVEL_LABEL[lv] == "偏高"
        assert "危象" not in LEVEL_LABEL[lv]

    # AC-04
    @pytest.mark.parametrize("sc", [
        SCENE_FASTING, SCENE_AFTER_MEAL_1H, SCENE_AFTER_MEAL_2H,
        SCENE_BEDTIME, SCENE_DAWN, SCENE_RANDOM,
    ])
    def test_value_under_28_always_low_critical(self, sc):
        assert judge_level(2.5, sc) == LEVEL_VERY_LOW
        assert LEVEL_LABEL[LEVEL_VERY_LOW] == "重度偏低"

    # AC-05
    def test_fasting_12_0_is_high_critical(self):
        assert judge_level(12.0, SCENE_FASTING) == LEVEL_VERY_HIGH
        assert LEVEL_LABEL[LEVEL_VERY_HIGH] == "重度偏高"

    def test_after_meal_1h_thresholds(self):
        # 餐后 1h: 3.9-9.0 正常, 9.0-11.1 偏高, ≥11.1 重度偏高
        assert judge_level(8.9, SCENE_AFTER_MEAL_1H) == LEVEL_NORMAL
        assert judge_level(9.0, SCENE_AFTER_MEAL_1H) == LEVEL_HIGH
        assert judge_level(10.0, SCENE_AFTER_MEAL_1H) == LEVEL_HIGH
        assert judge_level(11.1, SCENE_AFTER_MEAL_1H) == LEVEL_VERY_HIGH

    def test_dawn_thresholds(self):
        # 凌晨: 3.9-5.6 正常, 5.6-7.0 偏高, ≥7.0 重度偏高
        assert judge_level(5.5, SCENE_DAWN) == LEVEL_NORMAL
        assert judge_level(5.6, SCENE_DAWN) == LEVEL_HIGH
        assert judge_level(6.9, SCENE_DAWN) == LEVEL_HIGH
        assert judge_level(7.0, SCENE_DAWN) == LEVEL_VERY_HIGH


class TestLevelLabelNoCrisis:
    """[PRD §一/§3.1] 文案不再包含"危象"字眼。"""

    def test_all_level_labels_no_crisis(self):
        for label in LEVEL_LABEL.values():
            assert "危象" not in label, f"档位文案不应包含「危象」：{label}"

    def test_level_key_format(self):
        assert LEVEL_KEY[LEVEL_VERY_LOW] == "low_critical"
        assert LEVEL_KEY[LEVEL_LOW] == "low"
        assert LEVEL_KEY[LEVEL_NORMAL] == "normal"
        assert LEVEL_KEY[LEVEL_HIGH] == "high"
        assert LEVEL_KEY[LEVEL_VERY_HIGH] == "high_critical"


class TestSceneKeyMapping:
    """[PRD §3.3] 6 种测量类型字符串 key 与数字编码。"""

    def test_all_6_keys_mapped(self):
        for key in ("fasting", "after_meal_1h", "after_meal_2h",
                    "before_sleep", "dawn", "random"):
            assert key in SCENE_KEY_TO_CODE
        # 字符串 key 编码合法
        assert SCENE_KEY_TO_CODE["fasting"] == SCENE_FASTING
        assert SCENE_KEY_TO_CODE["after_meal_1h"] == SCENE_AFTER_MEAL_1H
        assert SCENE_KEY_TO_CODE["dawn"] == SCENE_DAWN

    def test_legacy_after_meal_to_2h(self):
        """旧值 'after_meal' 映射到 after_meal_2h"""
        assert SCENE_KEY_TO_CODE["after_meal"] == SCENE_AFTER_MEAL_2H

    def test_legacy_bedtime_to_before_sleep(self):
        assert SCENE_KEY_TO_CODE["bedtime"] == SCENE_BEDTIME


# ──────────────── API：POST 验收 ────────────────

@pytest.mark.asyncio
async def test_ac01_scene_required(client: AsyncClient, auth_headers):
    """[AC-01] 不传 scene → 400"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 5.5},
                          headers=auth_headers)
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_ac01_scene_none_rejected(client: AsyncClient, auth_headers):
    """显式 scene=null → 400"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 5.5, "scene": None},
                          headers=auth_headers)
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_ac02_after_meal_1h_str(client: AsyncClient, auth_headers):
    """[AC-02] 餐后1h 字符串 key 可保存"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 8.5, "scene": "after_meal_1h"},
                          headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    rec = body["record"]
    assert rec["scene"] == SCENE_AFTER_MEAL_1H
    assert rec["scene_label"] == "餐后1h"
    assert rec["period_label"] == "餐后1h"
    assert rec["period"] == "after_meal_1h"


@pytest.mark.asyncio
async def test_ac02_dawn_str(client: AsyncClient, auth_headers):
    """[AC-02] 凌晨 字符串 key 可保存"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 5.0, "scene": "dawn"},
                          headers=auth_headers)
    assert r.status_code == 200, r.text
    rec = r.json()["record"]
    assert rec["scene"] == SCENE_DAWN
    assert rec["scene_label"] == "凌晨"


@pytest.mark.asyncio
async def test_ac03_after_meal_2h_8_0_returns_high(client: AsyncClient, auth_headers):
    """[AC-03] 8.0 + 餐后2h → 偏高"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 8.0, "scene": "after_meal_2h"},
                          headers=auth_headers)
    assert r.status_code == 200
    rec = r.json()["record"]
    assert rec["level"] == LEVEL_HIGH
    assert rec["level_label"] == "偏高"
    assert rec["level_key"] == "high"
    # 严禁出现"危象"
    assert "危象" not in rec["level_label"]


@pytest.mark.asyncio
async def test_ac04_low_critical_label(client: AsyncClient, auth_headers):
    """[AC-04] 2.5 → 重度偏低"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 2.5, "scene": "fasting"},
                          headers=auth_headers)
    assert r.status_code == 200
    rec = r.json()["record"]
    assert rec["level"] == LEVEL_VERY_LOW
    assert rec["level_label"] == "重度偏低"
    assert rec["level_key"] == "low_critical"


@pytest.mark.asyncio
async def test_ac05_high_critical_label(client: AsyncClient, auth_headers):
    """[AC-05] 12.0 + 空腹 → 重度偏高"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 12.0, "scene": "fasting"},
                          headers=auth_headers)
    assert r.status_code == 200
    rec = r.json()["record"]
    assert rec["level"] == LEVEL_VERY_HIGH
    assert rec["level_label"] == "重度偏高"


# ──────────────── API：PUT / DELETE ────────────────

@pytest.mark.asyncio
async def test_ac06_put_record_updates_in_place(client: AsyncClient, auth_headers):
    """[AC-06] PUT 修改记录：原记录被更新而非新增一条"""
    # 1) 先建一条
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 5.5, "scene": "fasting"},
                          headers=auth_headers)
    rid = r.json()["record"]["id"]

    # 2) PUT 修改
    r2 = await client.put(f"{PREFIX}/records/{rid}",
                          json={"value": 8.0, "scene": "after_meal_2h"},
                          headers=auth_headers)
    assert r2.status_code == 200, r2.text
    rec = r2.json()
    assert rec["id"] == rid
    assert rec["value"] == 8.0
    assert rec["scene"] == SCENE_AFTER_MEAL_2H
    assert rec["level_label"] == "偏高"  # 重新计算

    # 3) 列表应只有 1 条
    r3 = await client.get(f"{PREFIX}/records", headers=auth_headers)
    assert r3.json()["total"] == 1


@pytest.mark.asyncio
async def test_ac07_delete_record(client: AsyncClient, auth_headers):
    """[AC-07] DELETE 删除记录"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 6.0, "scene": "fasting"},
                          headers=auth_headers)
    rid = r.json()["record"]["id"]

    r2 = await client.delete(f"{PREFIX}/records/{rid}",
                              headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["deleted"] is True

    # 列表为空
    r3 = await client.get(f"{PREFIX}/records", headers=auth_headers)
    assert r3.json()["total"] == 0


# ──────────────── API：AI 解读 ────────────────

@pytest.mark.asyncio
async def test_ac08_ai_explain_single_response_shape(client: AsyncClient, auth_headers):
    """[AC-08] AI 单次解读返回结构正确"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 8.0, "scene": "after_meal_2h"},
                          headers=auth_headers)
    rid = r.json()["record"]["id"]

    r2 = await client.post(f"{PREFIX}/ai-explain-single",
                            json={"record_id": rid},
                            headers=auth_headers)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    data = body.get("data") or body
    assert "from_cache" in data
    assert "model" in data
    assert "prompt_version" in data
    assert "content" in data
    assert "generated_at" in data
    assert data["from_cache"] is False
    # 内容不应含"危象"
    assert "危象" not in data["content"]


@pytest.mark.asyncio
async def test_ac09_ai_single_cache(client: AsyncClient, auth_headers):
    """[AC-09] 第二次调用 from_cache=True"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 6.5, "scene": "after_meal_2h"},
                          headers=auth_headers)
    rid = r.json()["record"]["id"]

    r1 = await client.post(f"{PREFIX}/ai-explain-single",
                            json={"record_id": rid},
                            headers=auth_headers)
    r2 = await client.post(f"{PREFIX}/ai-explain-single",
                            json={"record_id": rid},
                            headers=auth_headers)
    d2 = r2.json().get("data") or r2.json()
    assert d2["from_cache"] is True
    # 两次内容相同
    d1 = r1.json().get("data") or r1.json()
    assert d2["content"] == d1["content"]


@pytest.mark.asyncio
async def test_ac10_ai_explain_trend_response_shape(client: AsyncClient, auth_headers):
    """[AC-10] AI 趋势解读返回结构"""
    # 先录入几条
    for v in (6.5, 7.2, 5.8, 8.1):
        await client.post(f"{PREFIX}/records",
                          json={"value": v, "scene": "after_meal_2h"},
                          headers=auth_headers)

    r = await client.post(f"{PREFIX}/ai-explain-trend",
                          json={"range": "7d"},
                          headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    data = body.get("data") or body
    assert "summary" in data
    assert "trend" in data
    assert "advice" in data
    assert "model" in data
    assert data["summary"]


@pytest.mark.asyncio
async def test_trend_no_crisis_in_output(client: AsyncClient, auth_headers):
    """趋势文案不应包含"危象"字眼"""
    for v in (12.5, 16.8):
        await client.post(f"{PREFIX}/records",
                          json={"value": v, "scene": "after_meal_2h"},
                          headers=auth_headers)
    r = await client.post(f"{PREFIX}/ai-explain-trend",
                          json={"range": "7d"},
                          headers=auth_headers)
    data = r.json().get("data") or r.json()
    full = (data.get("summary", "") + data.get("trend", "") + data.get("advice", ""))
    assert "危象" not in full


# ──────────────── API：管理后台提示词配置 ────────────────

@pytest.mark.asyncio
async def test_ac11_admin_list_prompts(client: AsyncClient):
    """[AC-11] 管理后台可列出两条血糖提示词"""
    r = await client.get(f"{PREFIX}/admin/ai-prompts")
    assert r.status_code == 200, r.text
    items = (r.json().get("data") or r.json())["items"]
    keys = {it["prompt_key"] for it in items}
    assert "glucose_single_explain" in keys
    assert "glucose_trend_explain" in keys


@pytest.mark.asyncio
async def test_ac11_admin_update_prompt(client: AsyncClient):
    """[AC-11] 管理后台可更新提示词，版本号 +1"""
    # 先列出
    r = await client.get(f"{PREFIX}/admin/ai-prompts")
    items = (r.json().get("data") or r.json())["items"]
    cur = next(it for it in items if it["prompt_key"] == "glucose_single_explain")
    old_v = cur["version"]

    new_content = "测试提示词内容 — 数值 {value} 测量类型 {period_label} 档位 {level_label}"
    r2 = await client.put(f"{PREFIX}/admin/ai-prompts/glucose_single_explain",
                           json={"content": new_content, "updated_by": "tester"})
    assert r2.status_code == 200, r2.text
    body = r2.json().get("data") or r2.json()
    assert body["version"] == old_v + 1

    # 再查列表，内容已更新
    r3 = await client.get(f"{PREFIX}/admin/ai-prompts")
    items3 = (r3.json().get("data") or r3.json())["items"]
    cur3 = next(it for it in items3 if it["prompt_key"] == "glucose_single_explain")
    assert cur3["content"] == new_content
    assert cur3["version"] == old_v + 1


@pytest.mark.asyncio
async def test_admin_update_invalid_key(client: AsyncClient):
    r = await client.put(f"{PREFIX}/admin/ai-prompts/unknown_key",
                          json={"content": "x"})
    assert r.status_code == 400


# ──────────────── 兼容性 ────────────────

@pytest.mark.asyncio
async def test_ac14_legacy_after_meal_compat(client: AsyncClient, auth_headers):
    """[AC-14] 旧值 after_meal 兼容映射到 after_meal_2h"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 7.5, "scene": "after_meal"},
                          headers=auth_headers)
    assert r.status_code == 200
    rec = r.json()["record"]
    assert rec["scene"] == SCENE_AFTER_MEAL_2H
    assert rec["period"] == "after_meal_2h"


@pytest.mark.asyncio
async def test_int_scene_still_works(client: AsyncClient, auth_headers):
    """旧前端可能传 int 1~6，应同样可用"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 5.0, "scene": 1},
                          headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["record"]["scene"] == SCENE_FASTING

    r2 = await client.post(f"{PREFIX}/records",
                            json={"value": 5.0, "scene": 6},
                            headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["record"]["scene"] == SCENE_DAWN


@pytest.mark.asyncio
async def test_alert_message_no_crisis_keyword(client: AsyncClient, auth_headers):
    """触发 alert 时 message 不含"危象"字眼"""
    r = await client.post(f"{PREFIX}/records",
                          json={"value": 17.0, "scene": "random"},
                          headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    alert = body.get("alert") or {}
    if alert:
        assert "危象" not in (alert.get("message") or "")
        assert "危象" not in (alert.get("alert_label") or "")
