"""[PRD-HEART-RATE-DETAIL-RULE-V1 2026-05-31] 心率详情页展示规则 — 后端测试

需求核心：心率状态判断（统一标准 正常范围 60–100 次/分）
  - 低于 60（< 60）        → 偏慢
  - 60 ～ 100（含 60、100） → 正常
  - 高于 100（> 100）       → 偏快
  - 无数据（value=0/缺失）  → 未知（不显示状态）
"""
from __future__ import annotations

import pytest

from app.api.health_metric_card_v1 import _judge_status


@pytest.mark.parametrize("hr,expected_key,expected_label", [
    (40, "slow", "偏慢"),
    (59, "slow", "偏慢"),
    (60, "normal", "正常"),   # 边界值 60 算正常
    (72, "normal", "正常"),
    (100, "normal", "正常"),  # 边界值 100 算正常
    (101, "fast", "偏快"),
    (130, "fast", "偏快"),
])
def test_heart_rate_status_rule(hr, expected_key, expected_label):
    j = _judge_status("heart_rate", {"value": hr})
    assert j["key"] == expected_key
    assert j["label"] == expected_label


def test_heart_rate_no_data_returns_unknown():
    """无心率数据（value 为 0 / 缺失）时返回未知，不显示正常/偏快/偏慢。"""
    assert _judge_status("heart_rate", {"value": 0})["key"] == "unknown"
    assert _judge_status("heart_rate", {})["key"] == "unknown"


def test_heart_rate_slow_and_fast_use_warning_color():
    """偏慢/偏快为异常档，使用橙色预警色；正常为蓝色。"""
    assert _judge_status("heart_rate", {"value": 50})["color"] == "orange"
    assert _judge_status("heart_rate", {"value": 120})["color"] == "orange"
    assert _judge_status("heart_rate", {"value": 75})["color"] == "blue"
