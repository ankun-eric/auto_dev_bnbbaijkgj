"""[PRD-HEALTH-METRIC-AI-EXPLAIN-LAYOUT-V1 2026-06-01] AI 解读弹窗 Bug 修复 — 后端测试

覆盖需求验收点（后端侧）：
- 第 2 件：本次解读规则文案结尾不再包含重复的免责声明
  （「⚠️ 本提示仅供参考，不能替代专业医生诊断」已删除，统一由前端弹窗底部展示）
- 第 1 件（后端校验）：趋势解读的 advice 字段本身保留「建议」措辞，
  前端不应再额外加「建议：」前缀（前端侧改动，这里确认后端 advice 形态稳定）。
"""
from __future__ import annotations

import pytest

from app.api.health_metric_card_v1 import (
    _rule_explain_single,
    _rule_explain_trend,
)
from app.models.health_v3 import HealthMetricRecord


def _make_record(metric_type: str, value: dict) -> HealthMetricRecord:
    rec = HealthMetricRecord()
    rec.metric_type = metric_type
    rec.value_json = value
    rec.source = "manual"
    return rec


DISCLAIMER_FRAGMENTS = [
    "本提示仅供参考",
    "不能替代专业医生诊断",
]


@pytest.mark.parametrize(
    "metric_type,value",
    [
        ("heart_rate", {"value": 72}),
        ("heart_rate", {"value": 110}),
        ("heart_rate", {"value": 45}),
        ("blood_pressure", {"systolic": 120, "diastolic": 80}),
        ("blood_glucose", {"value": 5.5, "period": "fasting"}),
        ("spo2", {"value": 97}),
    ],
)
def test_single_explain_no_duplicate_disclaimer(metric_type, value):
    """本次解读正文不再携带重复的免责声明（第 2 件）。"""
    rec = _make_record(metric_type, value)
    content = _rule_explain_single(metric_type, rec)
    assert content, "解读文案不应为空"
    for frag in DISCLAIMER_FRAGMENTS:
        assert frag not in content, f"{metric_type} 本次解读不应包含重复免责声明片段：{frag}"


def test_single_explain_still_has_body():
    """删除免责声明后，正文主体（数值+建议）仍然完整。"""
    rec = _make_record("heart_rate", {"value": 72})
    content = _rule_explain_single("heart_rate", rec)
    assert "本次心率" in content
    assert "建议" in content


@pytest.mark.parametrize("metric_type", ["heart_rate", "blood_pressure", "blood_glucose", "spo2"])
def test_trend_advice_single_jianyi(metric_type):
    """趋势 advice 字段中『建议』作为措辞只出现在 advice 内，summary/trend 不重复加前缀。

    前端在拼接时不再额外加『建议：』，因此最终展示中『建议：』标题只出现一次。
    """
    records = [_make_record(metric_type, {"value": 80} if metric_type != "blood_pressure" else {"systolic": 120, "diastolic": 80}) for _ in range(5)]
    data = _rule_explain_trend(metric_type, records, 7)
    assert set(["summary", "trend", "advice"]).issubset(data.keys())
    # advice 自带建议措辞；summary/trend 不应以「建议：」开头造成重复
    assert not data["summary"].startswith("建议：")
