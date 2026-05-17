"""[BUG_FIX_AI_HOME_3BUGS_20260517] AI 输出统一清洗工具（v2 收敛版）。

本模块为所有 AI 接口（拍照识药、AI 对话、健康自查、报告解读等）提供统一的
"输出兜底清洗"函数。本次根据《AI 对话三 Bug 修复方案 v1.0》对 sanitizer 做
精细化改造：

核心变更（Bug A 修复要点）：

1. **关键词收敛为整句级**：仅命中"完整、规范"的免责声明整句（如
   "AI 识别结果仅供参考"、"本回答仅供参考，不构成医疗诊断"），
   不再使用"请遵医嘱"、"仅供参考，不能替代"等模糊高误伤词，
   避免把模型在正文末段附带的零星短语连带正文一起吃掉。
2. **清洗粒度从段落级改为行级**：命中只去掉**该行**（含前后换行），
   保留同段其他内容；正文末段不再被整段抛弃。
3. **不再做末尾追加**：法务话术统一靠前端 `AiActionBar` 那行小灰字
   "AI 生成内容仅供参考，不作为诊断依据"覆盖。

历史遗留功能（保持不变）：

1. 压缩连续空行（``\\n{3,}`` → ``\\n\\n``）
2. 段落 hash 去重，去掉完全重复段落
3. 行数 / 每段行数硬截断（识药卡片专用 enforce_line_limit=True 时启用）
4. 移除 ``---disclaimer---`` / ``</disclaimer>`` 等多余标签

设计原则：
- 纯字符串处理，不依赖任何外部状态，可在 sync / async / SSE 三种语境复用
- 失败安全：任何异常都直接返回原文本，绝不让兜底反而把正常输出搞坏
- 幂等：多次调用同一文本不应产生差异
"""
from __future__ import annotations

import hashlib
import re
from typing import List

# [BUG_FIX_AI_HOME_3BUGS_20260517]
# 整句级免责声明匹配：必须命中"完整免责整句"才会被剥离。
# 设计原则：宁愿漏过几条模型自定义的免责短句，也不能误伤正文。
# 每条规则使用「锚点子句 + 任意补语 + 终止符」三段式正则，确保命中的
# 只是"独立成段/独立成行的免责声明"，而非夹在正文中的零星词。
_DISCLAIMER_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "AI 识别结果仅供参考" / "AI识别结果仅供参考"
    re.compile(r"^\s*AI\s*识别结果仅供参考[，。、!\s]*.*?$", re.IGNORECASE),
    # "本回答仅供参考，不构成医疗诊断" / "本回答仅供参考"
    re.compile(r"^\s*本回答仅供参考(?:[，,].*?)?[。!]?\s*$"),
    # "以上内容由 AI 生成，仅供参考，不构成医疗诊断，请遵医嘱。"
    re.compile(r"^\s*以上.*?AI.*?生成.*?仅供参考.*?$"),
    # "AI 生成内容仅供参考，不作为诊断依据"
    re.compile(r"^\s*AI\s*生成内容仅供参考.*?$", re.IGNORECASE),
    # "本内容仅供参考，不构成医疗诊断"
    re.compile(r"^\s*本内容仅供参考.*?不构成.*?诊断.*?$"),
    # 纯免责整段：以"免责声明"开头的独立行
    re.compile(r"^\s*免责声明[:：].*?$"),
    # 仅由"仅供参考，不构成医疗诊断"独立成段（必须含"不构成…诊断"才匹配）
    re.compile(r"^\s*仅供参考[，,]\s*不构成.*?诊断.*?$"),
    # Disclaimer 英文整段
    re.compile(r"^\s*Disclaimer[:：].*?$", re.IGNORECASE),
)

# 整段免责（命中后整段去除，但不再扩散关键词）
# 仅当**整段全部文本**都被识别为免责声明时才剥离整段
_FULL_PARAGRAPH_DISCLAIMER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:AI\s*识别结果|本回答|本内容|以上内容).{0,40}仅供参考.*?$", re.DOTALL | re.IGNORECASE),
    re.compile(r"^\s*免责声明[:：].*?$", re.DOTALL),
    re.compile(r"^\s*Disclaimer[:：].*?$", re.DOTALL | re.IGNORECASE),
)

_DISCLAIMER_TAG_RE = re.compile(
    r"---\s*disclaimer\s*---|---/\s*disclaimer\s*---|<\s*/?\s*disclaimer\s*>",
    re.IGNORECASE,
)


def _is_disclaimer_line(line: str) -> bool:
    """[BUG_FIX_AI_HOME_3BUGS_20260517] 行级免责声明判定。

    只对**整行**进行匹配，且必须命中完整规范的免责整句。
    "请遵医嘱"、"仅供参考，不能替代"等模糊短语**不再单独**触发。
    """
    if not line or not line.strip():
        return False
    s = line.strip()
    return any(p.match(s) for p in _DISCLAIMER_LINE_PATTERNS)


def _is_full_paragraph_disclaimer(p: str) -> bool:
    """整段免责声明判定：仅当整段=独立的免责整句时才返回 True。"""
    if not p or not p.strip():
        return False
    s = p.strip()
    # 段落只有 1 行时才允许整段移除（避免误伤正文末段携带短句）
    lines = [ln for ln in s.splitlines() if ln.strip()]
    if len(lines) > 1:
        return False
    return any(p_re.match(s) for p_re in _FULL_PARAGRAPH_DISCLAIMER_PATTERNS) or _is_disclaimer_line(s)


def _hash_paragraph(p: str) -> str:
    return hashlib.md5(p.strip().encode("utf-8", errors="ignore")).hexdigest()


def _strip_disclaimer_lines(paragraph: str) -> str:
    """[BUG_FIX_AI_HOME_3BUGS_20260517] 行级清洗：去掉段落内的免责声明行。

    保留段落内非免责声明的其他行；命中只去掉该行（含前后空白），
    确保正文末段携带的零星免责短语不会把整段正文一起带走。
    """
    if not paragraph:
        return paragraph
    out_lines: List[str] = []
    for ln in paragraph.splitlines():
        if _is_disclaimer_line(ln):
            continue
        out_lines.append(ln)
    return "\n".join(out_lines).rstrip()


def sanitize_ai_output(
    text: str,
    *,
    max_lines: int = 15,
    max_paragraph_lines: int = 2,
    dedup_disclaimer: bool = True,
    enforce_line_limit: bool = False,
) -> str:
    """对 AI 模型返回的文本做兜底清洗。

    [BUG_FIX_AI_HOME_3BUGS_20260517] 收敛策略：
        - 不再追加任何兜底免责声明（前端 AiActionBar 小灰字已统一覆盖法务话术）
        - 关键词收敛为整句级，移除"请遵医嘱"、"仅供参考，不能替代"等模糊词
        - 清洗粒度从段落级改为行级：命中只去掉该行，保留同段其他正文

    参数：
        text: 原始 AI 输出
        max_lines: 整体行数上限（仅在 enforce_line_limit=True 时硬截断）
        max_paragraph_lines: 每段最多行数（仅在 enforce_line_limit=True 时生效）
        dedup_disclaimer: 是否去除免责声明行（默认 True；仍保留参数名以兼容历史调用）
        enforce_line_limit: 是否强制截断行数。
            - 拍照识药卡片这种"格式硬约束"场景：传 True
            - 普通 AI 对话 / 健康自查正文：传 False（仅做空行压缩 + 段落去重 + 行级免责清洗）

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
        seen_hashes: set[str] = set()
        deduped: List[str] = []

        for p in paragraphs:
            p_stripped = p.rstrip()
            if not p_stripped.strip():
                continue

            # [BUG_FIX_AI_HOME_3BUGS_20260517] 整段免责处理：
            # 仅当**整段就是一条免责整句**时整段剥离；否则进入行级清洗。
            if dedup_disclaimer and _is_full_paragraph_disclaimer(p_stripped):
                continue

            # [BUG_FIX_AI_HOME_3BUGS_20260517] 行级免责清洗：
            # 段落里如果夹杂免责整句，只去掉那一行，保留其余正文。
            if dedup_disclaimer:
                p_stripped = _strip_disclaimer_lines(p_stripped)
                if not p_stripped.strip():
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

        # 4) 不再追加任何兜底免责声明（已下沉到前端统一渲染）

        result = "\n\n".join(deduped).strip()

        # 5) 行数硬截断（仅识药卡片）
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


# ──────────────────────────────────────────────────────────────────────────
# [BUG_FIX_AI_HOME_ACTIONBAR_AND_ATTACHMENT_FILTER_20260517 · Bug-2]
# 内部协议提示语清洗：
#   "请参考下面相关附件：\n[附件 xxx.png 已保存到工作目录: .chat_attachments/xxx.png]"
#
# 这类提示语来自上游 AI agent 链路里的"工具调用内部协议"，本来不应外露给终端用户，
# 但偶尔会出现在 AI 回复正文中。本函数在 AI 消息 / 用户消息入库前做一道清洗，
# 保证 chat_messages.content 干净。
#
# 设计：必须三段同时满足才匹配（"请参考下面相关附件" + "[附件 xxx" + ".chat_attachments/xxx]"），
# 避免误伤用户自然语言中的"请..."。图片 URL 不动（前端会渲染为缩略图）。
# ──────────────────────────────────────────────────────────────────────────
_ATTACHMENT_HINT_RE = re.compile(
    r"请参考下面相关附件[:：]\s*\n*\s*\[附件\s+[A-Za-z0-9_\-\.]+\s+已保存到工作目录:\s*\.chat_attachments\/[^\]]+\]",
    re.MULTILINE,
)


def sanitize_attachment_hint(text: str) -> str:
    """清除 AI 回复 / 用户消息正文中的"内部协议附件提示语"整段。

    匹配规则（必须三段同时满足才删除）：
        请参考下面相关附件：
        \\n*
        \\[附件 xxx.png 已保存到工作目录: .chat_attachments/xxx.png\\]

    保留图片 URL 不动（由前端抽取后渲染为缩略图）。
    任何异常都直接返回原文本，绝不让兜底反而把正常输出搞坏。
    """
    if not text or not isinstance(text, str):
        return text or ""
    try:
        out = _ATTACHMENT_HINT_RE.sub("", text)
        # 压缩 sub 后可能引入的 3+ 空行
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.rstrip()
    except Exception:
        return text


__all__ = [
    "sanitize_ai_output",
    "sanitize_for_drug_card",
    "sanitize_attachment_hint",
    "verify_drug_name_against_ocr",
]
