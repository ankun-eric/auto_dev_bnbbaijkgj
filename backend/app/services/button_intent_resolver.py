"""[BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
统一按钮意图解析器（后端版）。

后台「功能按钮管理」配置体系已升级为 3 层（``button_type`` +
``ai_function_type`` + ``capture_purpose``）。本模块把任意一种合法配置
统一翻译成「专用引擎 intent」：

- ``'report_interpret'`` → ReportInterpretEngine
- ``'drug_identify'``    → DrugIdentifyEngine
- ``None``               → 通用 LLM

> ⚠️ 与前端 ``h5-web/src/utils/button-intent.ts`` 及小程序
> ``miniprogram/utils/buttonIntent.js`` 的逻辑必须保持 100% 一致。
> 三端任一修改时必须同步修改另外两端。
"""

from __future__ import annotations

from typing import Optional


__all__ = [
    "ResolvedIntent",
    "resolve_button_intent",
    "REPORT_INTERPRET",
    "DRUG_IDENTIFY",
]


REPORT_INTERPRET = "report_interpret"
DRUG_IDENTIFY = "drug_identify"

ResolvedIntent = Optional[str]


_REPORT_TOP_TYPES = {"report_interpret", "report_understand"}
_DRUG_TOP_TYPES = {"photo_recognize_drug", "drug_identify", "medication_recognize"}

_REPORT_AI_FN_LEGACY = {"report_interpret", "report_understand"}
_DRUG_AI_FN_LEGACY = {"medicine_recognize", "photo_recognize_drug", "drug_identify"}

_CAPTURE_REPORT = "interpret_report"
_CAPTURE_DRUG = "identify_medicine"
_CAPTURE_UPLOAD = "upload"


def _norm(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def resolve_button_intent(
    *,
    intent: Optional[str] = None,
    button_type: Optional[str] = None,
    ai_function_type: Optional[str] = None,
    capture_purpose: Optional[str] = None,
) -> ResolvedIntent:
    """统一按钮意图解析（前后端逻辑必须一致）。

    判定优先级（高 → 低，命中即返回，不再向下判定）：

    - P1 显式 intent：``intent`` 已显式传入 ``report_interpret`` /
      ``drug_identify``，原样返回。
    - P2 顶层老类型：``button_type`` 命中老体系报告/识药顶层类型。
    - P3 新顶层 + 老子类型兼容：``button_type='ai_function'`` 且
      ``ai_function_type`` 命中老子类型。
    - P4 新体系 image_capture + 用途：``button_type='ai_function'`` &&
      ``ai_function_type='image_capture'`` && ``capture_purpose`` 命中。
    - P5 兜底：其他所有组合返回 ``None``（走通用 LLM）。
    """
    i = _norm(intent)
    bt = _norm(button_type)
    aft = _norm(ai_function_type)
    cp = _norm(capture_purpose)

    # P1：显式 intent 最高优先级
    if i == REPORT_INTERPRET:
        return REPORT_INTERPRET
    if i == DRUG_IDENTIFY:
        return DRUG_IDENTIFY

    # P2：老顶层 button_type
    if bt in _REPORT_TOP_TYPES:
        return REPORT_INTERPRET
    if bt in _DRUG_TOP_TYPES:
        return DRUG_IDENTIFY

    # P3 / P4：新顶层 ai_function
    if bt == "ai_function":
        # P3 老子类型兼容
        if aft in _REPORT_AI_FN_LEGACY:
            return REPORT_INTERPRET
        if aft in _DRUG_AI_FN_LEGACY:
            return DRUG_IDENTIFY

        # P4 新体系 image_capture + capture_purpose
        if aft == "image_capture":
            if cp == _CAPTURE_REPORT:
                return REPORT_INTERPRET
            if cp == _CAPTURE_DRUG:
                return DRUG_IDENTIFY
            if cp == _CAPTURE_UPLOAD:
                return None
            # 其他 capture_purpose 兜底走通用 LLM
            return None

    # P5：兜底
    return None
