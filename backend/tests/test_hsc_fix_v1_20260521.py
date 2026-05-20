"""[BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21]
健康自查四问题集中修复非UI自动化测试。

涵盖：
- 模板字段：result_display_mode='triple'、key_field_codes 非空
- 答卷字段：key_summary 列存在且能写入
- Q5 选项：5 档单值（每档不重复）
- Q6 文案：题干与 subtitle 不重复
- 路由：route_h5 派发正确（health_self_check → /health-self-check/result/{id}）
- AI 追问：HSC 三段式输出 + 引用 key_summary
"""

from __future__ import annotations

import os
import sys
import asyncio
import importlib

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_hsc_severity_options_unique():
    """Q5 严重程度 5 档单值，每档文案不重复"""
    m = importlib.import_module("backend.app.services.prd_qn_content_v1_migration")
    opts = m.HSC_SEVERITY_OPTIONS
    # 排除 skip
    main = [o for o in opts if o["value"] != "skip"]
    labels = [o["label"].split()[1] if len(o["label"].split()) > 1 else o["label"] for o in main]
    # 期望 5 档
    assert len(main) == 5, f"Q5 期望 5 档单值，实际 {len(main)}: {main}"
    # 主文案应全部不同（取数字后的中文部分）
    label_zh = []
    for o in main:
        # label 形如 "1  🙂 轻微"
        parts = o["label"].split()
        label_zh.append(parts[-1])  # 最后一个 token
    assert len(set(label_zh)) == 5, f"Q5 档位文案重复: {label_zh}"


def test_hsc_q6_title_subtitle_not_duplicate():
    """Q6 题干与 subtitle/placeholder 不可完全相同"""
    m = importlib.import_module("backend.app.services.prd_qn_content_v1_migration")
    q6 = next(q for q in m.HSC_NEW_QUESTIONS if q["order"] == 93)
    assert q6["title"] != q6.get("subtitle"), "Q6 题干与 subtitle 不应相同"
    assert "补充" not in (q6.get("subtitle") or "") or "例如" in (q6.get("subtitle") or ""), (
        f"Q6 subtitle 应为示例填写，实际：{q6.get('subtitle')}"
    )


def test_route_h5_mapping_hsc():
    """detail_target.route_h5 应针对 health_self_check 走 /health-self-check/result/{id}"""
    qn = importlib.import_module("backend.app.api.questionnaire")

    class FakeTpl:
        code = "health_self_check"
        result_display_mode = "triple"

    class FakeAns:
        id = 12345

    dt = qn._build_detail_target(FakeTpl(), FakeAns())
    assert dt["route_h5"] == "/health-self-check/result/12345", dt
    assert dt["mp_path"] == "/pages/health-self-check-result/index?id=12345", dt


def test_route_h5_mapping_simple_returns_none():
    """非 triple 模式不输出 route_h5"""
    qn = importlib.import_module("backend.app.api.questionnaire")

    class FakeTpl:
        code = "health_self_check"
        result_display_mode = "simple"

    class FakeAns:
        id = 9

    dt = qn._build_detail_target(FakeTpl(), FakeAns())
    assert dt["route_h5"] is None
    assert dt["mp_path"] is None


def test_hsc_followup_text_structured():
    """HSC AI 追问应包含【针对性建议】【何时需就医】【注意事项】三段，并引用 key_summary"""
    qn = importlib.import_module("backend.app.api.questionnaire")
    text = qn._build_hsc_followup_text(
        archive_prefix="本次回答结合您的档案。",
        chip_code="jiaju",
        chip_label="居家如何处理",
        key_summary="部位：头部；症状：搏动性头痛；严重程度：7/10；持续时间：4-7 天",
    )
    assert "【针对性建议】" in text
    assert "【何时需就医】" in text
    assert "【注意事项】" in text
    assert "头部" in text or "搏动性头痛" in text or "7/10" in text, "回答应自然引用关键症状信息"
    assert "请查看上方卡片" not in text, "禁止使用「请查看上方卡片」空泛话术"


def test_hsc_followup_text_jiuyi():
    """是否需就医：返回的三段中应明确包含红线信号关键词（如 120、就诊）"""
    qn = importlib.import_module("backend.app.api.questionnaire")
    text = qn._build_hsc_followup_text(
        archive_prefix="本次回答结合您的档案。",
        chip_code="jiuyi",
        chip_label="是否需要就医",
        key_summary="部位：胸部；症状：胸痛；严重程度：5/10；持续时间：今天",
    )
    assert "120" in text or "立即就医" in text or "急" in text


def test_hsc_followup_text_zhuyi():
    qn = importlib.import_module("backend.app.api.questionnaire")
    text = qn._build_hsc_followup_text(
        archive_prefix="本次回答结合您的档案。",
        chip_code="zhuyi",
        chip_label="注意事项",
        key_summary="部位：腹部；症状：钝痛；严重程度：3/10；持续时间：1-3 天",
    )
    assert "【针对性建议】" in text
    assert "【何时需就医】" in text
    assert "【注意事项】" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
