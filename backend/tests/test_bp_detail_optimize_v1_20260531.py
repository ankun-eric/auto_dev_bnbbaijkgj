"""[PRD-BP-DETAIL-OPTIMIZE-V1 2026-05-31] 血压详情页优化（含血糖同步）后端契约测试。

本次优化主要为 H5 端交互（AI 解读按钮始终显示 + 无记录 toast、历史记录「...」底部
操作面板含「修改 / 删除」），后端复用既有 `/api/health-profile-v3/{profileId}/metric/{type}`
的 PUT / DELETE 接口，不新增后端代码。本测试用于确认这些接口对 blood_pressure 类型
按需求行为正确，保证 H5 端「修改走 PUT 完整更新原记录、删除物理删除」可落地。

覆盖验收点（后端可验证部分）：
- AC-06：血压「修改」走 PUT 完整更新原记录，不新增重复记录
- AC-07/AC-08：血压「删除」走 DELETE 物理删除，列表实时减少
- 越权 / 不存在校验：他人 profile 403、不存在记录 404
- 血糖同步：blood_glucose 的 PUT / DELETE 行为一致（AC-10 共用同一套接口）
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.models.models import User, HealthProfile

V3 = "/api/health-profile-v3"


@pytest_asyncio.fixture(autouse=True)
async def _ensure_metric_table():
    """health_metric_record 的主键为 BigInteger，在 SQLite 下不会自增，
    导致 INSERT 报 NOT NULL。重建为 INTEGER PRIMARY KEY AUTOINCREMENT（对齐血糖测试做法）。"""
    from tests.conftest import test_engine

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

# H5 详情页源码路径（容器内 / 本地两种布局兼容）
_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "..", "h5-web", "src", "app",
                 "health-metric", "[type]", "page.tsx"),
    "/app/h5-web/src/app/health-metric/[type]/page.tsx",
]


def _read_h5_source():
    for p in _CANDIDATES:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return None


@pytest_asyncio.fixture
async def profile_id(auth_headers):
    """为测试用户创建一个 health_profile，返回其 id。"""
    from tests.conftest import test_session

    async with test_session() as session:
        user = (await session.execute(
            select(User).where(User.phone == "13900000001")
        )).scalar_one()
        prof = HealthProfile(user_id=user.id, name="测试档案")
        session.add(prof)
        await session.commit()
        await session.refresh(prof)
        return prof.id


async def _create_bp(client, headers, profile_id, systolic, diastolic, period="晨起"):
    r = await client.post(
        f"{V3}/{profile_id}/metric/blood_pressure",
        json={"value": {"systolic": systolic, "diastolic": diastolic, "period": period},
              "source": "manual"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ──────────────── AC-06：PUT 完整更新原记录，不新增 ────────────────

@pytest.mark.asyncio
async def test_ac06_bp_put_updates_in_place(client, auth_headers, profile_id):
    rec = await _create_bp(client, auth_headers, profile_id, 128, 82)
    rid = rec["id"]

    r2 = await client.put(
        f"{V3}/{profile_id}/metric/blood_pressure/{rid}",
        json={"value": {"systolic": 150, "diastolic": 95, "period": "晚间"},
              "measured_at": rec["measured_at"]},
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text
    updated = r2.json()
    assert updated["id"] == rid
    assert updated["value"]["systolic"] == 150
    assert updated["value"]["diastolic"] == 95
    assert updated["value"]["period"] == "晚间"

    # 列表只有 1 条（未新增重复记录）
    r3 = await client.get(f"{V3}/{profile_id}/metric/blood_pressure", headers=auth_headers)
    assert r3.status_code == 200
    assert r3.json()["total"] == 1


# ──────────────── AC-07 / AC-08：DELETE 物理删除 ────────────────

@pytest.mark.asyncio
async def test_ac08_bp_delete_removes_record(client, auth_headers, profile_id):
    rec = await _create_bp(client, auth_headers, profile_id, 120, 80)
    rid = rec["id"]

    r2 = await client.delete(
        f"{V3}/{profile_id}/metric/blood_pressure/{rid}", headers=auth_headers
    )
    assert r2.status_code == 200, r2.text

    r3 = await client.get(f"{V3}/{profile_id}/metric/blood_pressure", headers=auth_headers)
    assert r3.json()["total"] == 0


@pytest.mark.asyncio
async def test_bp_delete_then_list_reflects_realtime(client, auth_headers, profile_id):
    """多条记录删除其中一条，列表实时反映剩余条数。"""
    await _create_bp(client, auth_headers, profile_id, 118, 78)
    rec2 = await _create_bp(client, auth_headers, profile_id, 145, 92)
    await _create_bp(client, auth_headers, profile_id, 130, 85)

    r0 = await client.get(f"{V3}/{profile_id}/metric/blood_pressure", headers=auth_headers)
    assert r0.json()["total"] == 3

    rd = await client.delete(
        f"{V3}/{profile_id}/metric/blood_pressure/{rec2['id']}", headers=auth_headers
    )
    assert rd.status_code == 200

    r1 = await client.get(f"{V3}/{profile_id}/metric/blood_pressure", headers=auth_headers)
    assert r1.json()["total"] == 2


# ──────────────── 校验：不存在 / 越权 ────────────────

@pytest.mark.asyncio
async def test_bp_put_nonexistent_record_404(client, auth_headers, profile_id):
    r = await client.put(
        f"{V3}/{profile_id}/metric/blood_pressure/999999",
        json={"value": {"systolic": 120, "diastolic": 80}},
        headers=auth_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_bp_delete_nonexistent_record_404(client, auth_headers, profile_id):
    r = await client.delete(
        f"{V3}/{profile_id}/metric/blood_pressure/999999", headers=auth_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_bp_put_other_user_profile_403(client, auth_headers, profile_id):
    """他人 profile 的记录无权修改 → 403。"""
    from tests.conftest import test_session
    from app.core.security import get_password_hash

    async with test_session() as session:
        other = User(phone="13900000099", password_hash=get_password_hash("x"),
                     nickname="他人")
        session.add(other)
        await session.commit()
        await session.refresh(other)
        other_prof = HealthProfile(user_id=other.id, name="他人档案")
        session.add(other_prof)
        await session.commit()
        await session.refresh(other_prof)
        other_pid = other_prof.id

    r = await client.put(
        f"{V3}/{other_pid}/metric/blood_pressure/1",
        json={"value": {"systolic": 120, "diastolic": 80}},
        headers=auth_headers,
    )
    assert r.status_code == 403


# ──────────────── 血糖同步：PUT / DELETE 行为一致（AC-10） ────────────────

@pytest.mark.asyncio
async def test_ac10_glucose_put_delete_consistent(client, auth_headers, profile_id):
    """血糖记录 PUT 完整更新 + DELETE 删除，行为与血压一致。"""
    r = await client.post(
        f"{V3}/{profile_id}/metric/blood_glucose",
        json={"value": {"value": 6.5, "period": "fasting"}, "source": "manual"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    rid = r.json()["id"]

    r2 = await client.put(
        f"{V3}/{profile_id}/metric/blood_glucose/{rid}",
        json={"value": 8.0, "period": "after_meal_2h"},
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["value"]["value"] == 8.0
    assert r2.json()["value"]["period"] == "after_meal_2h"

    rg = await client.get(f"{V3}/{profile_id}/metric/blood_glucose", headers=auth_headers)
    assert rg.json()["total"] == 1

    rd = await client.delete(
        f"{V3}/{profile_id}/metric/blood_glucose/{rid}", headers=auth_headers
    )
    assert rd.status_code == 200
    rg2 = await client.get(f"{V3}/{profile_id}/metric/blood_glucose", headers=auth_headers)
    assert rg2.json()["total"] == 0


# ──────────────── H5 源码静态断言（前端交互标记） ────────────────

class TestH5SourceMarkers:
    """对 H5 详情页源码做静态断言，验证本次新增/改动的交互标记存在。
    若源码不在当前环境（如纯后端容器内运行），跳过。"""

    def test_bp_ai_single_always_shown_and_toast_guard(self):
        src = _read_h5_source()
        if src is None:
            pytest.skip("H5 源码不可见，跳过静态断言")
        # AC-01：AI 解读本次血压按钮始终存在
        assert 'data-testid="bp-ai-single"' in src
        # AC-02：无记录时 toast 文案，且 return 不进入解读流程
        assert "暂无血压记录，请先录入一次再点击解读。" in src
        assert "if (mode === 'single' && !latest?.id)" in src

    def test_bp_history_more_entry_and_action_sheet(self):
        src = _read_h5_source()
        if src is None:
            pytest.skip("H5 源码不可见，跳过静态断言")
        # AC-04：血压历史「...」入口
        assert "bp-row-more-" in src
        # AC-05/AC-11：共用底部操作面板组件
        assert "MetricActionSheet" in src
        assert 'testid="bp-action-sheet"' in src
        # AC-06：血压编辑 PUT
        assert 'data-testid="bp-edit-save"' in src
        assert "/metric/blood_pressure/${editRecord.id}" in src
        # AC-07：二次确认文案
        assert "确认删除这条记录？此操作不可撤销" in src
        # AC-08：删除 toast「已删除」
        assert "showToast('已删除', 'success')" in src

    def test_bg_history_more_entry_added(self):
        src = _read_h5_source()
        if src is None:
            pytest.skip("H5 源码不可见，跳过静态断言")
        # AC-09：血糖历史「...」入口 + 复用底部操作面板
        assert "bg-row-more-" in src
        assert 'testid="bg-action-sheet"' in src

    def test_action_sheet_has_edit_and_delete(self):
        src = _read_h5_source()
        if src is None:
            pytest.skip("H5 源码不可见，跳过静态断言")
        assert 'data-testid="metric-action-edit"' in src
        assert 'data-testid="metric-action-delete"' in src
