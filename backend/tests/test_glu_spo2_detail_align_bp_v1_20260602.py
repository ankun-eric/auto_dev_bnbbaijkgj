"""[PRD-GLU-SPO2-DETAIL-ALIGN-BP-V1 2026-06-02] 健康档案 · 血糖 / 血氧详情页向血压对齐。

覆盖端：H5 网页端 + 微信小程序（小程序详情页 = web-view 加载同一 H5 页，自动继承）。

需求：
  1) 血糖详情页：「AI 解读本次血糖」从趋势图后移到顶部主卡片正下方；
     「AI 解读趋势」保留在趋势图下方；两按钮都不删。
  2) 血氧详情页：整套照搬血压精装 6 区块（顶部大卡片 + 解读本次 + 操作按钮 + 趋势图日/周 +
     解读趋势 + 历史「...」）。状态胶囊三档：≥95 正常 / 90~94 偏低 / <90 偏低明显。
  3) 血糖 / 血氧 历史每条「...」→ 修改（PUT 完整更新）/ 删除（二次确认）。

测试分两部分：
  1) 前端源码静态断言（H5 .tsx + spo2-level.ts + 小程序 web-view）。
  2) 后端接口回归：血氧记录 增 / 改（PUT）/ 删（DELETE）走既有 health-profile-v3 接口，
     保证详情页历史可改可删可落地；血氧通用 AI 接口可用。
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.models.models import User, HealthProfile

V3 = "/api/health-profile-v3"
METRIC_V1 = "/api/health-metric-v1"


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

def _read(*rel_parts):
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", *rel_parts),
        os.path.join("/app", *rel_parts),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return None


def _detail_src():
    return _read("h5-web", "src", "app", "health-metric", "[type]", "page.tsx")


def _spo2_level_src():
    return _read("h5-web", "src", "lib", "spo2-level.ts")


def _mp_metric_wxml():
    return _read("miniprogram", "pages", "health-metric", "index.wxml")


def _detail_or_skip():
    src = _detail_src()
    if src is None:
        pytest.skip("详情页源码不在当前环境（backend 容器内无 h5-web 源码），跳过静态断言")
    return src


# ════════════════ 一、需求1：血糖 AI 解读本次按钮挪位 ════════════════

def test_h5_glucose_ai_single_moved_below_main_card():
    """血糖「AI 解读本次血糖」移到顶部主卡片正下方（在操作按钮 bg-action-row 之前）。"""
    src = _detail_or_skip()
    assert 'data-testid="bg-ai-single"' in src
    assert "AI 解读本次血糖" in src
    idx_single = src.find('data-testid="bg-ai-single"')
    idx_action_row = src.find('data-testid="bg-action-row"')
    idx_trend_card = src.find('data-testid="bg-trend-card"')
    # 解读本次 在 操作按钮行 之前，操作按钮行 在 趋势卡 之前
    assert idx_single < idx_action_row < idx_trend_card


def test_h5_glucose_ai_trend_below_trend_chart():
    """血糖「AI 解读趋势」保留在趋势图下方（trend-card 之后），且解读本次在其前面。"""
    src = _detail_or_skip()
    assert 'data-testid="bg-ai-trend"' in src
    idx_single = src.find('data-testid="bg-ai-single"')
    idx_trend_card = src.find('data-testid="bg-trend-card"')
    idx_trend = src.find('data-testid="bg-ai-trend"')
    assert idx_single < idx_trend_card < idx_trend


def test_h5_glucose_both_ai_buttons_kept():
    """两个 AI 按钮都保留，一个都不删。"""
    src = _detail_or_skip()
    assert "AI 解读本次血糖" in src
    assert "AI 解读趋势" in src


def test_h5_glucose_history_more_action_exists():
    """血糖历史每条「...」入口 + 操作面板 + 编辑（PUT）+ 删除二次确认 已具备。"""
    src = _detail_or_skip()
    assert 'bg-row-more-${r.id}' in src
    assert "/metric/blood_glucose/" in src  # PUT/DELETE 走既有接口


# ════════════════ 二、需求2：血氧详情页整套对齐血压 ════════════════

def test_spo2_level_three_tier_rule():
    """血氧档位规则：≥95 正常 / 90~94 偏低 / <90 偏低明显。"""
    src = _spo2_level_src()
    assert src is not None, "未找到 spo2-level.ts"
    assert "value >= 95" in src and "value >= 90" in src
    assert "'正常'" in src and "'偏低'" in src and "'偏低明显'" in src
    # 颜色档：正常蓝 / 偏低黄 / 偏低明显橙
    assert "'blue'" in src and "'yellow'" in src and "'orange'" in src


def test_h5_spo2_dedicated_branch():
    """详情页对 spo2 走专属 Spo2Page 精装布局。"""
    src = _detail_or_skip()
    assert "metricType === 'spo2'" in src
    assert "Spo2Page" in src
    assert "function Spo2Page" in src


def test_h5_spo2_six_blocks_order():
    """血氧 6 区块顺序与血压一致：
    主卡片 → 解读本次 → 操作按钮 → 趋势图 → 解读趋势 → 历史记录。"""
    src = _detail_or_skip()
    idx_card = src.find('data-testid="spo2-status-card"')
    idx_single = src.find('data-testid="spo2-ai-single"')
    idx_action = src.find('data-testid="spo2-action-row"')
    idx_trend = src.find('data-testid="spo2-trend-card"')
    idx_aitrend = src.find('data-testid="spo2-ai-trend"')
    idx_history = src.find('data-testid="spo2-history-all-entry"')
    for v in (idx_card, idx_single, idx_action, idx_trend, idx_aitrend, idx_history):
        assert v != -1
    assert idx_card < idx_single < idx_action < idx_trend < idx_aitrend < idx_history


def test_h5_spo2_status_card_value_unit_capsule():
    """顶部大卡片：超大数值 + 单位 % + 时间·来源 + 状态胶囊（按档位变色底卡）。"""
    src = _detail_or_skip()
    assert 'data-testid="spo2-main-value"' in src
    assert 'data-testid="spo2-sync-text"' in src
    assert 'data-testid="spo2-capsule"' in src
    assert "palette.cardBg" in src
    assert "judgeSpo2" in src and "getSpo2Palette" in src


def test_h5_spo2_dual_ai_buttons():
    """双 AI 按钮：解读本次血氧（主卡片下方）+ 解读趋势（趋势图后）。"""
    src = _detail_or_skip()
    assert "AI 解读本次血氧" in src
    assert 'data-testid="spo2-ai-single"' in src
    assert 'data-testid="spo2-ai-trend"' in src


def test_h5_spo2_ai_reuses_metric_api():
    """血氧 AI 解读复用通用指标接口（spo2）。"""
    src = _detail_or_skip()
    assert "/spo2/ai-explain-single" in src
    assert "/spo2/ai-explain-trend" in src


def test_h5_spo2_trend_day_week_switch():
    """血氧趋势图支持 日/周 切换 + 数据点弹窗。"""
    src = _detail_or_skip()
    assert 'data-testid="spo2-trend-card"' in src
    assert 'spo2-range-${opt.key}' in src
    assert "key: 'day'" in src and "key: 'week'" in src
    assert 'data-testid="spo2-trend-svg"' in src
    assert 'data-testid="spo2-point-popup"' in src
    assert "Spo2TrendChart" in src


def test_h5_spo2_blue_theme_and_no_data():
    """整体主题与血压一致（#F4F7FB + #0EA5E9），无数据时显示「—」并隐藏胶囊。"""
    src = _detail_or_skip()
    assert "data-testid=\"spo2-tab-page\"" in src
    assert "#0EA5E9" in src
    assert "尚无血氧记录" in src
    assert "judgement && (" in src


# ════════════════ 三、需求3：血氧历史「...」修改/删除 ════════════════

def test_h5_spo2_history_more_edit_delete():
    """血氧历史每条「...」→ 操作面板 → 修改（PUT 完整更新）/ 删除（二次确认）。"""
    src = _detail_or_skip()
    assert 'spo2-row-more-${r.id}' in src
    assert 'testid="spo2-action-sheet"' in src
    assert 'data-testid="spo2-edit-popup"' in src
    assert 'data-testid="spo2-edit-save"' in src
    assert 'data-testid="spo2-delete-confirm"' in src
    assert 'data-testid="spo2-delete-confirm-btn"' in src
    # 修改走 PUT、删除走 DELETE，路径含 /metric/spo2/
    assert "/metric/spo2/" in src
    assert "api.put(" in src and "api.delete(" in src


def test_h5_spo2_delete_double_confirm_text():
    """删除二次确认文案 + 已删除 toast。"""
    src = _detail_or_skip()
    assert "确认删除这条记录？此操作不可撤销。" in src
    assert "已删除" in src


# ════════════════ 四、小程序两端 web-view 继承 ════════════════

def test_mp_detail_webview_inherits_h5():
    """小程序血糖/血氧详情页 = web-view 加载 H5，自动继承精装详情页与历史操作。"""
    src = _mp_metric_wxml()
    if src is None:
        pytest.skip("backend 容器内无 miniprogram 源码，跳过")
    assert "<web-view" in src and "webUrl" in src


# ════════════════ 五、后端回归：血氧 增/改/删 走既有接口 ════════════════

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


async def _create_spo2(client, headers, profile_id, value, period="晨起"):
    r = await client.post(
        f"{V3}/{profile_id}/metric/spo2",
        json={"value": {"value": value, "period": period}, "source": "manual"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_spo2_create_and_list(client, auth_headers, profile_id):
    rec = await _create_spo2(client, auth_headers, profile_id, 98)
    assert rec["value"]["value"] == 98
    r = await client.get(f"{V3}/{profile_id}/metric/spo2", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_spo2_put_updates_in_place(client, auth_headers, profile_id):
    """详情页/历史页「修改」走 PUT 完整更新原记录，不新增重复记录（AC-6）。"""
    rec = await _create_spo2(client, auth_headers, profile_id, 98)
    rid = rec["id"]
    r2 = await client.put(
        f"{V3}/{profile_id}/metric/spo2/{rid}",
        json={"value": {"value": 92, "period": "午间"}, "measured_at": rec["measured_at"]},
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text
    updated = r2.json()
    assert updated["id"] == rid
    assert updated["value"]["value"] == 92
    r3 = await client.get(f"{V3}/{profile_id}/metric/spo2", headers=auth_headers)
    assert r3.json()["total"] == 1  # 仍只有一条，未新增重复


@pytest.mark.asyncio
async def test_spo2_delete_then_list_decreases(client, auth_headers, profile_id):
    """删除走 DELETE，列表条数减少（AC-7）。"""
    await _create_spo2(client, auth_headers, profile_id, 88)
    rec2 = await _create_spo2(client, auth_headers, profile_id, 93)
    await _create_spo2(client, auth_headers, profile_id, 99)
    r0 = await client.get(f"{V3}/{profile_id}/metric/spo2", headers=auth_headers)
    assert r0.json()["total"] == 3
    rd = await client.delete(
        f"{V3}/{profile_id}/metric/spo2/{rec2['id']}", headers=auth_headers
    )
    assert rd.status_code == 200
    r1 = await client.get(f"{V3}/{profile_id}/metric/spo2", headers=auth_headers)
    assert r1.json()["total"] == 2


@pytest.mark.asyncio
async def test_spo2_delete_nonexistent_404(client, auth_headers, profile_id):
    r = await client.delete(
        f"{V3}/{profile_id}/metric/spo2/999999", headers=auth_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_spo2_ai_explain_single_available(client, auth_headers, profile_id):
    """血氧通用 AI 解读（单次）接口可用（详情页「AI 解读本次血氧」依赖）。"""
    rec = await _create_spo2(client, auth_headers, profile_id, 91)
    r = await client.post(
        f"{METRIC_V1}/{profile_id}/spo2/ai-explain-single",
        json={"record_id": rec["id"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    content = (body.get("data") or body).get("content") if isinstance(body, dict) else None
    assert content, body


@pytest.mark.asyncio
async def test_spo2_ai_explain_trend_available(client, auth_headers, profile_id):
    """血氧通用 AI 解读（趋势）接口可用（详情页「AI 解读趋势」依赖）。"""
    await _create_spo2(client, auth_headers, profile_id, 97)
    await _create_spo2(client, auth_headers, profile_id, 96)
    r = await client.post(
        f"{METRIC_V1}/{profile_id}/spo2/ai-explain-trend",
        json={"range": "7d"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
