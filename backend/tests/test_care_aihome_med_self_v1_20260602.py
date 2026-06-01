"""[BUGFIX-CARE-AIHOME-MED-SELF-V1 2026-06-02] 关怀模式 AI 首页优化修复验收测试

本次需求（仅 H5 端）：
  第1点（Bug）：欢迎区「今日提醒」那行文字读错人——原来调用
    /api/medication-reminder/today 不带任何参数，后端 consultant_id=None 走「不过滤」分支，
    把本人 + 所有家庭成员档案的待打卡用药全混在一起统计了。
    修复目标：这行「今日提醒」固定只读「本人」（健康档案=本人，即 family_member_id IS NULL），
    永远不随被守护对象/咨询人切换而变化。
    修复手段：前端固定传 consultant_id=0（后端语义：0=本人 → family_member_id IS NULL）。

  第2点（UI 优化 方案甲）：把「模式切换」胶囊从欢迎区右上角浮动改为挪进右侧竖排容器，
    摞在 LOGO 正上方、上下对齐（右侧竖排对齐）。左侧文字、LOGO 大小样式保持不变。

测试覆盖：
1) 后端口径：/today?consultant_id=0 只返回本人（family_member_id IS NULL）的提醒，
   不混入家庭成员（family_member_id>0）的提醒；不传参数（旧行为）则混入全部（对照）。
2) 前端源码静态断言（非 UI）：
   - H5 关怀版 loadMedication 调用 today 时固定带 consultant_id: 0
   - 模式切换胶囊与 LOGO 同处右侧竖排容器（care-home-mode-logo-column）
"""
from __future__ import annotations

import os
from datetime import date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
H5_CARE = os.path.join(_ROOT, "h5-web", "src", "app", "care-ai-home", "page.tsx")
PREFIX = "/api/medication-reminder"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


async def _seed_reminder(times, family_member_id=None, medicine_name="降压药"):
    """向 medication_reminders 表写入今日提醒。

    family_member_id=None → 本人档案；>0 → 家庭成员档案。
    返回新建 reminder 的 id。
    """
    from app.models.models import MedicationReminder, User
    from tests.conftest import test_session

    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == "13900000001"))).scalar_one()
        rem = MedicationReminder(
            user_id=u.id,
            family_member_id=family_member_id,
            medicine_name=medicine_name,
            dosage="1片",
            status="active",
            long_term=True,
            custom_times=list(times),
            reminder_enabled=True,
        )
        s.add(rem)
        await s.commit()
        await s.refresh(rem)
        return rem.id


# ============== 第1点：今日提醒固定只读本人 ==============


@pytest.mark.asyncio
async def test_today_self_only_excludes_family_member(client: AsyncClient, auth_headers):
    """consultant_id=0 只返回本人（family_member_id IS NULL）的提醒，不混家庭成员。"""
    # 本人：08:00 / 20:00 两条（本人「降压药」）
    await _seed_reminder(["08:00", "20:00"], family_member_id=None, medicine_name="本人降压药")
    # 家庭成员（family_member_id=999）：12:00 一条
    await _seed_reminder(["12:00"], family_member_id=999, medicine_name="家人感冒药")

    r = await client.get(f"{PREFIX}/today", params={"consultant_id": 0}, headers=auth_headers)
    assert r.status_code == 200, r.text
    items = r.json()
    times = sorted(it["scheduled_time"] for it in items)
    assert times == ["08:00", "20:00"], f"应只返回本人两条提醒，实际={times}"
    for it in items:
        assert it["drug_name"] == "本人降压药", "不应混入家庭成员的用药"


@pytest.mark.asyncio
async def test_today_self_count_unaffected_by_family(client: AsyncClient, auth_headers):
    """多成员场景：家庭成员有大量未打卡提醒，本人口径下的数量不受影响。"""
    await _seed_reminder(["09:00"], family_member_id=None, medicine_name="本人药")
    # 家庭成员一堆提醒
    await _seed_reminder(["07:00", "13:00", "19:00", "21:00"], family_member_id=1001)
    await _seed_reminder(["06:00", "18:00"], family_member_id=1002)

    items = (await client.get(f"{PREFIX}/today", params={"consultant_id": 0}, headers=auth_headers)).json()
    assert len(items) == 1, f"本人只有 1 条提醒，不应被家庭成员影响，实际={len(items)}"
    assert items[0]["scheduled_time"] == "09:00"


@pytest.mark.asyncio
async def test_today_no_param_mixes_all_contrast(client: AsyncClient, auth_headers):
    """对照实验：不传 consultant_id（旧行为）会把本人 + 家庭成员全混在一起，
    正是本次要规避的「读错人」表现。"""
    await _seed_reminder(["08:00"], family_member_id=None)
    await _seed_reminder(["12:00"], family_member_id=2001)

    # 不传参数 → 旧「不过滤」行为，混入全部
    mixed = (await client.get(f"{PREFIX}/today", headers=auth_headers)).json()
    mixed_times = sorted(it["scheduled_time"] for it in mixed)
    assert mixed_times == ["08:00", "12:00"], "不传参数应混入全部（对照旧 Bug 行为）"

    # 传 consultant_id=0 → 只本人
    self_only = (await client.get(f"{PREFIX}/today", params={"consultant_id": 0}, headers=auth_headers)).json()
    self_times = sorted(it["scheduled_time"] for it in self_only)
    assert self_times == ["08:00"], "consultant_id=0 应只返回本人"


# ============== 前端源码静态断言（非 UI） ==============


def test_h5_care_today_fixed_self_param():
    """H5 关怀版 loadMedication 调用 today 时固定带 consultant_id: 0（永远只读本人）。"""
    src = _read(H5_CARE)
    assert "/api/medication-reminder/today" in src
    # 固定传 consultant_id: 0
    assert "consultant_id: 0" in src, "今日提醒必须固定传 consultant_id: 0（本人）"
    # 修复标记注释存在，便于追溯
    assert "BUGFIX-CARE-AIHOME-MED-SELF-V1" in src


def test_h5_care_mode_capsule_above_logo_column():
    """H5 关怀版：模式切换胶囊与 LOGO 同处右侧竖排容器，胶囊在 LOGO 正上方。"""
    src = _read(H5_CARE)
    # 新增竖排容器
    assert 'data-testid="care-home-mode-logo-column"' in src, "应有右侧竖排容器"
    # 胶囊与 LOGO 仍存在
    assert 'data-testid="care-home-mode-capsule"' in src
    assert 'data-testid="care-home-robot-logo"' in src
    # 胶囊不再用旧的右上角绝对定位（right: 16, top: 14）
    assert "right: 16, top: 14" not in src, "胶囊不应再用右上角绝对定位"
    # 竖排容器必须为竖向排列 + 居中对齐（保证胶囊在 LOGO 正上方、上下对齐）
    col_idx = src.find('data-testid="care-home-mode-logo-column"')
    assert col_idx != -1
    # 容器样式在 testid 之前的 style 中声明了 flexDirection: column 与 alignItems: center
    seg = src[max(0, col_idx - 400):col_idx]
    assert "flexDirection: 'column'" in seg, "竖排容器应为纵向排列"
    assert "alignItems: 'center'" in seg, "竖排容器应水平居中（胶囊与 LOGO 同一竖中轴对齐）"
