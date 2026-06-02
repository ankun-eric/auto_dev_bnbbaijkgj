"""[PRD-SLEEP-ALL-HISTORY-FIX-V1 2026-06-02] 睡眠「全部历史」显示不全 & 编辑保存异常 — 修复测试

Bug 根因：四指标通用「全部历史」模板（H5 health-metric/[type]/history）漏掉了睡眠这种
双值指标（{ duration_h, deep_h }），导致：
  ① 列表数值格式化只认血压双值/单值，睡眠输出残缺的 `- h`；
  ② 状态档位配置缺睡眠四档；
  ③ 编辑弹窗缺睡眠时长/深睡时长输入框；
  ④ 编辑保存 value 拼装按血压/单值规则走，睡眠双值无法正确组装。

本套测试覆盖：
1) 后端 health-metric-v1 全部历史接口对 sleep 正确返回 value（duration_h/deep_h）+ status 四档；
2) 后端 PUT 更新 sleep 双值（duration_h + deep_h）正确写回，更新原记录不新增；
3) 后端 PUT 仅更新 duration_h 时保留/覆盖 deep_h 的合并行为；
4) 前端 H5 history 模板源码静态断言：睡眠格式化、四档配置、编辑字段、value 拼装。
"""
from __future__ import annotations

import json as _json
import os
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text


@pytest_asyncio.fixture(autouse=True)
async def _ensure_metric_table():
    """health_metric_record 主键在 SQLite 不自增，重建为自增 INTEGER。"""
    from .conftest import test_engine

    async with test_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS health_metric_record"))
        await conn.execute(text(
            "CREATE TABLE health_metric_record ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " profile_id INTEGER NOT NULL,"
            " metric_type VARCHAR(32) NOT NULL,"
            " value_json JSON NOT NULL,"
            " source VARCHAR(32),"
            " measured_at DATETIME NOT NULL,"
            " created_at DATETIME,"
            " created_by INTEGER"
            ")"
        ))
    yield


@pytest_asyncio.fixture
async def user_auth(client: AsyncClient, auth_headers):
    from sqlalchemy import select

    from app.models.models import User
    from .conftest import test_session

    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == "13900000001"))
        user = res.scalar_one()
        return {"user_id": user.id, "headers": auth_headers}


@pytest_asyncio.fixture
async def sleep_profile(user_auth):
    from app.models.models import FamilyMember, HealthProfile

    from .conftest import test_session

    user_id = user_auth["user_id"]
    async with test_session() as session:
        fm = FamilyMember(
            user_id=user_id, relationship_type="本人", nickname="睡眠历史修复本人",
            is_self=True, gender="male", status="active",
        )
        session.add(fm)
        await session.flush()
        hp = HealthProfile(
            user_id=user_id, family_member_id=fm.id, name="睡眠历史修复本人", gender="male",
        )
        session.add(hp)
        await session.commit()
        return {"profile_id": hp.id, "user_id": user_id}


_RID_COUNTER = {"next": 95000}


async def _insert_sleep_record(profile_id: int, duration_h: float, *,
                               days_ago: int = 0, hour: int = 7, minute: int = 20,
                               source: str = "manual", user_id: int = 1,
                               deep_h: float | None = None):
    from .conftest import test_session

    _RID_COUNTER["next"] += 1
    rid = _RID_COUNTER["next"]
    measured_at = (datetime.now() - timedelta(days=days_ago)).replace(
        hour=hour, minute=minute, second=0, microsecond=0)
    vj = {"duration_h": duration_h}
    if deep_h is not None:
        vj["deep_h"] = deep_h
    async with test_session() as session:
        await session.execute(text(
            "INSERT INTO health_metric_record (id, profile_id, metric_type, value_json, source, measured_at, created_at, created_by) "
            "VALUES (:id, :pid, 'sleep', :vj, :src, :ma, :ca, :cb)"
        ), {
            "id": rid, "pid": profile_id,
            "vj": _json.dumps(vj),
            "src": source, "ma": measured_at, "ca": datetime.now(), "cb": user_id,
        })
        await session.commit()
    return rid


# ─── 后端 TC-1：全部历史接口对 sleep 返回完整 value + 四档 status ─────────────

@pytest.mark.asyncio
async def test_history_filters_sleep_returns_full_value_and_status(client: AsyncClient, user_auth, sleep_profile):
    pid = sleep_profile["profile_id"]
    uid = sleep_profile["user_id"]
    # 充足（8h 含深睡）、偏少（6.5h）、不足（5h）、偏多（10h）
    await _insert_sleep_record(pid, 8.0, deep_h=2.5, days_ago=0, user_id=uid)
    await _insert_sleep_record(pid, 6.5, days_ago=1, user_id=uid)
    await _insert_sleep_record(pid, 5.0, days_ago=2, user_id=uid)
    await _insert_sleep_record(pid, 10.0, days_ago=3, user_id=uid)

    resp = await client.get(
        f"/api/health-metric-v1/{pid}/sleep/history",
        headers=user_auth["headers"], params={"date_range": "30d"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["metric_type"] == "sleep"
    assert data["meta"]["label"] == "睡眠"
    assert data["meta"]["unit"] == "h"
    items = data["items"]
    assert len(items) == 4

    by_dur = {float(it["value"]["duration_h"]): it for it in items}
    # ① 双值结构完整透传：duration_h 必有，含深睡的那条 deep_h 也在
    assert by_dur[8.0]["value"].get("deep_h") == 2.5
    # ② 四档 status 正确（与详情页/后端一致）
    assert by_dur[8.0]["status"]["key"] == "enough"
    assert by_dur[8.0]["status"]["color"] == "blue"
    assert by_dur[6.5]["status"]["key"] == "less"
    assert by_dur[6.5]["status"]["color"] == "yellow"
    assert by_dur[5.0]["status"]["key"] == "insufficient"
    assert by_dur[5.0]["status"]["color"] == "orange"
    assert by_dur[10.0]["status"]["key"] == "more"
    assert by_dur[10.0]["status"]["color"] == "yellow"
    # editable：手工录入可改
    assert all(it["editable"] for it in items)


# ─── 后端 TC-2：按 status 筛选 sleep 档位 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_history_filters_sleep_status_filter(client: AsyncClient, user_auth, sleep_profile):
    pid = sleep_profile["profile_id"]
    uid = sleep_profile["user_id"]
    await _insert_sleep_record(pid, 8.0, days_ago=0, user_id=uid)
    await _insert_sleep_record(pid, 5.0, days_ago=1, user_id=uid)

    resp = await client.get(
        f"/api/health-metric-v1/{pid}/sleep/history",
        headers=user_auth["headers"], params={"date_range": "30d", "status": "insufficient"},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert float(items[0]["value"]["duration_h"]) == 5.0
    assert items[0]["status"]["key"] == "insufficient"


# ─── 后端 TC-3：PUT 更新 sleep 双值（duration_h + deep_h）写回原记录 ──────────

@pytest.mark.asyncio
async def test_put_sleep_double_value_updates_in_place(client: AsyncClient, user_auth, sleep_profile):
    pid = sleep_profile["profile_id"]
    h = user_auth["headers"]

    # 先录入一条
    post = await client.post(
        f"/api/health-profile-v3/{pid}/metric/sleep",
        headers=h, json={"value": {"duration_h": 7.0, "deep_h": 1.5}, "source": "manual"},
    )
    assert post.status_code == 200, post.text
    rid = post.json()["id"]

    # 模拟全部历史页编辑保存：value 为双值对象
    put = await client.put(
        f"/api/health-profile-v3/{pid}/metric/sleep/{rid}",
        headers=h, json={"value": {"duration_h": 8.5, "deep_h": 3.0}},
    )
    assert put.status_code == 200, put.text

    # 历史确认更新原记录（不新增）
    resp = await client.get(
        f"/api/health-metric-v1/{pid}/sleep/history",
        headers=h, params={"date_range": "30d"},
    )
    items = resp.json()["data"]["items"]
    assert len(items) == 1, "更新应在原记录上进行，不得新增"
    it = items[0]
    assert it["id"] == rid
    assert float(it["value"]["duration_h"]) == 8.5
    assert float(it["value"]["deep_h"]) == 3.0
    assert it["status"]["key"] == "enough"


# ─── 后端 TC-4：PUT 仅更新 duration_h 不影响其他字段（merge 行为）────────────

@pytest.mark.asyncio
async def test_put_sleep_partial_value_merge(client: AsyncClient, user_auth, sleep_profile):
    pid = sleep_profile["profile_id"]
    h = user_auth["headers"]

    post = await client.post(
        f"/api/health-profile-v3/{pid}/metric/sleep",
        headers=h, json={"value": {"duration_h": 7.0, "deep_h": 2.0}, "source": "manual"},
    )
    rid = post.json()["id"]

    # 只改总时长（深睡留空 → 前端不带 deep_h）
    put = await client.put(
        f"/api/health-profile-v3/{pid}/metric/sleep/{rid}",
        headers=h, json={"value": {"duration_h": 6.0}},
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert float(body["value"]["duration_h"]) == 6.0
    # 后端 merge：未传的 deep_h 保留
    assert float(body["value"]["deep_h"]) == 2.0


# ─── 前端静态断言公共工具 ────────────────────────────────────────────────────

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(rel_path: str) -> str:
    path = os.path.join(_REPO_ROOT, rel_path)
    if not os.path.exists(path):
        pytest.skip(f"源码文件不存在（容器内无该端源码）：{rel_path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


_HISTORY_PAGE = "h5-web/src/app/health-metric/[type]/history/page.tsx"


# ─── 前端 TC-5：① 列表格式化纳入睡眠双值 ────────────────────────────────────

def test_h5_history_formats_sleep_value():
    src = _read(_HISTORY_PAGE)
    # formatMetricValue 中对 sleep 分支处理
    assert "metricType === 'sleep'" in src
    assert "duration_h" in src and "deep_h" in src
    # 显示「X 小时」+「深睡 Yh」
    assert "小时" in src and "深睡" in src
    assert "formatSleepHours" in src


# ─── 前端 TC-6：② 状态档位配置含睡眠四档 ───────────────────────────────────

def test_h5_history_status_options_has_sleep():
    src = _read(_HISTORY_PAGE)
    # STATUS_OPTIONS_BY_TYPE.sleep 四档
    assert "'睡眠不足'" in src or "睡眠不足" in src
    assert "睡眠偏少" in src and "睡眠充足" in src and "睡眠偏多" in src
    assert "insufficient" in src and "less" in src and "enough" in src and "more" in src


# ─── 前端 TC-7：③ 编辑弹窗字段配置含睡眠 ────────────────────────────────────

def test_h5_history_edit_meta_has_sleep():
    src = _read(_HISTORY_PAGE)
    # EDIT_META_BY_TYPE.sleep：睡眠时长 + 深睡时长（选填）
    assert "睡眠时长" in src
    assert "深睡时长" in src
    # 选填标记
    assert "optional" in src


# ─── 前端 TC-8：④ 编辑保存 value 拼装含睡眠双值 ─────────────────────────────

def test_h5_history_save_assembles_sleep_value():
    src = _read(_HISTORY_PAGE)
    # 保存时按 { duration_h, deep_h? } 组装
    assert "value = { duration_h:" in src or "value = { duration_h " in src or "duration_h: nums['duration_h']" in src
    assert "value.deep_h = nums['deep_h']" in src
    # 选填留空时跳过校验
    assert "fd.optional" in src
