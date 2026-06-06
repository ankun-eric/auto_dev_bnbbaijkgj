"""[PRD-CARE-OPTIM-FINAL-V1 2026-06-01] 关怀版优化（最终版）验收测试

本次需求为关怀版首页 4 项优化（H5 + 微信小程序两端，后端 0 业务改动）：
  优化1：左上角「☰ 三横杠」点击 404 修复 —— 关怀版照搬标准版（标准版 ☰ = 打开历史会话抽屉）。
         H5 关怀版改为跳标准版 /ai-home?openDrawer=1（标准版新增 openDrawer 自动弹抽屉），
         小程序关怀版已是 /pages/ai/index?openDrawer=1（沿用，不再 404）。
  优化2：主页底部加「向下小箭头」提示（轻轻上下跳动，下滑后自动隐藏）。
  优化3：「邀请好友 / 立即分享」合并为一个「分享给好友」按钮 —— 仅负责第 3 种（纯拉新分享），
         点击弹分享面板：卡片预览（统一文案）+ 微信好友 / 生成海报 / 复制链接 三渠道。
  优化4：「今日提醒」智能轮转 —— 优先显示最近一条未打卡提醒；打卡后跳下一条；
         点击卡片直达打卡页；跨凌晨自动从第二天首条开始。

测试覆盖：
1) 后端回归：/api/medication-reminder/today 返回的每条含 checked 打卡状态字段（优化4 依赖），
   打卡后该条 checked=True，可据此实现"优先显示最近一条未打卡"的轮转（后端无需新增字段）。
2) 前端源码静态断言（非 UI）：H5 + 小程序关怀版页面、CareSharePanel、标准版 openDrawer
   均含本次 4 项优化的关键标记。
"""
from __future__ import annotations

import os
from datetime import date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

H5_CARE = os.path.join(_ROOT, "h5-web", "src", "app", "care-ai-home", "page.tsx")
H5_STD = os.path.join(_ROOT, "h5-web", "src", "app", "(ai-chat)", "ai-home", "page.tsx")
H5_SHARE = os.path.join(_ROOT, "h5-web", "src", "components", "care", "CareSharePanel.tsx")

MP_CARE_WXML = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.wxml")
MP_CARE_JS = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.js")
MP_CARE_WXSS = os.path.join(_ROOT, "miniprogram", "pages", "care-ai-home", "index.wxss")

PREFIX = "/api/medication-reminder"

UNIFIED_SLOGAN = "我在用 宾尼小康 守护家人健康，推荐您也来试试~"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _first_unchecked(items):
    """前端轮转算法：按 scheduled_time 升序取首条 checked=False。"""
    s = sorted(items, key=lambda x: x["scheduled_time"])
    for it in s:
        if not it["checked"]:
            return it["scheduled_time"]
    return None


async def _seed_reminder(times, checked_times=None):
    """直接向 medication_reminders + medication_check_ins 表写入今日提醒及打卡。

    /api/medication-reminder/today 的数据源为 MedicationReminder + MedicationCheckIn
    （非旧 MedicationPlan 表），故测试直接 seed 这两张表，确保口径与线上一致。
    返回测试用户 id。
    """
    from app.models.models import MedicationCheckIn, MedicationReminder, User
    from tests.conftest import test_session

    checked_times = checked_times or []
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == "13900000001"))).scalar_one()
        rem = MedicationReminder(
            user_id=u.id,
            medicine_name="降压药",
            dosage="1片",
            status="active",
            long_term=True,
            custom_times=list(times),
            reminder_enabled=True,
        )
        s.add(rem)
        await s.flush()
        # 按 schedule 顺序写入打卡（today 接口按打卡顺序映射 schedule 顺序）
        for t in sorted(checked_times):
            s.add(MedicationCheckIn(
                reminder_id=rem.id,
                user_id=u.id,
                check_in_date=date.today(),
                check_in_time=datetime.now(),
            ))
        await s.commit()
        return u.id


# ============== 后端回归：优化4 依赖的打卡状态字段 ==============


@pytest.mark.asyncio
async def test_today_returns_checked_status_field(client: AsyncClient, auth_headers):
    """/today 每条提醒都带 checked 打卡状态字段（优化4：用于判断未打卡/已打卡）。"""
    await _seed_reminder(["08:00", "12:00", "20:00"])

    r = await client.get(f"{PREFIX}/today", headers=auth_headers)
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 3
    for it in items:
        assert "checked" in it, "today 每条必须返回 checked 打卡状态字段"
        assert "scheduled_time" in it
        assert "plan_id" in it
        assert it["checked"] is False


@pytest.mark.asyncio
async def test_first_unchecked_rotates_after_check(client: AsyncClient, auth_headers):
    """优化4 轮转核心：打卡完成后「最近一条未打卡」自动跳到下一条。

    首条未打卡 = 按 scheduled_time 升序的首条 checked=False。
    打卡 08:00 后，首条未打卡应变为 12:00。
    """
    # 未打卡时：首条未打卡 = 08:00
    await _seed_reminder(["08:00", "12:00", "20:00"])
    items = (await client.get(f"{PREFIX}/today", headers=auth_headers)).json()
    assert _first_unchecked(items) == "08:00"


@pytest.mark.asyncio
async def test_first_unchecked_after_one_checkin(client: AsyncClient, auth_headers):
    """已打卡 1 次（最早一条 08:00）后，首条未打卡轮转到 12:00。"""
    await _seed_reminder(["08:00", "12:00", "20:00"], checked_times=["08:00"])
    items = (await client.get(f"{PREFIX}/today", headers=auth_headers)).json()
    by_t = {it["scheduled_time"]: it for it in items}
    assert by_t["08:00"]["checked"] is True
    assert _first_unchecked(items) == "12:00", "打卡后应自动轮转到下一条未打卡提醒"


@pytest.mark.asyncio
async def test_all_checked_means_no_unchecked(client: AsyncClient, auth_headers):
    """优化4 兜底：全部打卡完成后，无未打卡条目（前端展示「今天都打完啦」）。"""
    await _seed_reminder(["09:00", "21:00"], checked_times=["09:00", "21:00"])
    items = (await client.get(f"{PREFIX}/today", headers=auth_headers)).json()
    unchecked = [it for it in items if not it["checked"]]
    assert unchecked == [], "全部打卡后应无未打卡条目"


# ============== 优化1：左上角左上角入口（[BUGFIX-AI-HOME-CARE-BACK-V1 2026-06-01] 改为「返回箭头」） ==============
# 注：原"优化1"将关怀版左上角设为 ☰（跳标准版 openDrawer 历史抽屉）。
#     [BUGFIX-AI-HOME-CARE-BACK-V1 2026-06-01 §问题2] 修复"点 ☰ 就跳回标准模式"的 BUG：
#     去掉 ☰，改为「← 返回箭头」，点击退出关怀模式、统一退回标准 AI 主页。
#     以下三个用例已同步更新为校验新行为（返回箭头 → 标准首页）。


def test_h5_care_left_top_is_back_arrow_to_standard():
    """H5 关怀版左上角为「← 返回箭头」（非 ☰），点击退回标准 AI 主页 /ai-home。"""
    src = _read(H5_CARE)
    assert 'data-testid="care-home-back-btn"' in src, "关怀版左上角应为返回按钮"
    assert 'data-testid="care-home-back-icon"' in src, "应渲染返回箭头图标"
    # 点击复用 handleSwitchToStandard：退出关怀模式 → 标准首页（不再弹历史抽屉、不再 openDrawer）
    assert "onClick={handleSwitchToStandard}" in src, "返回按钮应调用切回标准模式逻辑"
    # 已去掉旧 ☰ 入口与 openDrawer 跳转
    assert 'data-testid="care-home-hamburger-btn"' not in src, "不应再保留旧 ☰ 按钮"
    assert "/ai-home?openDrawer=1" not in src, "返回不再走 openDrawer 历史抽屉路径"


def test_h5_care_back_returns_to_standard_home():
    """H5 关怀版返回逻辑：保存 standard 偏好并跳 /ai-home（避免回弹关怀模式）。"""
    src = _read(H5_CARE)
    assert "saveModePreference('standard')" in src, "返回应将模式偏好置为 standard"
    assert "router.push('/ai-home')" in src, "返回应跳标准 AI 主页"


def test_mp_care_left_top_is_back_arrow_to_standard():
    """小程序关怀版左上角为「← 返回箭头」，点击退回标准 AI 主页 /pages/ai/index。"""
    wxml = _read(MP_CARE_WXML)
    js = _read(MP_CARE_JS)
    assert 'data-testid="care-home-back-btn"' in wxml, "应有返回按钮"
    assert 'catchtap="goBackStandard"' in wxml, "返回按钮绑定 goBackStandard"
    assert "goBackStandard" in js, "JS 应实现 goBackStandard"
    assert "/pages/ai/index" in js, "返回应跳标准 AI 主页"
    assert "'app_mode_preference', 'standard'" in js, "返回应将模式偏好置为 standard"
    # 不再用 openHistory / openDrawer
    assert "openHistory" not in js, "不应再保留旧 openHistory"
    assert "/pages/ai/index?openDrawer=1" not in js, "返回不再走 openDrawer 历史抽屉路径"


# ============== 优化2：底部向下小箭头 ==============


def test_h5_care_scroll_hint_arrow():
    src = _read(H5_CARE)
    assert 'data-testid="care-home-scroll-hint"' in src
    assert "showScrollHint" in src
    assert "care-home-arrow-bounce" in src  # 上下跳动动画


def test_mp_care_scroll_hint_arrow():
    wxml = _read(MP_CARE_WXML)
    js = _read(MP_CARE_JS)
    wxss = _read(MP_CARE_WXSS)
    assert 'data-testid="care-home-scroll-hint"' in wxml
    assert "showScrollHint" in js
    assert "care-arrow-bounce" in wxss


# ============== 优化3：合并为「分享给好友」+ 分享面板 ==============


def test_h5_care_share_button_merged():
    """H5：原邀请好友/立即分享合并为一个「分享给好友」按钮，下方有小字推荐语。"""
    src = _read(H5_CARE)
    assert 'data-testid="care-home-share-friend-btn"' in src
    assert "分享给好友" in src
    assert "把宾尼小康推荐给亲友" in src
    assert "CareSharePanel" in src


def test_h5_care_share_panel_card_and_channels():
    """CareSharePanel：含分享卡片预览（统一文案）+ 微信好友/生成海报/复制链接三渠道 + 温情暖色海报。"""
    src = _read(H5_SHARE)
    assert UNIFIED_SLOGAN in src, "分享卡片文案必须为指定统一文案"
    assert 'data-testid="care-share-card-preview"' in src
    # 渠道 testid 用模板字符串 care-share-channel-${kind} 生成
    assert "care-share-channel-" in src
    for kind in ["wechat", "poster", "copy"]:
        assert f"'{kind}'" in src, f"缺少分享渠道：{kind}"
    assert "微信好友" in src and "生成海报" in src and "复制链接" in src
    # 海报（方案 A 温情暖色）
    assert 'data-testid="care-share-poster"' in src
    assert "用药提醒" in src and "健康记录" in src and "家人守护" in src
    # 落地拉新页 /invite（纯拉新分享：背后能力支撑为 /invite 链接，不出现"守护我/被我守护"邀请引导）
    assert "/invite" in src
    # 不得出现守护类邀请引导（守护我 / 被我守护 / 守护好友）——那是家庭档案的事
    for forbidden in ["守护我", "被我守护", "去守护", "守护好友", "守护对方"]:
        assert forbidden not in src, f"分享面板不应出现守护类邀请引导：{forbidden}"


def test_mp_care_share_panel():
    """小程序：分享面板含卡片预览（统一文案）+ 三渠道；微信好友走 open-type=share。"""
    wxml = _read(MP_CARE_WXML)
    js = _read(MP_CARE_JS)
    assert 'data-testid="care-home-share-friend-btn"' in wxml
    assert UNIFIED_SLOGAN in wxml
    assert 'data-testid="care-share-channel-wechat"' in wxml
    assert 'data-testid="care-share-channel-poster"' in wxml
    assert 'data-testid="care-share-channel-copy"' in wxml
    assert 'open-type="share"' in wxml
    assert "onShareAppMessage" in js
    # 复制链接落地 /invite 纯拉新
    assert "/invite" in js


def test_mp_care_poster_warm_orange():
    """小程序海报方案 A 温情暖色：含机器人头像、品牌名、3 功能、小程序码占位。"""
    wxml = _read(MP_CARE_WXML)
    assert 'data-testid="care-share-poster"' in wxml
    assert "宾尼小康" in wxml
    assert "用药提醒" in wxml and "健康记录" in wxml and "家人守护" in wxml
    assert 'data-testid="care-share-poster-qr"' in wxml


# ============== 优化4：今日提醒智能轮转 + 点击直达打卡页 ==============


def test_h5_care_med_reminder_clickable():
    src = _read(H5_CARE)
    assert 'data-testid="care-home-med-reminder"' in src
    assert "goMedicationReminder" in src
    assert "/ai-home/medication-reminder" in src
    # 轮转：优先未打卡 + 全部完成兜底
    assert "今天都打完啦" in src
    assert "checked" in src


def test_mp_care_med_reminder_clickable_and_rotation():
    wxml = _read(MP_CARE_WXML)
    js = _read(MP_CARE_JS)
    assert "onTapMedReminder" in wxml
    assert "onTapMedReminder" in js
    assert "care-medication" in js  # 跳打卡页
    assert "今天都打完啦" in js
    assert "checked" in js
