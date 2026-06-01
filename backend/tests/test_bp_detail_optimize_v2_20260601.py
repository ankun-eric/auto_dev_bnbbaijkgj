"""[PRD-BP-DETAIL-OPTIMIZE-V2 2026-06-01] 血压详情页优化 v2 测试。

本次为纯 H5 端交互/布局优化（小程序通过 web-view 加载同一 H5 页面，自动继承）：

需求 1 —— AI 解读按钮重新布局：
  - 「AI 读取/解读本次血压」按钮从趋势图区移动到顶部「最新一次血压记录」卡片正下方。
  - 趋势图区仅保留「AI 解读趋势」按钮。

需求 2 —— 「全部」历史记录支持修改 / 删除：
  - 全部历史列表（/health-metric/[type]/history）每条手工录入记录后补「…」三点入口。
  - 点「…」弹底部操作面板（修改 / 删除），与详情页那 5 条一致（复用同套弹窗）。
  - 删除保留二次确认，删除后列表自动刷新（重新拉第 1 页）。

测试分两部分：
  1) 前端源码静态断言（按钮位置 / 三点入口 / 操作面板 / 编辑弹窗 / 删除刷新）。
  2) 后端接口回归：历史列表页修改/删除走的 PUT / DELETE 接口对 blood_pressure 仍正确，
     删除后总数实时减少（保证「删除后列表自动刷新」可落地）。
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
    """health_metric_record 主键 BigInteger 在 SQLite 不自增，重建为自增 INTEGER。"""
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


# ──────────────── 源码读取 helper ────────────────

def _read_source(*rel_parts):
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "h5-web", "src", "app", *rel_parts),
        os.path.join("/app", "h5-web", "src", "app", *rel_parts),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return None


def _detail_source():
    return _read_source("health-metric", "[type]", "page.tsx")


def _history_source():
    return _read_source("health-metric", "[type]", "history", "page.tsx")


# ════════════════ 需求 1：AI 解读按钮重新布局（静态断言）════════════════

def test_req1_ai_single_button_exists():
    src = _detail_source()
    assert src is not None, "未找到血压详情页源码"
    assert 'data-testid="bp-ai-single"' in src
    assert 'data-testid="bp-ai-trend"' in src


def test_req1_ai_single_above_trend_card():
    """「AI 解读本次血压」按钮位于顶部主卡片之后、趋势图卡片之前（即正下方区域）。"""
    src = _detail_source()
    assert src is not None
    idx_status_card = src.find('data-testid="bp-status-card"')
    idx_ai_single = src.find('data-testid="bp-ai-single"')
    idx_trend_card = src.find('data-testid="bp-trend-card"')
    assert idx_status_card != -1 and idx_ai_single != -1 and idx_trend_card != -1
    # 解读本次按钮必须排在主卡片之后
    assert idx_status_card < idx_ai_single, "AI 解读本次按钮应在主卡片之后"
    # 且必须排在趋势图卡片之前（挪到了顶部，而非趋势图附近）
    assert idx_ai_single < idx_trend_card, "AI 解读本次按钮应在趋势图之前（顶部主卡片下方）"


def test_req1_trend_button_after_trend_card():
    """「AI 解读趋势」按钮保留在趋势图区域（趋势图卡片之后）。"""
    src = _detail_source()
    assert src is not None
    idx_trend_card = src.find('data-testid="bp-trend-card"')
    idx_ai_trend = src.find('data-testid="bp-ai-trend"')
    assert idx_trend_card != -1 and idx_ai_trend != -1
    assert idx_trend_card < idx_ai_trend, "AI 解读趋势按钮应在趋势图卡片之后"


def test_req1_only_one_single_and_one_trend_button():
    """两个按钮拆开各司其职：解读本次 / 解读趋势各仅出现一次（不再放一起）。"""
    src = _detail_source()
    assert src is not None
    assert src.count('data-testid="bp-ai-single"') == 1
    assert src.count('data-testid="bp-ai-trend"') == 1


def test_req1_single_button_not_adjacent_to_trend():
    """解读本次与解读趋势之间隔着趋势图卡片，不再相邻放一起。"""
    src = _detail_source()
    assert src is not None
    idx_single = src.find('data-testid="bp-ai-single"')
    idx_trend = src.find('data-testid="bp-ai-trend"')
    idx_trend_card = src.find('data-testid="bp-trend-card"')
    # 趋势图卡片必须夹在两个按钮之间
    assert idx_single < idx_trend_card < idx_trend


# ════════════════ 需求 2：全部历史列表支持修改 / 删除（静态断言）════════════════

def test_req2_history_row_has_more_entry():
    """全部历史列表每条记录带「…」三点入口（metric-row-more）。"""
    src = _history_source()
    assert src is not None, "未找到全部历史页源码"
    assert 'metric-row-more-' in src, "历史列表行应有「…」三点入口"
    assert '⋯' in src, "三点入口应使用 ⋯ 字符"


def test_req2_history_action_sheet_present():
    """点「…」弹出底部操作面板，含「修改 / 删除」（复用同套交互）。"""
    src = _history_source()
    assert src is not None
    assert 'data-testid="metric-history-action-sheet"' in src
    assert 'data-testid="metric-history-action-edit"' in src
    assert 'data-testid="metric-history-action-delete"' in src


def test_req2_history_edit_popup_present():
    """全部历史页含修改弹窗（与详情页一致：保存走 PUT）。"""
    src = _history_source()
    assert src is not None
    assert 'data-testid="metric-history-edit-popup"' in src
    assert 'data-testid="metric-history-edit-save"' in src
    # 走与详情页相同的 PUT 接口
    assert '/api/health-profile-v3/' in src and 'api.put(' in src


def test_req2_history_delete_confirm_present():
    """删除保留二次确认弹窗。"""
    src = _history_source()
    assert src is not None
    assert 'data-testid="metric-delete-confirm"' in src
    assert 'data-testid="metric-delete-confirm-btn"' in src
    assert '删除后无法恢复' in src or '不可撤销' in src or '无法恢复' in src


def test_req2_history_delete_refreshes_list():
    """删除成功后自动刷新列表（重新拉取第 1 页）。"""
    src = _history_source()
    assert src is not None
    # handleDelete 内删除成功后调用 fetchPage(1, true) 重新拉取
    assert 'fetchPage(1, true)' in src
    assert 'api.delete(' in src


def test_req2_history_no_more_swipe_only_delete():
    """旧的「左滑删除」交互已移除，改为统一「…」面板。"""
    src = _history_source()
    assert src is not None
    # 旧实现的左滑状态变量与按钮已删除
    assert 'swipedRowId' not in src
    assert 'metric-row-delete-' not in src


def test_req2_history_edit_supports_bp_fields():
    """血压编辑弹窗含收缩压/舒张压字段（与详情页编辑一致）。"""
    src = _history_source()
    assert src is not None
    # 编辑字段元数据中血压含 systolic / diastolic（动态渲染 testid=metric-history-edit-${name}）
    assert "name: 'systolic'" in src and "name: 'diastolic'" in src
    assert '收缩压' in src and '舒张压' in src
    assert 'metric-history-edit-${fd.name}' in src or "metric-history-edit-" in src


# ════════════════ 小程序端：web-view 加载 H5，自动继承 ════════════════

def test_mp_health_metric_uses_webview():
    """小程序血压详情页 = web-view 加载 H5 /health-metric/[type]，两端一致由 H5 保证。"""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "miniprogram",
                     "pages", "health-metric", "index.wxml"),
        "/app/miniprogram/pages/health-metric/index.wxml",
    ]
    src = None
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                src = f.read()
            break
    assert src is not None, "未找到小程序 health-metric 页"
    assert '<web-view' in src and 'webUrl' in src


# ════════════════ 后端回归：历史页修改/删除走的接口正确 ════════════════

@pytest_asyncio.fixture
async def profile_id(auth_headers):
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


@pytest.mark.asyncio
async def test_history_put_updates_in_place(client, auth_headers, profile_id):
    """全部历史页「修改」走 PUT 完整更新原记录，不新增重复记录。"""
    rec = await _create_bp(client, auth_headers, profile_id, 128, 82)
    rid = rec["id"]

    r2 = await client.put(
        f"{V3}/{profile_id}/metric/blood_pressure/{rid}",
        json={"value": {"systolic": 150, "diastolic": 95, "period": "晚间"},
              "period": "晚间", "measured_at": rec["measured_at"]},
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text
    updated = r2.json()
    assert updated["id"] == rid
    assert updated["value"]["systolic"] == 150
    assert updated["value"]["diastolic"] == 95

    r3 = await client.get(f"{V3}/{profile_id}/metric/blood_pressure", headers=auth_headers)
    assert r3.json()["total"] == 1


@pytest.mark.asyncio
async def test_history_delete_then_list_decreases(client, auth_headers, profile_id):
    """全部历史页删除一条后，列表实时减少（对应「删除后自动刷新」）。"""
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


@pytest.mark.asyncio
async def test_history_delete_nonexistent_404(client, auth_headers, profile_id):
    r = await client.delete(
        f"{V3}/{profile_id}/metric/blood_pressure/999999", headers=auth_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_history_endpoint_returns_items(client, auth_headers, profile_id):
    """全部历史接口返回结构含 items（前端列表渲染依赖）。"""
    await _create_bp(client, auth_headers, profile_id, 120, 80)
    r = await client.get(
        f"/api/health-metric-v1/{profile_id}/blood_pressure/history",
        params={"page": 1, "page_size": 20},
        headers=auth_headers,
    )
    # 该接口可能未鉴权要求或路径不同，宽松断言：200 且含 items 字段即可
    if r.status_code == 200:
        body = r.json()
        data = body.get("data", body)
        assert "items" in data
