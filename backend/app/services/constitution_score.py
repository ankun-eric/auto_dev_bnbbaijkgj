"""[PRD-TCM-CONSTITUTION-36Q-V1 2026-05-20] 王琦国标 36 题中医体质判定 · 本地确定性公式

核心公式（王琦国标简化版）：
  原始分：5 级李克特量表 没有=1, 很少=2, 有时=3, 经常=4, 总是=5
  反向计分题（题 34/35/36）：score = 6 - raw_score
  按 9 个 question_group 分桶累加 → 每体质"原始分"
  转换分 = (原始分 - 题数) ÷ (题数 × 4) × 100
        = (sum - 4) / 16 * 100   （每体质 4 题）

判定规则：
  平和质：转换分 ≥ 60 且 其他 8 项转换分均 < 30 → 是
         转换分 ≥ 60 且 其他 8 项转换分均 < 40 → 基本是
  其他 8 种偏颇体质：
         转换分 ≥ 40 → 是
         转换分 30~39 → 倾向是
         转换分 < 30 → 否

输出（ConstitutionResult）：
  main_type：主体质（取转换分最高的"是"）
  secondary_types：兼夹体质（所有 transformed ≥ 40 且 ≠ 主）
  scores：9 项转换分（雷达图数据源）
  confidence：主体质与第二高分的差值
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

CONSTITUTION_GROUPS: List[str] = [
    "气虚质",
    "阳虚质",
    "阴虚质",
    "痰湿质",
    "湿热质",
    "血瘀质",
    "气郁质",
    "特禀质",
    "平和质",
]

# 反向计分题号（王琦国标：平和质第 34、35、36 题为反向题）
REVERSE_SCORE_ORDER_NUMS = {34, 35, 36}

QUESTIONS_PER_GROUP = 4

# option_index → raw score：没有=1, 很少=2, 有时=3, 经常=4, 总是=5
OPTION_SCORE_MAP: Dict[int, int] = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}

# 兼容文本答案
ANSWER_TEXT_MAP: Dict[str, int] = {
    "没有": 1,
    "很少": 2,
    "有时": 3,
    "经常": 4,
    "总是": 5,
    # 旧版兼容
    "从不": 1,
    "偶尔": 2,
    "频繁": 4,
    "经常 ": 4,
}


@dataclass
class ConstitutionResult:
    main_type: str
    secondary_types: List[str]
    scores: Dict[str, float]  # 9 项转换分
    raw_sums: Dict[str, int]  # 9 项原始分
    confidence: float  # 主体质与第二高分的差值
    judgments: Dict[str, str]  # 每体质判定字符串："是" / "倾向是" / "基本是" / "否"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _coerce_score(option_index: Optional[int], answer_value: Optional[str]) -> int:
    """把前端可能传入的 option_index 或文本 answer_value 统一转为 1~5 原始分。"""
    if option_index is not None:
        try:
            idx = int(option_index)
            if idx in OPTION_SCORE_MAP:
                return OPTION_SCORE_MAP[idx]
        except (TypeError, ValueError):
            pass
    if answer_value:
        s = str(answer_value).strip()
        if s in ANSWER_TEXT_MAP:
            return ANSWER_TEXT_MAP[s]
        # 兼容数字字符串
        try:
            n = int(s)
            if 1 <= n <= 5:
                return n
            if n in OPTION_SCORE_MAP:
                return OPTION_SCORE_MAP[n]
        except ValueError:
            pass
    # 兜底：返回最低分
    return 1


def calculate_constitution(answers: List[Dict[str, Any]]) -> ConstitutionResult:
    """计算王琦体质判定结果。

    答案条目格式（字段名灵活，兼容多种命名）：
      {
        "order_num": int,           # 题号 1~36（用于判定反向计分）
        "group": str,               # 体质类型（如"气虚质"）
        "option_index": int | None, # 0~4 选项索引（优先）
        "answer_value": str | None  # "没有/很少/有时/经常/总是" 或数字（备用）
      }

    若题目缺失 group，则跳过该题（不参与任何体质求和）。
    若某体质题数不足 4 题，仍按"题数 × 4"作为最大可得分进行归一化。
    """
    # 1. 收集每体质的"原始分总和"与"题数"
    raw_sums: Dict[str, int] = {g: 0 for g in CONSTITUTION_GROUPS}
    counts: Dict[str, int] = {g: 0 for g in CONSTITUTION_GROUPS}

    for ans in answers or []:
        group = ans.get("group") or ans.get("question_group")
        if not group or group not in raw_sums:
            continue
        order_num = ans.get("order_num")
        try:
            order_num = int(order_num) if order_num is not None else None
        except (TypeError, ValueError):
            order_num = None
        is_reverse = bool(ans.get("is_reverse_score")) or (
            order_num in REVERSE_SCORE_ORDER_NUMS
        )
        raw = _coerce_score(ans.get("option_index"), ans.get("answer_value"))
        if is_reverse:
            raw = 6 - raw
        raw_sums[group] += raw
        counts[group] += 1

    # 2. 计算每体质转换分：(sum - n) / (n * 4) * 100
    scores: Dict[str, float] = {}
    for g in CONSTITUTION_GROUPS:
        n = counts[g] or QUESTIONS_PER_GROUP
        denom = n * 4
        if denom <= 0:
            scores[g] = 0.0
            continue
        val = (raw_sums[g] - n) / denom * 100.0
        # 转换分理论范围 0~100，钳制
        if val < 0:
            val = 0.0
        if val > 100:
            val = 100.0
        scores[g] = round(val, 1)

    # 3. 判定每体质（"是 / 倾向是 / 基本是 / 否"）
    judgments: Dict[str, str] = {}
    pinghe_score = scores.get("平和质", 0.0)
    others_max = max(
        (v for k, v in scores.items() if k != "平和质"), default=0.0
    )
    if pinghe_score >= 60 and others_max < 30:
        judgments["平和质"] = "是"
    elif pinghe_score >= 60 and others_max < 40:
        judgments["平和质"] = "基本是"
    else:
        judgments["平和质"] = "否"
    for g in CONSTITUTION_GROUPS:
        if g == "平和质":
            continue
        v = scores[g]
        if v >= 40:
            judgments[g] = "是"
        elif v >= 30:
            judgments[g] = "倾向是"
        else:
            judgments[g] = "否"

    # 4. 主体质 & 兼夹体质
    if judgments["平和质"] in ("是", "基本是"):
        main_type = "平和质"
        secondary_types: List[str] = []
    else:
        # 偏颇候选：所有"是"的偏颇体质
        candidates = [
            (g, scores[g])
            for g in CONSTITUTION_GROUPS
            if g != "平和质" and judgments[g] == "是"
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)
        if candidates:
            main_type = candidates[0][0]
            secondary_types = [g for g, _ in candidates[1:]]
        else:
            # 兜底：所有体质都没达"是"，取转换分最高的体质（含倾向是 / 否）
            best = max(CONSTITUTION_GROUPS, key=lambda g: scores[g])
            main_type = best if scores[best] > 0 else "平和质"
            secondary_types = []

    # 5. 置信度：主体质与第二高分的差值
    sorted_vals = sorted(scores.values(), reverse=True)
    if len(sorted_vals) >= 2:
        confidence = round(sorted_vals[0] - sorted_vals[1], 1)
    else:
        confidence = 0.0

    return ConstitutionResult(
        main_type=main_type,
        secondary_types=secondary_types,
        scores=scores,
        raw_sums=raw_sums,
        confidence=confidence,
        judgments=judgments,
    )


__all__ = [
    "CONSTITUTION_GROUPS",
    "REVERSE_SCORE_ORDER_NUMS",
    "QUESTIONS_PER_GROUP",
    "OPTION_SCORE_MAP",
    "ConstitutionResult",
    "calculate_constitution",
]
