"""[BUG_FIX_拍照识药三联_20260516] AI 输出统一清洗工具。

本模块为所有 AI 接口（拍照识药、AI 对话、健康自查、报告解读等）提供统一的
"输出兜底清洗"函数，承担方案文档第 3.3 节的全局责任：

1. 压缩连续空行（\\n{3,} → \\n\\n），消除"段落之间动辄 2~3 个空行"现象
2. 段落 hash 去重，去掉完全重复段落（识药卡里"注意事项"被重复一遍）
3. 免责声明去重，**无论以何种形式出现**只保留最后 1 段
4. 行数 / 每段行数硬截断，与 Prompt 双保险
5. 移除 ``---disclaimer---`` / ``</disclaimer>`` 等多余标签

设计原则：
- 纯字符串处理，不依赖任何外部状态，可在 sync / async / SSE 三种语境复用
- 失败安全：任何异常都直接返回原文本，绝不让兜底反而把正常输出搞坏
- 幂等：多次调用同一文本不应产生差异
"""
from __future__ import annotations

import hashlib
import re
from typing import List

# 识别多种格式的免责声明片段，统一收敛为最后一段
_DISCLAIMER_KEYWORDS = (
    "本回答仅供参考",
    "AI 识别结果仅供参考",
    "AI识别结果仅供参考",
    "具体用药请遵医嘱",
    "不构成医疗诊断",
    "请遵医嘱",
    "仅供参考，不能替代",
    "Disclaimer",
)

_DISCLAIMER_TAG_RE = re.compile(
    r"---\s*disclaimer\s*---|---/\s*disclaimer\s*---|<\s*/?\s*disclaimer\s*>",
    re.IGNORECASE,
)


def _is_disclaimer_paragraph(p: str) -> bool:
    p_norm = p.strip()
    if not p_norm:
        return False
    return any(kw in p_norm for kw in _DISCLAIMER_KEYWORDS)


def _hash_paragraph(p: str) -> str:
    return hashlib.md5(p.strip().encode("utf-8", errors="ignore")).hexdigest()


def sanitize_ai_output(
    text: str,
    *,
    max_lines: int = 15,
    max_paragraph_lines: int = 2,
    dedup_disclaimer: bool = True,
    enforce_line_limit: bool = False,
) -> str:
    """对 AI 模型返回的文本做兜底清洗。

    参数：
        text: 原始 AI 输出
        max_lines: 整体行数上限（仅在 enforce_line_limit=True 时硬截断）
        max_paragraph_lines: 每段最多行数（仅在 enforce_line_limit=True 时生效）
        dedup_disclaimer: 是否去重免责声明（默认 True）
        enforce_line_limit: 是否强制截断行数。
            - 拍照识药卡片这种"格式硬约束"场景：传 True
            - 普通 AI 对话 / 健康自查正文：传 False（仅做空行压缩 + 段落去重 + 免责去重）

    返回：
        清洗后的文本。任何异常都会回退到原文本。
    """
    if not text or not isinstance(text, str):
        return text or ""

    try:
        cleaned = text

        # 1) 移除显式的 ---disclaimer--- 标签（无论位置）
        cleaned = _DISCLAIMER_TAG_RE.sub("", cleaned)

        # 2) 压缩连续空行：3 个以上 \n 收敛为 \n\n
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        # 3) 段落级处理（按空行切段）
        paragraphs = re.split(r"\n\s*\n", cleaned)
        seen_hashes = set()
        deduped: List[str] = []
        disclaimer_paragraphs: List[str] = []

        for p in paragraphs:
            p_stripped = p.rstrip()
            if not p_stripped.strip():
                continue
            # 免责声明先抽取出来，后面统一只保留最后一段
            if dedup_disclaimer and _is_disclaimer_paragraph(p_stripped):
                disclaimer_paragraphs.append(p_stripped.strip())
                continue
            h = _hash_paragraph(p_stripped)
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            if enforce_line_limit and max_paragraph_lines > 0:
                lines = [ln for ln in p_stripped.splitlines() if ln.strip()]
                if len(lines) > max_paragraph_lines:
                    lines = lines[:max_paragraph_lines]
                p_stripped = "\n".join(lines)

            deduped.append(p_stripped)

        # 4) 拼回最终免责声明（取最后一段，作为统一兜底）
        if dedup_disclaimer and disclaimer_paragraphs:
            deduped.append(disclaimer_paragraphs[-1])

        result = "\n\n".join(deduped).strip()

        # 5) 行数硬截断
        if enforce_line_limit and max_lines > 0:
            all_lines = result.splitlines()
            if len(all_lines) > max_lines:
                result = "\n".join(all_lines[:max_lines]).rstrip()

        # 6) 再压缩一次（去重段落拼回时可能引入少量空行）
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()
    except Exception:
        return text


def sanitize_for_drug_card(text: str) -> str:
    """识药卡片专用：启用行数硬约束（≤ 15 行 / 每段 ≤ 2 行）。"""
    return sanitize_ai_output(
        text,
        max_lines=15,
        max_paragraph_lines=2,
        dedup_disclaimer=True,
        enforce_line_limit=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# 一致性校验（B4）
# ──────────────────────────────────────────────────────────────────────────


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def _normalize_drug_text(s: str) -> str:
    """归一化药名/OCR 文字：去空白、去括号内容、统一大小写。"""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[\s\u3000]+", "", s)
    s = re.sub(r"[（(].*?[）)]", "", s)
    s = re.sub(r"[【\[].*?[】\]]", "", s)
    return s


def verify_drug_name_against_ocr(model_drug_name: str, ocr_text: str) -> float:
    """计算模型输出的药名与 OCR 文字的相似度（0.0~1.0）。

    实现思路：
    - 把 OCR 文字按行/常见分隔符切片，挑出"看起来像药名"的候选行
    - 对每一行与模型药名做编辑距离计算 → 1 - dist/max_len
    - 取所有候选中的最高相似度

    用于方案 §3.1 的"一致性二次校验"：
    - 相似度 ≥ 0.7 视为一致
    - 0.4~0.7 视为可疑（建议降级 pick_candidate）
    - < 0.4 视为不一致（建议 retake）
    """
    if not model_drug_name or not ocr_text:
        return 0.0

    name = _normalize_drug_text(model_drug_name)
    if not name:
        return 0.0

    # 候选切片
    candidates: List[str] = []
    for raw_line in re.split(r"[\n\r\t,，。；;]+", ocr_text):
        ln = _normalize_drug_text(raw_line)
        if not ln:
            continue
        # 单行整体 + 滑窗子串两种粒度
        candidates.append(ln)
        if len(ln) > len(name):
            for i in range(0, len(ln) - len(name) + 1):
                candidates.append(ln[i : i + len(name)])

    if not candidates:
        return 0.0

    best = 0.0
    for c in candidates:
        if not c:
            continue
        max_len = max(len(c), len(name))
        if max_len == 0:
            continue
        d = _levenshtein(c, name)
        sim = 1.0 - d / max_len
        if sim > best:
            best = sim
        if best >= 1.0:
            break
    return round(best, 4)


__all__ = [
    "sanitize_ai_output",
    "sanitize_for_drug_card",
    "verify_drug_name_against_ocr",
]
