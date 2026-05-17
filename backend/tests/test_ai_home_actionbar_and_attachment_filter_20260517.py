"""[BUG_FIX_AI_HOME_ACTIONBAR_AND_ATTACHMENT_FILTER_20260517] 单元测试

覆盖：
1. sanitize_attachment_hint：清除 AI 回复 / 用户消息正文中的"内部协议附件提示语"
2. 边界用例：不误伤用户自然语言中的"请..."
3. 多段提示语、含图片 URL（保留）、空文本等极端场景
"""
from __future__ import annotations

import pytest

from app.utils.ai_output_sanitizer import sanitize_attachment_hint


# ──────────────────────────────────────────────────────────────────────
# 用例 1：典型脏数据 —— 整段过滤
# ──────────────────────────────────────────────────────────────────────
def test_case_1_basic_attachment_hint_removed():
    """完整三段结构的提示语 → 整段被清洗掉。"""
    raw = (
        "您好，我已收到您发来的图片。\n\n"
        "请参考下面相关附件：\n"
        "[附件 e276fa2d408f440392bc0202adaaa817.png 已保存到工作目录: "
        ".chat_attachments/18106262_e276fa2d408f440392bc0202adaaa817.png]\n"
    )
    out = sanitize_attachment_hint(raw)
    assert "请参考下面相关附件" not in out, f"提示语未被清洗: {out!r}"
    assert ".chat_attachments" not in out, f"内部路径未被清洗: {out!r}"
    assert "您好，我已收到您发来的图片" in out, f"正文被误伤: {out!r}"


# ──────────────────────────────────────────────────────────────────────
# 用例 2：图片 URL 必须保留（前端会渲染为缩略图）
# ──────────────────────────────────────────────────────────────────────
def test_case_2_image_url_preserved():
    """图片 URL 不属于提示语范围，必须保留不变。"""
    raw = (
        "图片如下：\n"
        "https://xiaokang-1323135906.cos.ap-guangzhou.myqcloud.com/images/abc.png\n\n"
        "请参考下面相关附件：\n"
        "[附件 abc.png 已保存到工作目录: .chat_attachments/123_abc.png]"
    )
    out = sanitize_attachment_hint(raw)
    assert "https://xiaokang-1323135906.cos" in out, f"图片 URL 被误伤: {out!r}"
    assert "请参考下面相关附件" not in out
    assert ".chat_attachments" not in out


# ──────────────────────────────────────────────────────────────────────
# 用例 3：不误伤用户自然语言中的"请..."
# ──────────────────────────────────────────────────────────────────────
def test_case_3_no_false_positive_on_natural_language():
    """用户消息中的"请..."自然语言不应被清洗。"""
    raw_list = [
        "请帮我看看这张化验单的结果",
        "请遵医嘱按时服药，每天 3 次。",
        "请参考下面相关附件，但没有 [附件] 这种格式",  # 缺第三段 → 不匹配
        "[附件 a.png 已保存到工作目录: .chat_attachments/x.png]",  # 缺第一段 → 不匹配
        "请参考下面相关附件：[附件 a.png 没有路径]",  # 缺路径 → 不匹配
    ]
    for raw in raw_list:
        out = sanitize_attachment_hint(raw)
        # 不应该被完全清空、不应改动原文核心信息
        assert out, f"误清空: 输入={raw!r}"
        assert "请" in out or "附件" in out, f"被误伤: 输入={raw!r} 输出={out!r}"


# ──────────────────────────────────────────────────────────────────────
# 用例 4：多段提示语共存 → 全部移除
# ──────────────────────────────────────────────────────────────────────
def test_case_4_multiple_hints_all_removed():
    """同一回复里多次出现提示语，全部被清洗。"""
    raw = (
        "第一段正文。\n"
        "请参考下面相关附件：\n[附件 a.png 已保存到工作目录: .chat_attachments/u1_a.png]\n"
        "第二段正文。\n"
        "请参考下面相关附件：\n[附件 b.jpg 已保存到工作目录: .chat_attachments/u1_b.jpg]\n"
        "第三段正文。"
    )
    out = sanitize_attachment_hint(raw)
    assert "请参考下面相关附件" not in out
    assert ".chat_attachments" not in out
    assert "第一段正文" in out
    assert "第二段正文" in out
    assert "第三段正文" in out


# ──────────────────────────────────────────────────────────────────────
# 用例 5：空 / None / 非字符串安全兜底
# ──────────────────────────────────────────────────────────────────────
def test_case_5_safe_on_empty_or_none():
    assert sanitize_attachment_hint("") == ""
    assert sanitize_attachment_hint(None) == ""  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# 用例 6：幂等
# ──────────────────────────────────────────────────────────────────────
def test_case_6_idempotent():
    raw = (
        "正文开头。\n"
        "请参考下面相关附件：\n"
        "[附件 x.png 已保存到工作目录: .chat_attachments/u_x.png]\n"
        "正文结尾。"
    )
    once = sanitize_attachment_hint(raw)
    twice = sanitize_attachment_hint(once)
    assert once == twice, "sanitize_attachment_hint 不幂等"


# ──────────────────────────────────────────────────────────────────────
# 用例 7：中文冒号变体
# ──────────────────────────────────────────────────────────────────────
def test_case_7_chinese_colon_variant():
    raw = (
        "你好。\n"
        "请参考下面相关附件：\n[附件 a.png 已保存到工作目录: .chat_attachments/123_a.png]"
    )
    out = sanitize_attachment_hint(raw)
    assert "请参考下面相关附件" not in out
    assert "你好" in out
