"""[PRD-BP-AI-EXPLAIN-V1 2026-05-31] 血压 AI 解读接口测试。

覆盖：
1) 档位判定 judge_bp 纯函数（正常 / 轻度偏高 / 中度偏高 / 严重偏高 / 偏低 / 未知）
2) 规则兜底文案 _fallback_single_explain / _fallback_trend_explain
3) /api/bp-v1/ai-explain-single 鉴权：未登录 401
4) /api/bp-v1/ai-explain-single 404（记录不存在）
5) /api/bp-v1/ai-explain-single 200（自己的记录走规则兜底返回 content）
6) /api/bp-v1/ai-explain-single 缓存命中（from_cache=True）
7) /api/bp-v1/ai-explain-single 403（他人的血压记录禁止解读）
8) /api/bp-v1/ai-explain-trend 鉴权：未登录 401
9) /api/bp-v1/ai-explain-trend 404（profile 不存在）
10) /api/bp-v1/ai-explain-trend 200 兜底（含 summary/trend/advice 三段）
11) /api/bp-v1/ai-explain-trend 缓存命中
12) /api/bp-v1/ai-explain-trend 403（他人 profile）
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import text

from app.api.bp_v1 import (
    judge_bp,
    _fallback_single_explain,
    _fallback_trend_explain,
    _ai_cache,
)

PREFIX = "/api/bp-v1"


# ────────── 临时建表（在 SQLite 测试 DB 上） ──────────

@pytest_asyncio.fixture(autouse=True)
async def _ensure_bp_tables():
    """强制重建 health_metric_record（ORM 默认 BigInteger PK 在 SQLite 上不自增），
    health_profiles 主表保留（含很多业务列），由 Base.metadata.create_all 提供。"""
    from tests.conftest import test_engine

    async with test_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS health_metric_record"))
        await conn.execute(text(
            "CREATE TABLE health_metric_record ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " profile_id INTEGER NOT NULL,"
            " metric_type VARCHAR(32) NOT NULL,"
            " value_json TEXT NOT NULL,"
            " source VARCHAR(32) NOT NULL DEFAULT 'manual',"
            " measured_at DATETIME NOT NULL,"
            " created_at DATETIME NOT NULL,"
            " created_by INTEGER NOT NULL"
            ")"
        ))
    _ai_cache.clear()
    yield
    _ai_cache.clear()


async def _create_user_profile_and_bp(
    user_token_str: str, profile_user_id: int,
    sbp: int = 130, dbp: int = 85,
):
    """直接通过测试 DB 写入一个 profile + 一条血压记录，返回 (profile_id, record_id)。"""
    from tests.conftest import test_session
    from app.models.models import HealthProfile
    import json as _json
    async with test_session() as s:
        prof = HealthProfile(user_id=profile_user_id, name="测试档案")
        s.add(prof)
        await s.flush()
        pid = int(prof.id)
        now = datetime.now()
        # 用 raw SQL 插入 health_metric_record（自定义 INTEGER PK + AUTOINCREMENT）
        await s.execute(text(
            "INSERT INTO health_metric_record "
            "(profile_id, metric_type, value_json, source, measured_at, created_at, created_by) "
            "VALUES (:pid, :mt, :v, :src, :ma, :ca, :cb)"
        ), {
            "pid": pid, "mt": "blood_pressure",
            "v": _json.dumps({"systolic": sbp, "diastolic": dbp}),
            "src": "manual",
            "ma": now, "ca": now, "cb": profile_user_id,
        })
        rid_row = (await s.execute(text(
            "SELECT id FROM health_metric_record ORDER BY id DESC LIMIT 1"
        ))).fetchone()
        await s.commit()
        return pid, int(rid_row[0])


# ──────────────── 1. judge_bp 纯函数 ────────────────

class TestJudgeBp:
    def test_normal(self):
        lvl, label = judge_bp(110, 70)
        assert lvl == "normal" and "正常" in label

    def test_mild_high_sbp(self):
        lvl, _ = judge_bp(130, 78)
        assert lvl == "mild_high"

    def test_mid_high_dbp(self):
        lvl, _ = judge_bp(135, 92)
        assert lvl == "mid_high"

    def test_severe_high(self):
        lvl, _ = judge_bp(165, 105)
        assert lvl == "severe_high"

    def test_low(self):
        lvl, _ = judge_bp(85, 55)
        assert lvl == "low"

    def test_unknown(self):
        lvl, label = judge_bp(None, None)
        assert lvl == "unknown" and label == "未知"


# ──────────────── 2. 兜底文案 ────────────────

class TestFallback:
    def test_single_normal_contains_value(self):
        txt = _fallback_single_explain(110, 70)
        assert "110/70 mmHg" in txt
        assert "正常" in txt

    def test_single_severe(self):
        txt = _fallback_single_explain(170, 105)
        assert "严重偏高" in txt

    def test_trend_empty(self):
        d = _fallback_trend_explain(7, [])
        assert "summary" in d and "暂无" in d["summary"]
        assert "trend" in d and "advice" in d

    def test_trend_with_rows(self):
        # 模拟 health_metric_record 行 (value_json, measured_at)
        import json as _json
        rows = [
            (_json.dumps({"systolic": 150, "diastolic": 95}), datetime.now()),
            (_json.dumps({"systolic": 120, "diastolic": 78}), datetime.now()),
        ]
        d = _fallback_trend_explain(7, rows)
        assert "summary" in d and "2 次" in d["summary"]


# ──────────────── 3. AI 单次解读端到端 ────────────────

@pytest.mark.asyncio
async def test_ai_single_requires_auth(client: AsyncClient):
    r = await client.post(f"{PREFIX}/ai-explain-single",
                          json={"record_id": 1, "profile_id": 1})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_ai_single_record_not_found(client: AsyncClient, auth_headers):
    r = await client.post(f"{PREFIX}/ai-explain-single",
                          json={"record_id": 99999, "profile_id": 1},
                          headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_ai_single_success_with_fallback(client: AsyncClient, auth_headers, user_token):
    # 当前用户 id 通过 /api/auth/me 或自查；偷懒：因为只有一个 user，user_id=1
    pid, rid = await _create_user_profile_and_bp(user_token, profile_user_id=1, sbp=135, dbp=88)
    r = await client.post(f"{PREFIX}/ai-explain-single",
                          json={"record_id": rid, "profile_id": pid},
                          headers=auth_headers)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["content"]
    assert "135/88" in d["content"] or "135" in d["content"]
    assert d["from_cache"] is False


@pytest.mark.asyncio
async def test_ai_single_cache_hit(client: AsyncClient, auth_headers, user_token):
    pid, rid = await _create_user_profile_and_bp(user_token, profile_user_id=1, sbp=120, dbp=78)
    r1 = await client.post(f"{PREFIX}/ai-explain-single",
                           json={"record_id": rid, "profile_id": pid},
                           headers=auth_headers)
    assert r1.status_code == 200 and r1.json()["data"]["from_cache"] is False
    r2 = await client.post(f"{PREFIX}/ai-explain-single",
                           json={"record_id": rid, "profile_id": pid},
                           headers=auth_headers)
    assert r2.status_code == 200 and r2.json()["data"]["from_cache"] is True


@pytest.mark.asyncio
async def test_ai_single_forbidden_other_user(client: AsyncClient, auth_headers, user_token):
    # 创建一条属于「别人」（user_id=999）的血压记录
    pid, rid = await _create_user_profile_and_bp(user_token, profile_user_id=999, sbp=130, dbp=85)
    r = await client.post(f"{PREFIX}/ai-explain-single",
                          json={"record_id": rid, "profile_id": pid},
                          headers=auth_headers)
    assert r.status_code == 403


# ──────────────── 4. AI 趋势解读端到端 ────────────────

@pytest.mark.asyncio
async def test_ai_trend_requires_auth(client: AsyncClient):
    r = await client.post(f"{PREFIX}/ai-explain-trend",
                          json={"range": "7d", "profile_id": 1})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_ai_trend_profile_not_found(client: AsyncClient, auth_headers):
    r = await client.post(f"{PREFIX}/ai-explain-trend",
                          json={"range": "7d", "profile_id": 99999},
                          headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_ai_trend_success_with_fallback(client: AsyncClient, auth_headers, user_token):
    pid, _ = await _create_user_profile_and_bp(user_token, profile_user_id=1, sbp=140, dbp=92)
    # 再插几条
    from tests.conftest import test_session
    import json as _json
    async with test_session() as s:
        for sbp, dbp, hours_ago in [(125, 80, 1), (110, 70, 24), (155, 98, 48)]:
            now = datetime.now() - timedelta(hours=hours_ago)
            await s.execute(text(
                "INSERT INTO health_metric_record "
                "(profile_id, metric_type, value_json, source, measured_at, created_at, created_by) "
                "VALUES (:pid, :mt, :v, :src, :ma, :ca, :cb)"
            ), {
                "pid": pid, "mt": "blood_pressure",
                "v": _json.dumps({"systolic": sbp, "diastolic": dbp}),
                "src": "manual",
                "ma": now, "ca": now, "cb": 1,
            })
        await s.commit()

    r = await client.post(f"{PREFIX}/ai-explain-trend",
                          json={"range": "7d", "profile_id": pid},
                          headers=auth_headers)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["summary"]
    assert d["advice"]
    assert d["from_cache"] is False


@pytest.mark.asyncio
async def test_ai_trend_cache_hit(client: AsyncClient, auth_headers, user_token):
    pid, _ = await _create_user_profile_and_bp(user_token, profile_user_id=1, sbp=130, dbp=85)
    r1 = await client.post(f"{PREFIX}/ai-explain-trend",
                           json={"range": "7d", "profile_id": pid},
                           headers=auth_headers)
    assert r1.status_code == 200 and r1.json()["data"]["from_cache"] is False
    r2 = await client.post(f"{PREFIX}/ai-explain-trend",
                           json={"range": "7d", "profile_id": pid},
                           headers=auth_headers)
    assert r2.status_code == 200 and r2.json()["data"]["from_cache"] is True


@pytest.mark.asyncio
async def test_ai_trend_forbidden_other_profile(client: AsyncClient, auth_headers, user_token):
    pid, _ = await _create_user_profile_and_bp(user_token, profile_user_id=999, sbp=130, dbp=85)
    r = await client.post(f"{PREFIX}/ai-explain-trend",
                          json={"range": "7d", "profile_id": pid},
                          headers=auth_headers)
    assert r.status_code == 403
