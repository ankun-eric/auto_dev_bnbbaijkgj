"""[PRD-HR-ALIGN-BP-V1 2026-06-01] 健康档案「心率」全面对齐「血压」（H5 + 小程序，全量统一）。

本次将心率模块（小卡片 + 详情页）改造为与血压一致的「精装」样式，并补齐小程序两端
（血压 / 血糖小卡片也一并胶囊化，达到全端一致）。

范围（端）：
  - H5：心率小卡片胶囊化（health-profile）、心率详情页精装化（health-metric/[type]）。
  - 微信小程序：health-profile 小卡片（血压/心率/血糖）胶囊化 + 时间·来源行；
    详情页 = web-view 加载同一 H5 页，自动继承精装详情。

测试分两部分：
  1) 前端源码静态断言（H5 .tsx + 小程序 .wxml/.js/.wxss）。
  2) 后端接口回归：心率记录的 增 / 改（PUT）/ 删（DELETE）走既有 health-profile-v3 接口正确，
     保证详情页「历史可改可删」可落地。
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


def _profile_src():
    return _read("h5-web", "src", "app", "health-profile", "page.tsx")


def _hr_level_src():
    return _read("h5-web", "src", "lib", "heart-rate-level.ts")


def _mp_profile_wxml():
    return _read("miniprogram", "pages", "health-profile", "index.wxml")


def _mp_profile_js():
    return _read("miniprogram", "pages", "health-profile", "index.js")


def _mp_profile_wxss():
    return _read("miniprogram", "pages", "health-profile", "index.wxss")


def _mp_metric_wxml():
    return _read("miniprogram", "pages", "health-metric", "index.wxml")


# ════════════════ 一、心率判定规则文件（复用既有 + 扩展色板）════════════════

def test_hr_level_rule_60_100():
    src = _hr_level_src()
    assert src is not None, "未找到 heart-rate-level.ts"
    # 三档：偏慢 / 正常 / 偏快，正常区间 60–100
    assert "'偏慢'" in src and "'正常'" in src and "'偏快'" in src
    assert "value < 60" in src and "value <= 100" in src


def test_hr_palette_extended_for_精装():
    """色板扩展出 cardBg / text / border（用于详情页主卡片按档位变色，对齐血压）。"""
    src = _hr_level_src()
    assert src is not None
    assert "cardBg" in src and "border" in src
    # 正常蓝、偏慢偏快橙
    assert "#3B82F6" in src  # blue capsule
    assert "#F97316" in src  # orange capsule


# ════════════════ 二、H5 心率详情页精装化（对齐血压）════════════════

def test_h5_hr_detail_dedicated_branch():
    """详情页对 heart_rate 走专属 HeartRatePage 精装布局。"""
    src = _detail_src()
    assert src is not None
    assert "metricType === 'heart_rate'" in src
    assert "HeartRatePage" in src
    assert "function HeartRatePage" in src


def test_h5_hr_detail_status_card():
    """顶部主卡片：大号居中数值 + 居中彩色胶囊 + 按档位变色底卡。"""
    src = _detail_src()
    assert 'data-testid="hr-status-card"' in src
    assert 'data-testid="hr-main-value"' in src
    assert 'data-testid="hr-capsule"' in src
    # 底卡背景取色板 cardBg（按档位变色）
    assert "palette.cardBg" in src


def test_h5_hr_detail_dual_ai_buttons():
    """双 AI 按钮：解读本次心率 + 解读趋势，本次按钮在主卡片下方、趋势按钮在趋势图后。"""
    src = _detail_src()
    assert 'data-testid="hr-ai-single"' in src
    assert 'data-testid="hr-ai-trend"' in src
    assert "AI 解读本次心率" in src
    idx_single = src.find('data-testid="hr-ai-single"')
    idx_trend_card = src.find('data-testid="hr-trend-card"')
    idx_trend = src.find('data-testid="hr-ai-trend"')
    assert idx_single < idx_trend_card < idx_trend


def test_h5_hr_detail_ai_reuses_metric_api():
    """AI 解读复用通用指标接口框架（指标名替换为 heart_rate）。"""
    src = _detail_src()
    assert "/heart_rate/ai-explain-single" in src
    assert "/heart_rate/ai-explain-trend" in src


def test_h5_hr_detail_trend_day_week_point_refline():
    """趋势图支持 日/周 切换 + 点击数据点弹窗 + 正常参考线（60/100）。"""
    src = _detail_src()
    assert 'data-testid="hr-trend-card"' in src
    assert 'data-testid="hr-range-day"' in src and 'data-testid="hr-range-week"' in src
    assert 'data-testid="hr-trend-svg"' in src
    assert 'data-testid="hr-point-popup"' in src
    assert "HrTrendChart" in src
    # 参考线 60 / 100
    assert "y: 60" in src and "y: 100" in src


def test_h5_hr_detail_history_editable_deletable():
    """历史记录每条可编辑可删除，带档位配色。"""
    src = _detail_src()
    assert 'data-testid="hr-row-more-' in src      # 三点入口
    assert 'data-testid="hr-action-sheet"' in src  # 操作面板（复用 MetricActionSheet）
    assert 'data-testid="hr-edit-popup"' in src
    assert 'data-testid="hr-edit-save"' in src
    assert 'data-testid="hr-delete-confirm"' in src
    assert 'data-testid="hr-delete-confirm-btn"' in src
    # 走既有 PUT / DELETE 接口
    assert "/metric/heart_rate/" in src
    # 历史行档位配色
    assert "getHrPalette" in src and "judgeHeartRate" in src


def test_h5_hr_detail_blue_theme():
    """整体主题浅蓝灰底 + 蓝色系（与血压同套）。"""
    src = _detail_src()
    # 心率页背景与血压一致 #F4F7FB
    assert "background: '#F4F7FB'" in src
    # 蓝色主色 #0EA5E9
    assert "#0EA5E9" in src


def test_h5_hr_no_data_hides_capsule_and_time():
    """无数据时数值显示「—」，胶囊与时间·来源行隐藏（judgement 为 null 时不渲染）。"""
    src = _detail_src()
    # 主卡片胶囊只在 judgement 存在时渲染
    assert "judgement && (" in src
    # 心率详情页无数据文案
    assert "尚无心率记录" in src


# ════════════════ 三、H5 心率小卡片胶囊化（health-profile）════════════════

def test_h5_hr_mini_card_capsule():
    src = _profile_src()
    assert src is not None
    assert "c.id === 'heart_rate'" in src
    assert 'data-testid="hr-mini-capsule"' in src
    assert 'data-testid="hr-mini-time-source"' in src
    assert "judgeHeartRate" in src and "getHrPalette" in src


def test_h5_hr_mini_card_hides_when_no_data():
    """无数据时不渲染胶囊 / 时间·来源行（与血压一致）。"""
    src = _profile_src()
    # 胶囊仅在 j（判定结果）存在时渲染、时间行仅在 timeSrc 存在时渲染
    assert "j && (" in src
    assert "timeSrc && (" in src


# ════════════════ 四、小程序小卡片胶囊化（血压/心率/血糖）+ 时间·来源 ════════════════

def test_mp_profile_wxml_capsule_and_time_source():
    src = _mp_profile_wxml()
    assert src is not None
    assert 'class="metric-capsule"' in src
    assert "item.capLabel" in src
    assert 'class="metric-time-source"' in src
    assert "item.timeSource" in src


def test_mp_profile_js_judging_three_metrics():
    src = _mp_profile_js()
    assert src is not None
    # 血压 / 心率 / 血糖三档判定函数
    assert "judgeBpMini" in src
    assert "judgeHrMini" in src
    assert "judgeBgMini" in src
    # 心率正常区间 60–100
    assert "v < 60" in src and "v <= 100" in src
    # 时间·来源拼装
    assert "miniTimeSource" in src
    # 单元格携带胶囊与时间·来源字段
    assert "capLabel" in src and "timeSource" in src


def test_mp_profile_wxss_capsule_style():
    src = _mp_profile_wxss()
    assert src is not None
    assert ".metric-capsule" in src
    assert ".metric-time-source" in src
    assert "999rpx" in src  # 胶囊圆角


def test_mp_detail_webview_inherits_h5():
    """小程序心率/血压/血糖详情页 = web-view 加载 H5，自动继承精装详情页。"""
    src = _mp_metric_wxml()
    assert src is not None
    assert "<web-view" in src and "webUrl" in src


# ════════════════ 五、后端回归：心率 增/改/删 走既有接口 ════════════════

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


async def _create_hr(client, headers, profile_id, value, activity="静息"):
    r = await client.post(
        f"{V3}/{profile_id}/metric/heart_rate",
        json={"value": {"value": value, "activity": activity}, "source": "manual"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_hr_create_and_list(client, auth_headers, profile_id):
    rec = await _create_hr(client, auth_headers, profile_id, 72)
    assert rec["value"]["value"] == 72
    r = await client.get(f"{V3}/{profile_id}/metric/heart_rate", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_hr_put_updates_in_place(client, auth_headers, profile_id):
    """详情页/历史页「修改」走 PUT 完整更新原记录，不新增重复记录。"""
    rec = await _create_hr(client, auth_headers, profile_id, 72)
    rid = rec["id"]
    r2 = await client.put(
        f"{V3}/{profile_id}/metric/heart_rate/{rid}",
        json={"value": {"value": 110, "activity": "运动"}, "measured_at": rec["measured_at"]},
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text
    updated = r2.json()
    assert updated["id"] == rid
    assert updated["value"]["value"] == 110
    r3 = await client.get(f"{V3}/{profile_id}/metric/heart_rate", headers=auth_headers)
    assert r3.json()["total"] == 1


@pytest.mark.asyncio
async def test_hr_delete_then_list_decreases(client, auth_headers, profile_id):
    await _create_hr(client, auth_headers, profile_id, 58)
    rec2 = await _create_hr(client, auth_headers, profile_id, 105)
    await _create_hr(client, auth_headers, profile_id, 80)
    r0 = await client.get(f"{V3}/{profile_id}/metric/heart_rate", headers=auth_headers)
    assert r0.json()["total"] == 3
    rd = await client.delete(
        f"{V3}/{profile_id}/metric/heart_rate/{rec2['id']}", headers=auth_headers
    )
    assert rd.status_code == 200
    r1 = await client.get(f"{V3}/{profile_id}/metric/heart_rate", headers=auth_headers)
    assert r1.json()["total"] == 2


@pytest.mark.asyncio
async def test_hr_delete_nonexistent_404(client, auth_headers, profile_id):
    r = await client.delete(
        f"{V3}/{profile_id}/metric/heart_rate/999999", headers=auth_headers
    )
    assert r.status_code == 404
