"""
[PRD-01 全平台固定时段切片体系 v1.0] 单元测试

覆盖范围
========
A. utils.time_slots 工具函数
   - SLOT_HOURS 9 段配置正确性 / 连续性 / 每段 2h
   - slot_label / slot_start_str / slot_end_str
   - appointment_to_slot：每段命中 + 边界值（08:00 / 22:00）+ 凌晨段 None
     + 跨日（PRD R-01-03 起始时间归段）+ None 输入
   - slot_window 起止时间窗 + 第 9 段跨日 24:00→次日 00:00
   - slots_config_payload 严格匹配 PRD §2.3 字段（slot_no/start/end）

B. /api/common/time-slots 接口
   - 公开（无需鉴权）
   - 返回 9 段 + 字段名严格 = slot_no/start/end
   - 第 9 段 end == "24:00"

C. merchant_dashboard 与 utils.time_slots 的兼容性（re-export 后行为一致）
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.utils.time_slots import (
    SLOT_COUNT,
    SLOT_HOURS,
    appointment_to_slot,
    slot_end_str,
    slot_label,
    slot_start_str,
    slot_window,
    slots_config_payload,
)


# ─────────── A. utils.time_slots 单元 ───────────

def test_slot_hours_count_is_9():
    assert SLOT_COUNT == 9
    assert len(SLOT_HOURS) == 9


def test_slot_hours_each_two_hours():
    for start, end in SLOT_HOURS:
        assert end - start == 2


def test_slot_hours_start_at_6_end_at_24():
    assert SLOT_HOURS[0][0] == 6
    assert SLOT_HOURS[-1][1] == 24


def test_slot_hours_continuous():
    for i in range(len(SLOT_HOURS) - 1):
        assert SLOT_HOURS[i][1] == SLOT_HOURS[i + 1][0]


def test_slot_label_first():
    assert slot_label(1) == "06:00-08:00"


def test_slot_label_middle():
    assert slot_label(5) == "14:00-16:00"


def test_slot_label_last_uses_24():
    assert slot_label(9) == "22:00-24:00"


def test_slot_label_invalid_returns_empty():
    assert slot_label(0) == ""
    assert slot_label(10) == ""
    assert slot_label(-1) == ""


def test_slot_start_end_str():
    assert slot_start_str(1) == "06:00"
    assert slot_end_str(1) == "08:00"
    assert slot_start_str(9) == "22:00"
    assert slot_end_str(9) == "24:00"


@pytest.mark.parametrize(
    "hour,expected_slot",
    [
        (0, None),  # 凌晨段
        (3, None),
        (5, None),
        (6, 1),     # 段 1 开始
        (7, 1),
        (8, 2),     # 段 2 开始（边界）
        (9, 2),
        (10, 3),
        (11, 3),
        (12, 4),
        (13, 4),
        (14, 5),
        (15, 5),
        (16, 6),
        (17, 6),
        (18, 7),
        (19, 7),
        (20, 8),
        (21, 8),
        (22, 9),    # 段 9 开始
        (23, 9),
    ],
)
def test_appointment_to_slot_each_hour(hour, expected_slot):
    dt = datetime(2026, 5, 6, hour, 0, 0)
    assert appointment_to_slot(dt) == expected_slot


def test_appointment_to_slot_none_input_returns_none():
    assert appointment_to_slot(None) is None


def test_appointment_to_slot_cross_day_starts_at_22_returns_9():
    """PRD R-01-03：跨日订单（22:00-次日 00:00）按起始时间归段"""
    dt = datetime(2026, 5, 6, 22, 30, 0)
    assert appointment_to_slot(dt) == 9


def test_slot_window_first_slot():
    target = date(2026, 5, 6)
    start, end = slot_window(target, 1)
    assert start == datetime(2026, 5, 6, 6, 0)
    assert end == datetime(2026, 5, 6, 8, 0)


def test_slot_window_last_slot_crosses_midnight():
    """第 9 段 22:00-24:00：end 取次日 00:00"""
    target = date(2026, 5, 6)
    start, end = slot_window(target, 9)
    assert start == datetime(2026, 5, 6, 22, 0)
    assert end == datetime(2026, 5, 7, 0, 0)


def test_slot_window_invalid_raises():
    with pytest.raises(ValueError):
        slot_window(date(2026, 5, 6), 0)
    with pytest.raises(ValueError):
        slot_window(date(2026, 5, 6), 10)


# ─────────── slots_config_payload (PRD §2.3 接口规格) ───────────

def test_slots_config_payload_strict_prd_schema():
    payload = slots_config_payload()
    assert "slots" in payload
    assert "rule" in payload
    slots = payload["slots"]
    assert len(slots) == 9
    # 字段严格 = PRD 文档：slot_no / start / end
    for s in slots:
        assert set(s.keys()) == {"slot_no", "start", "end"}


def test_slots_config_payload_first_and_last():
    payload = slots_config_payload()
    slots = payload["slots"]
    assert slots[0] == {"slot_no": 1, "start": "06:00", "end": "08:00"}
    assert slots[8] == {"slot_no": 9, "start": "22:00", "end": "24:00"}


def test_slots_config_payload_continuous_and_two_hours():
    slots = slots_config_payload()["slots"]
    for i in range(len(slots) - 1):
        assert slots[i]["end"] == slots[i + 1]["start"]


# ─────────── B. /api/common/time-slots 接口（公开） ───────────

@pytest.fixture(scope="module")
def app_client():
    """启动 FastAPI 测试客户端，仅注册 common 路由避免重型依赖"""
    from fastapi import FastAPI
    from app.api.common import router as common_router

    app = FastAPI()
    app.include_router(common_router)
    return TestClient(app)


def test_common_time_slots_endpoint_public_200(app_client):
    resp = app_client.get("/api/common/time-slots")
    assert resp.status_code == 200


def test_common_time_slots_endpoint_returns_9_slots(app_client):
    body = app_client.get("/api/common/time-slots").json()
    assert "slots" in body
    assert len(body["slots"]) == 9


def test_common_time_slots_endpoint_first_slot_06_08(app_client):
    body = app_client.get("/api/common/time-slots").json()
    assert body["slots"][0] == {"slot_no": 1, "start": "06:00", "end": "08:00"}


def test_common_time_slots_endpoint_last_slot_22_24(app_client):
    body = app_client.get("/api/common/time-slots").json()
    assert body["slots"][-1] == {"slot_no": 9, "start": "22:00", "end": "24:00"}


def test_common_time_slots_endpoint_field_names_match_prd(app_client):
    """PRD §2.3 严格规定字段为 slot_no/start/end"""
    body = app_client.get("/api/common/time-slots").json()
    for s in body["slots"]:
        assert set(s.keys()) == {"slot_no", "start", "end"}


# ─────────── C. merchant_dashboard 兼容性 ───────────

def test_merchant_dashboard_reexports_match_utils():
    """看板模块从 utils 引入 SLOT_HOURS 等，二者必须完全一致"""
    from app.api import merchant_dashboard as md

    assert md.SLOT_HOURS == SLOT_HOURS
    assert md.slot_label is slot_label
    assert md.appointment_to_slot is appointment_to_slot
    assert md.slot_window is slot_window
