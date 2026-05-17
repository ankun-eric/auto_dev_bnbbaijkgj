"""[BUG_FIX_AI_HOME_3BUGS_20260517] AI 对话三 Bug 修复 — sanitizer 单元测试

覆盖《AI 对话三 Bug 修复方案 v1.0》第二节 Bug A 的 sanitizer 改造：

1. 关键词收敛为整句级（移除"请遵医嘱"、"仅供参考，不能替代"等高误伤词）
2. 清洗粒度从段落级改为行级（命中只去掉该行，保留同段其他正文）
3. 取消末尾追加（不再追加任何兜底免责声明）

要求 ≥4 个用例，本文件实际包含 8 个，覆盖正常/边界/极端三类场景。
"""
from __future__ import annotations

from app.utils.ai_output_sanitizer import sanitize_ai_output
from app.utils.ai_output_sanitizer import _is_disclaimer_line, _is_full_paragraph_disclaimer


# ──────────────────────────────────────────────────────────────────
# Bug A · 用例 1：正文末段同时含"请遵医嘱"和有效内容 → 仅"请遵医嘱"被去掉？
#
# 注意：根据方案，"请遵医嘱"已**不再**作为单独关键词剥离整段；
# 但它如果作为整段免责整句出现在末尾（`仅供参考...请遵医嘱...`），仍可被识别。
# 真实 Bug A 现场：模型在正文末段附带"请遵医嘱"短句 → 旧实现整段抛弃。
# 新实现：因为"请遵医嘱"不再单独触发，整段正文必须保留。
# ──────────────────────────────────────────────────────────────────
def test_case_1_zhengwen_with_zunyizhu_should_keep_paragraph():
    """正文末段同时含'请遵医嘱'和有效内容 → 整段必须保留，不被抛弃。"""
    text = (
        "高血压患者可以适量吃西瓜，西瓜含水分高、糖分中等，建议饭后两小时少量食用，"
        "并控制单次摄入量在 200g 以内。请遵医嘱合理安排饮食。"
    )
    out = sanitize_ai_output(text)
    # 正文核心信息必须保留
    assert "高血压患者可以适量吃西瓜" in out, f"正文被错误吞掉: {out!r}"
    assert "200g" in out, f"具体数值丢失: {out!r}"


# ──────────────────────────────────────────────────────────────────
# Bug A · 用例 2：多段重复"仅供参考"独立成段 → 去重保留 0 段
# ──────────────────────────────────────────────────────────────────
def test_case_2_multiple_disclaimer_paragraphs_dedup_to_zero():
    """多段独立免责整句 → 全部移除（去重保留 0 段）。"""
    text = (
        "AI 识别结果仅供参考。\n\n"
        "西瓜含糖量约 5%，每 100g 约 25 千卡。\n\n"
        "本回答仅供参考，不构成医疗诊断。\n\n"
        "建议餐后两小时再进食。\n\n"
        "本回答仅供参考，不构成医疗诊断。"
    )
    out = sanitize_ai_output(text)
    # 正文段保留
    assert "西瓜含糖量约 5%" in out
    assert "建议餐后两小时再进食" in out
    # 免责整句被移除（不再尾部追加）
    assert "AI 识别结果仅供参考" not in out
    assert "本回答仅供参考" not in out


# ──────────────────────────────────────────────────────────────────
# Bug A · 用例 3：独立段落仅含免责声明 → 整段移除
# ──────────────────────────────────────────────────────────────────
def test_case_3_standalone_disclaimer_paragraph_removed():
    """独立段落仅含免责声明 → 整段移除。"""
    text = (
        "西瓜含水量约 92%，糖分以果糖和葡萄糖为主。\n\n"
        "AI 识别结果仅供参考"
    )
    out = sanitize_ai_output(text)
    assert "西瓜含水量约 92%" in out
    assert "AI 识别结果仅供参考" not in out


# ──────────────────────────────────────────────────────────────────
# Bug A · 用例 4：零免责段 → 输出与输入完全一致（仅做必要的空行压缩）
# ──────────────────────────────────────────────────────────────────
def test_case_4_no_disclaimer_should_be_identical():
    """零免责段 → 输出内容与输入实质一致。"""
    text = (
        "西瓜含水量约 92%，糖分以果糖和葡萄糖为主。\n\n"
        "建议餐后两小时再进食，单次摄入控制在 200g 以内。"
    )
    out = sanitize_ai_output(text)
    assert "西瓜含水量约 92%" in out
    assert "200g 以内" in out
    # 不应出现新增的免责声明
    assert "仅供参考" not in out
    assert "请遵医嘱" not in out


# ──────────────────────────────────────────────────────────────────
# Bug A · 补充用例 5：正文末段尾部夹"AI 识别结果仅供参考" → 行级清洗，正文保留
# ──────────────────────────────────────────────────────────────────
def test_case_5_disclaimer_line_inline_in_paragraph_keeps_other_lines():
    """段落里夹一行免责整句 → 仅去掉该行，同段其余行保留。"""
    text = (
        "西瓜的注意事项：\n"
        "1. 单次不超过 200g\n"
        "2. 餐后 2 小时再吃\n"
        "AI 识别结果仅供参考\n"
        "3. 冷藏后立即食用可能刺激肠胃"
    )
    out = sanitize_ai_output(text)
    assert "1. 单次不超过 200g" in out
    assert "2. 餐后 2 小时再吃" in out
    assert "3. 冷藏后立即食用可能刺激肠胃" in out
    assert "AI 识别结果仅供参考" not in out


# ──────────────────────────────────────────────────────────────────
# Bug A · 补充用例 6："请遵医嘱"作为正文一部分（非整句免责）不应被剥离
# ──────────────────────────────────────────────────────────────────
def test_case_6_zunyizhu_short_phrase_should_not_be_stripped():
    """"请遵医嘱"作为正文中夹带的短语不应触发任何剥离（行级也不行）。"""
    text = "建议每天监测血压，调整用药剂量请遵医嘱。"
    out = sanitize_ai_output(text)
    assert "建议每天监测血压" in out
    # "请遵医嘱"作为正文短语保留
    assert "请遵医嘱" in out


# ──────────────────────────────────────────────────────────────────
# Bug A · 补充用例 7：sanitizer 幂等性 — 多次调用结果不变
# ──────────────────────────────────────────────────────────────────
def test_case_7_idempotency():
    """sanitize 应当幂等：sanitize(sanitize(x)) == sanitize(x)。"""
    text = (
        "高血压可适量吃西瓜，单次 200g。\n\n"
        "AI 识别结果仅供参考"
    )
    once = sanitize_ai_output(text)
    twice = sanitize_ai_output(once)
    assert once == twice


# ──────────────────────────────────────────────────────────────────
# Bug A · 补充用例 8：空字符串 / None 安全
# ──────────────────────────────────────────────────────────────────
def test_case_8_empty_input_safe():
    assert sanitize_ai_output("") == ""
    assert sanitize_ai_output(None) == ""  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────
# 行级判定单测（白盒）
# ──────────────────────────────────────────────────────────────────
def test_is_disclaimer_line_only_match_full_sentences():
    # 命中：整句级免责
    assert _is_disclaimer_line("AI 识别结果仅供参考")
    assert _is_disclaimer_line("AI识别结果仅供参考")
    assert _is_disclaimer_line("本回答仅供参考，不构成医疗诊断")
    assert _is_disclaimer_line("Disclaimer: This is not medical advice.")

    # 不命中：模糊短语
    assert not _is_disclaimer_line("请遵医嘱")
    assert not _is_disclaimer_line("仅供参考，不能替代")
    assert not _is_disclaimer_line("调整用药剂量请遵医嘱")
    assert not _is_disclaimer_line("")
    assert not _is_disclaimer_line("高血压可适量吃西瓜")


def test_is_full_paragraph_disclaimer_only_single_line():
    # 整段是单行免责整句 → True
    assert _is_full_paragraph_disclaimer("AI 识别结果仅供参考")
    assert _is_full_paragraph_disclaimer("免责声明: 本内容由 AI 生成")

    # 多行段落即便首行是免责整句 → False（避免误伤）
    multi = "AI 识别结果仅供参考\n实际剂量 500mg"
    assert not _is_full_paragraph_disclaimer(multi)
