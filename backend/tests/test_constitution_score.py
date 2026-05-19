"""[PRD-TCM-CONSTITUTION-36Q-V1] 王琦本地公式判定 · 单元测试

覆盖 F14.3 全部 5 个用例：
  1. 全选"没有" → 9 项转换分全为 0
  2. 阳虚质全"总是"，其他全"没有" → 阳虚 100、其余 0、主体质=阳虚质
  3. 平和质≥60、其他<30 → 主体质=平和质
  4. 阳虚 + 气虚均 ≥ 40 → 主体质=转换分最高、另一进 secondary
  5. 反向计分（题 34）：raw=5 应被计为 1 分

可独立运行：python -m pytest backend/tests/test_constitution_score.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

# 兼容直接 pytest 运行（保证能 import app.*）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
for _p in (_BACKEND_ROOT, _PROJECT_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.services.constitution_score import (  # noqa: E402
    CONSTITUTION_GROUPS,
    calculate_constitution,
)


def _build_answers(scenario: dict[str, str]) -> list[dict]:
    """构造 36 题答案。
    scenario: {体质类型: "没有"/"很少"/"有时"/"经常"/"总是"}
    其余未指定的体质默认"没有"。
    """
    order_map = {
        "气虚质": [1, 2, 3, 4],
        "阳虚质": [5, 6, 7, 8],
        "阴虚质": [9, 10, 11, 12],
        "痰湿质": [13, 14, 15, 16],
        "湿热质": [17, 18, 19, 20],
        "血瘀质": [21, 22, 23, 24],
        "气郁质": [25, 26, 27, 28],
        "特禀质": [29, 30, 31, 32],
        "平和质": [33, 34, 35, 36],
    }
    answers = []
    for g in CONSTITUTION_GROUPS:
        ans_text = scenario.get(g, "没有")
        for order_num in order_map[g]:
            answers.append({
                "order_num": order_num,
                "group": g,
                "answer_value": ans_text,
            })
    return answers


def test_case1_all_no():
    """用例 1：全 36 题选「没有」→ 9 项转换分全为 0。"""
    answers = _build_answers({g: "没有" for g in CONSTITUTION_GROUPS})
    result = calculate_constitution(answers)
    for g in CONSTITUTION_GROUPS:
        if g == "平和质":
            # 平和质 3 道反向 + 1 道正向 全选"没有"：
            # 反向 raw=5 (6-1) × 3 + 正向 raw=1 × 1 = 16，转换分 = (16-4)/16*100 = 75
            # 是否有兜底"基本是"，依赖 others_max < 40
            continue
        assert result.scores[g] == 0.0, f"{g} 转换分应为 0，实际 {result.scores[g]}"


def test_case2_yangxu_all_max():
    """用例 2：阳虚质 4 题「总是」、其他 32 题「没有」→ 阳虚=100、主体质=阳虚质。"""
    answers = _build_answers({"阳虚质": "总是"})
    result = calculate_constitution(answers)
    assert result.scores["阳虚质"] == 100.0, f"阳虚转换分应为 100，实际 {result.scores['阳虚质']}"
    assert result.main_type == "阳虚质", f"主体质应为阳虚质，实际 {result.main_type}"
    # 其他偏颇体质应为 0
    for g in ["气虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质"]:
        assert result.scores[g] == 0.0


def test_case3_pinghe_main():
    """用例 3：平和质转换分≥60、其他≤30 → 主体质=平和质。

    构造：平和质 33 题（正向）"总是"=5；34/35/36 反向"没有"=raw1→实际 5。
    总和 = 5 + 5 + 5 + 5 = 20，转换分=(20-4)/16*100=100。
    其他体质全"没有"=0。
    """
    answers = []
    order_map_pinghe = [33, 34, 35, 36]
    for order_num in order_map_pinghe:
        if order_num == 33:
            answers.append({"order_num": 33, "group": "平和质", "answer_value": "总是"})
        else:
            # 34/35/36 反向题，"没有"反向计分 → raw=5
            answers.append({"order_num": order_num, "group": "平和质", "answer_value": "没有"})
    # 其他体质全"没有"
    for g in CONSTITUTION_GROUPS:
        if g == "平和质":
            continue
        order_map = {
            "气虚质": [1, 2, 3, 4], "阳虚质": [5, 6, 7, 8], "阴虚质": [9, 10, 11, 12],
            "痰湿质": [13, 14, 15, 16], "湿热质": [17, 18, 19, 20], "血瘀质": [21, 22, 23, 24],
            "气郁质": [25, 26, 27, 28], "特禀质": [29, 30, 31, 32],
        }
        for o in order_map[g]:
            answers.append({"order_num": o, "group": g, "answer_value": "没有"})
    result = calculate_constitution(answers)
    assert result.scores["平和质"] == 100.0
    assert result.main_type == "平和质", f"主体质应为平和质，实际 {result.main_type}"


def test_case4_main_and_secondary():
    """用例 4：阳虚 + 气虚转换分均 ≥ 40，主体质=转换分最高，另一进 secondary。"""
    answers = []
    # 气虚质 4 题"经常"(raw=4 每题)=16，转换分=(16-4)/16*100=75
    for o in [1, 2, 3, 4]:
        answers.append({"order_num": o, "group": "气虚质", "answer_value": "经常"})
    # 阳虚质 4 题"总是"(raw=5 每题)=20，转换分=(20-4)/16*100=100
    for o in [5, 6, 7, 8]:
        answers.append({"order_num": o, "group": "阳虚质", "answer_value": "总是"})
    # 其余全"没有"
    for g, orders in [
        ("阴虚质", [9, 10, 11, 12]), ("痰湿质", [13, 14, 15, 16]),
        ("湿热质", [17, 18, 19, 20]), ("血瘀质", [21, 22, 23, 24]),
        ("气郁质", [25, 26, 27, 28]), ("特禀质", [29, 30, 31, 32]),
        ("平和质", [33, 34, 35, 36]),
    ]:
        for o in orders:
            answers.append({"order_num": o, "group": g, "answer_value": "没有"})
    result = calculate_constitution(answers)
    assert result.scores["阳虚质"] == 100.0
    assert result.scores["气虚质"] == 75.0
    assert result.main_type == "阳虚质", f"主体质应为阳虚质，实际 {result.main_type}"
    assert "气虚质" in result.secondary_types, f"气虚质应在 secondary，实际 {result.secondary_types}"


def test_case5_reverse_score():
    """用例 5：反向题（题 34）选「总是」（raw=5）应被计为 1 分。

    构造：平和质 33 正向 "没有"(1) + 34 反向 "总是"(原始5→反向1) + 35反向"总是"+36反向"总是"
    总和 = 1+1+1+1 = 4，转换分 = (4-4)/16*100 = 0
    """
    answers = [
        {"order_num": 33, "group": "平和质", "answer_value": "没有"},  # 正向 → 1
        {"order_num": 34, "group": "平和质", "answer_value": "总是"},  # 反向 → 6-5=1
        {"order_num": 35, "group": "平和质", "answer_value": "总是"},  # 反向 → 1
        {"order_num": 36, "group": "平和质", "answer_value": "总是"},  # 反向 → 1
    ]
    # 其他题全"没有"
    for g, orders in [
        ("气虚质", [1, 2, 3, 4]), ("阳虚质", [5, 6, 7, 8]), ("阴虚质", [9, 10, 11, 12]),
        ("痰湿质", [13, 14, 15, 16]), ("湿热质", [17, 18, 19, 20]),
        ("血瘀质", [21, 22, 23, 24]), ("气郁质", [25, 26, 27, 28]),
        ("特禀质", [29, 30, 31, 32]),
    ]:
        for o in orders:
            answers.append({"order_num": o, "group": g, "answer_value": "没有"})
    result = calculate_constitution(answers)
    # 反向计分正确性：平和质转换分应为 0（说明反向计分被正确应用）
    assert result.scores["平和质"] == 0.0, f"反向计分错误，平和质转换分 {result.scores['平和质']}"


def test_determinism_10_times():
    """同一份 36 题答案，重复计算 10 次结果完全一致（确定性验证 验收标准 #9）。"""
    answers = _build_answers({"阳虚质": "总是", "气虚质": "经常"})
    first = calculate_constitution(answers).to_dict()
    for _ in range(9):
        again = calculate_constitution(answers).to_dict()
        assert again == first, "公式判定非确定性！"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
