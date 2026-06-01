"""[PRD-SPO2-CARD-V1 2026-06-02] 健康档案页「血氧卡片」补充 — 测试

需求要点：
- 健康档案页「今日健康数据」补血氧卡片，插在睡眠**前面**（顺序：血压/血糖/心率/血氧/睡眠）；
- 样式对标血压：🫁 图标 + 档位胶囊 + 大号数值 + 单位 % + 时间·来源行；
- 档位标准（方案 A）：≥95 正常（蓝）/ 90~94 偏低（黄）/ <90 偏低明显（橙）；
- 点击进 /health-metric/spo2；
- 后端 today-metrics 返回 spo2 字段（数值/测量时间/来源/是否异常）。

本套测试包含：
1) 后端 today-metrics 透传 spo2（value/measured_at/source/is_abnormal）；
2) 后端异常阈值（spo2 < 95 视为异常，>=95 正常）；
3) H5 / 小程序 / Flutter 三端源码静态断言（血氧卡片存在、顺序在睡眠前、三档胶囊判定标准一致）。
"""
from __future__ import annotations

import json as _json
import os
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text


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
async def spo2_profile(user_auth):
    from app.models.models import FamilyMember, HealthProfile

    from .conftest import test_session

    user_id = user_auth["user_id"]
    async with test_session() as session:
        fm = FamilyMember(
            user_id=user_id, relationship_type="本人", nickname="血氧测试本人",
            is_self=True, gender="male", status="active",
        )
        session.add(fm)
        await session.flush()
        hp = HealthProfile(
            user_id=user_id, family_member_id=fm.id, name="血氧测试本人", gender="male",
        )
        session.add(hp)
        await session.commit()
        return {"profile_id": hp.id, "user_id": user_id}


_RID_COUNTER = {"next": 70000}


async def _insert_spo2_record(profile_id: int, value: int, *,
                              days_ago: int = 0, hour: int = 9, minute: int = 0,
                              source: str = "manual", user_id: int = 1):
    from .conftest import test_session

    _RID_COUNTER["next"] += 1
    rid = _RID_COUNTER["next"]
    measured_at = (datetime.now() - timedelta(days=days_ago)).replace(
        hour=hour, minute=minute, second=0, microsecond=0)
    async with test_session() as session:
        await session.execute(text(
            "INSERT INTO health_metric_record (id, profile_id, metric_type, value_json, source, measured_at, created_at, created_by) "
            "VALUES (:id, :pid, 'spo2', :vj, :src, :ma, :ca, :cb)"
        ), {
            "id": rid, "pid": profile_id,
            "vj": _json.dumps({"value": value}),
            "src": source, "ma": measured_at, "ca": datetime.now(), "cb": user_id,
        })
        await session.commit()
    return rid


# ─── 后端 TC-1：today-metrics 透传 spo2 全字段 ───────────────────────────────

@pytest.mark.asyncio
async def test_today_metrics_spo2_carries_value_time_source(client: AsyncClient, user_auth, spo2_profile):
    pid = spo2_profile["profile_id"]
    uid = spo2_profile["user_id"]
    await _insert_spo2_record(pid, 97, source="huawei_watch", user_id=uid)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/today-metrics",
        headers=user_auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "spo2" in data, "today-metrics 必须返回 spo2 字段"
    sp = data["spo2"]
    assert sp["value"]["value"] == 97
    assert sp["source"] == "huawei_watch"
    assert sp["measured_at"]  # 非空
    assert sp["is_abnormal"] is False  # 97 >= 95 正常


# ─── 后端 TC-2：spo2 异常阈值（<95 异常）─────────────────────────────────────

@pytest.mark.asyncio
async def test_today_metrics_spo2_abnormal_below_95(client: AsyncClient, user_auth, spo2_profile):
    pid = spo2_profile["profile_id"]
    uid = spo2_profile["user_id"]
    # 92% 偏低 → 异常
    await _insert_spo2_record(pid, 92, source="manual", user_id=uid, hour=10)

    resp = await client.get(
        f"/api/health-profile-v3/{pid}/today-metrics",
        headers=user_auth["headers"],
    )
    data = resp.json()
    sp = data["spo2"]
    assert sp["value"]["value"] == 92
    assert sp["is_abnormal"] is True


# ─── 后端 TC-3：无 spo2 数据时返回空快照（卡片显示「—」）────────────────────

@pytest.mark.asyncio
async def test_today_metrics_spo2_empty_when_no_record(client: AsyncClient, user_auth, spo2_profile):
    pid = spo2_profile["profile_id"]
    resp = await client.get(
        f"/api/health-profile-v3/{pid}/today-metrics",
        headers=user_auth["headers"],
    )
    data = resp.json()
    assert "spo2" in data
    assert data["spo2"]["value"] in (None, {}, )  # 无记录 → value 为空
    assert data["spo2"]["is_abnormal"] is False


# ─── 前端静态断言公共工具 ────────────────────────────────────────────────────

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read(rel_path: str) -> str:
    path = os.path.join(_REPO_ROOT, rel_path)
    if not os.path.exists(path):
        pytest.skip(f"源码文件不存在（容器内无该端源码）：{rel_path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ─── 前端 TC-4：H5 血氧 lib 判定标准（≥95/90~94/<90）─────────────────────────

def test_h5_spo2_level_lib_thresholds():
    src = _read("h5-web/src/lib/spo2-level.ts")
    assert "judgeSpo2" in src
    assert ">= 95" in src or ">=95" in src or "value >= 95" in src
    assert ">= 90" in src or ">=90" in src or "value >= 90" in src
    assert "正常" in src and "偏低" in src and "偏低明显" in src


# ─── 前端 TC-5：H5 健康档案页含血氧卡片且排在睡眠前 ─────────────────────────

def test_h5_health_profile_spo2_card_before_sleep():
    src = _read("h5-web/src/app/health-profile/page.tsx")
    assert "judgeSpo2" in src
    assert "spo2-mini-capsule" in src  # 血氧专属胶囊
    assert "/health-metric/spo2" in src  # 点击进血氧详情
    # 顺序：血氧出现在睡眠之前（vitals 数组里 id:'spo2' 在 id:'sleep' 之前）
    sp_idx = src.index("id: 'spo2'")
    sl_idx = src.index("id: 'sleep'")
    assert sp_idx < sl_idx, "血氧卡片必须排在睡眠前面"


# ─── 前端 TC-6：小程序健康档案页含血氧胶囊且排在睡眠前 ─────────────────────

def test_miniprogram_spo2_card_before_sleep():
    src = _read("miniprogram/pages/health-profile/index.js")
    assert "judgeSpo2Mini" in src
    # 三档标准
    assert ">= 95" in src and ">= 90" in src
    assert "偏低明显" in src
    sp_idx = src.index("id: 'spo2'")
    sl_idx = src.index("id: 'sleep'")
    assert sp_idx < sl_idx, "小程序血氧卡片必须排在睡眠前面"


# ─── 前端 TC-7：Flutter 健康档案页含血氧档位且排在睡眠前 ───────────────────

def test_flutter_spo2_card_before_sleep():
    src = _read("flutter_app/lib/screens/health/health_profile_screen.dart")
    assert "_spo2Cap" in src
    assert ">= 95" in src and ">= 90" in src
    assert "偏低明显" in src
    sp_idx = src.index("'id': 'spo2'")
    sl_idx = src.index("'id': 'sleep'")
    assert sp_idx < sl_idx, "Flutter 血氧卡片必须排在睡眠前面"
