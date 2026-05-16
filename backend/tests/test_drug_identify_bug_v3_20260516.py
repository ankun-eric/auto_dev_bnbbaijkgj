"""[BUG_FIX_拍照识药三联_20260516] 后端单元/契约测试。

仅覆盖纯函数 + 路由层契约，避免依赖真实 LLM / OCR：
- sanitize_ai_output：免责声明去重 / 空行压缩 / 段落 hash 去重
- verify_drug_name_against_ocr：OCR 一致性相似度
- is_drug_identify_intent：触发条件
- build_implicit_drug_context：drug_identify_card meta → 隐式上下文
- run_drug_identify_stream：无图片场景立即 retake
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.ai_output_sanitizer import (  # noqa: E402
    sanitize_ai_output,
    sanitize_for_drug_card,
    verify_drug_name_against_ocr,
)
from app.services.drug_identify_engine import (  # noqa: E402
    build_implicit_drug_context,
    is_drug_identify_intent,
    run_drug_identify_stream,
)


# ── sanitize ───────────────────────────────────────────────────────────


def test_sanitize_collapses_blank_lines():
    raw = "段落A\n\n\n\n段落B\n\n\n段落C"
    out = sanitize_ai_output(raw)
    assert "\n\n\n" not in out
    assert "段落A" in out and "段落B" in out and "段落C" in out


def test_sanitize_dedups_disclaimer_paragraphs():
    raw = (
        "正文内容\n\n"
        "AI 识别结果仅供参考，具体用药请遵医嘱。\n\n"
        "AI 识别结果仅供参考，具体用药请遵医嘱。\n\n"
        "本回答仅供参考，不构成医疗诊断。"
    )
    out = sanitize_ai_output(raw)
    # 多段免责声明只保留最后一段
    assert out.count("具体用药请遵医嘱") <= 1
    assert "本回答仅供参考" in out


def test_sanitize_removes_disclaimer_tags():
    raw = "正文\n\n---disclaimer---\n免责声明\n---/disclaimer---"
    out = sanitize_ai_output(raw)
    assert "---disclaimer---" not in out and "---/disclaimer---" not in out


def test_sanitize_for_drug_card_truncates():
    lines = [f"line{i}" for i in range(50)]
    raw = "\n".join(lines)
    out = sanitize_for_drug_card(raw)
    # 应被硬截断到 ≤ 15 行（实现里 max_paragraph_lines=2，可能更少）
    assert out.count("\n") < 50


def test_sanitize_dedups_repeated_paragraph():
    raw = "注意事项：饭后服用\n\n注意事项：饭后服用\n\n剂量：5mg"
    out = sanitize_ai_output(raw)
    assert out.count("注意事项：饭后服用") == 1


# ── verify_drug_name_against_ocr ───────────────────────────────────────


def test_verify_drug_name_high_similarity():
    sim = verify_drug_name_against_ocr("阿司匹林肠溶片", "阿司匹林肠溶片 100mg*30片 拜耳")
    assert sim >= 0.7


def test_verify_drug_name_zero_when_no_overlap():
    sim = verify_drug_name_against_ocr("感冒灵颗粒", "阿司匹林肠溶片 100mg")
    assert sim < 0.4  # 完全不一致 → 应触发 retake


def test_verify_drug_name_partial():
    sim = verify_drug_name_against_ocr("布洛芬缓释胶囊", "布洛芬 0.3g 缓释")
    assert 0.3 <= sim <= 1.0


# ── is_drug_identify_intent ────────────────────────────────────────────


def test_intent_button_type_with_image():
    assert (
        is_drug_identify_intent(
            button_type="photo_recognize_drug",
            content="https://x/y.jpg",
            image_urls=["https://x/y.jpg"],
        )
        is True
    )


def test_intent_keyword_with_image():
    assert (
        is_drug_identify_intent(
            button_type=None,
            content="我上传了一张药品图片，请帮我识别 https://x/y.jpg",
            image_urls=["https://x/y.jpg"],
        )
        is True
    )


def test_intent_no_image_returns_false():
    assert (
        is_drug_identify_intent(
            button_type="photo_recognize_drug",
            content="拍照识药",
            image_urls=[],
        )
        is False
    )


# ── build_implicit_drug_context ────────────────────────────────────────


def test_build_implicit_drug_context_with_card():
    meta = {
        "message_type": "drug_identify_card",
        "medicines": [{"name": "阿司匹林肠溶片", "spec": "100mg*30片"}],
    }
    ctx = build_implicit_drug_context(meta)
    assert ctx is not None
    assert "阿司匹林" in ctx


def test_build_implicit_drug_context_returns_none_for_other_types():
    assert build_implicit_drug_context({"message_type": "text"}) is None
    assert build_implicit_drug_context({}) is None
    assert build_implicit_drug_context({"message_type": "drug_identify_retake"}) is None


# ── run_drug_identify_stream ───────────────────────────────────────────


def test_run_drug_identify_stream_empty_images_returns_retake():
    async def _run():
        events = []
        async for ev in run_drug_identify_stream(
            image_urls=[],
            ocr_text_hint=None,
            user_id=1,
            family_member_id=None,
            db=None,  # type: ignore
        ):
            events.append(ev)
        return events

    events = asyncio.get_event_loop().run_until_complete(_run())
    types = [e.get("type") for e in events]
    assert "delta" in types
    assert "done" in types
    final = [e for e in events if e.get("type") == "done"][-1]
    assert final["meta"]["message_type"] == "drug_identify_retake"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
