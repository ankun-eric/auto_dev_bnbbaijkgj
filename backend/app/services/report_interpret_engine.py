"""[BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517] 聊天内嵌「报告解读」引擎。

修复背景：ai-home 入口提交报告解读时走的是 ``POST /api/chat/sessions/{sid}/stream``
普通聊天 SSE，前端只把"图片 URL 列表 + 一句兜底文案"作为普通消息发出，
后端没有报告解读分支 → AI 拿不到 OCR 文本、专属模板、报告日期/标题等结构化上下文，
回答自然与图片对不上。

本引擎与 ``drug_identify_engine`` 并列，被 ``chat.py`` SSE 入口根据
``intent / button_id`` 分发调用。设计要点（与方案文档 §4 对齐）：

1. **复用 OCR**：与 ``/api/reports/start``、``drug_identify_engine`` 复用同一份
   ``smart_ocr_recognize`` + ``check_image_quality``，多图串行 OCR 后合并文本。
2. **复用 prompt 模板**：装载 ``_load_prompt('checkup_report_interpret', ...)``
   按 ``member_info / report_ocr_text / report_date / report_title`` format，
   与 checkup 入口完全一致；保证两条路径输出风格统一。
3. **流式输出**：用 ``call_ai_model_stream`` 推送 delta，与 drug_identify_engine
   一样按 ``{type: progress|delta|done, ...}`` 字典 yield，由调用方包成 SSE 事件。
4. **OCR 失败兜底**：当 OCR 文本为空 / OCR 失败 / 关键字命中率低时，跳过 LLM，
   按 ``card_type=report_retake`` 输出兜底气泡（含「重新上传」按钮）。
5. **会话级 family_member_id**：以 ``session.family_member_id`` 为唯一档案归属，
   不再叠加登录用户档案，避免咨询人档案串味（Bug #2 配套修复）。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import FamilyMember, PromptTemplate, User

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Intent 枚举与触发判定（通用，供 chat.py 路由层使用）
# ──────────────────────────────────────────────────────────────────────────

REPORT_INTERPRET_INTENT = "report_interpret"
REPORT_INTERPRET_BUTTON_TYPES = {
    "report_interpret",
    "report_understand",
}

# 体检/化验报告常见关键词，用于 OCR 文本"是否疑似报告"启发式判断
_REPORT_KEYWORDS = (
    "体检", "检验", "化验", "报告", "参考值", "参考范围",
    "项目名称", "结果", "单位", "异常", "↑", "↓",
    "血常规", "尿常规", "肝功能", "肾功能", "血脂", "血糖",
    "ALT", "AST", "TC", "TG", "LDL", "HDL", "WBC", "RBC", "PLT", "Hb",
)


def is_report_interpret_intent(
    *,
    intent: Optional[str],
    button_type: Optional[str],
    button_id: Optional[int],
    image_urls: List[str],
    known_report_button_ids: Optional[set] = None,
) -> bool:
    """判断当前消息是否应该走"聊天内嵌报告解读引擎"。

    分发优先级（与方案文档 §3.2 对齐）：
      1. 显式 ``intent == 'report_interpret'`` 且有图片
      2. ``button_type`` 命中 ``REPORT_INTERPRET_BUTTON_TYPES`` 且有图片
      3. 后端配置的 ``known_report_button_ids`` 命中且有图片
    """
    if not image_urls:
        return False
    if (intent or "").strip().lower() == REPORT_INTERPRET_INTENT:
        return True
    if (button_type or "").strip().lower() in REPORT_INTERPRET_BUTTON_TYPES:
        return True
    if known_report_button_ids and button_id and button_id in known_report_button_ids:
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────
# 工具：拼装当前会话归属人的 member_info 文本
# ──────────────────────────────────────────────────────────────────────────


def _calc_age(birthday) -> Optional[int]:
    if not birthday:
        return None
    try:
        today = datetime.now().date()
        return today.year - birthday.year - (
            (today.month, today.day) < (birthday.month, birthday.day)
        )
    except Exception:
        return None


def _safe_list_join(raw, sep: str = "、") -> str:
    if not raw:
        return "无"
    if isinstance(raw, list):
        items = []
        for it in raw:
            if isinstance(it, str) and it.strip():
                items.append(it.strip())
            elif isinstance(it, dict):
                for k in ("value", "name", "label", "text", "title"):
                    v = it.get(k)
                    if isinstance(v, str) and v.strip():
                        items.append(v.strip())
                        break
        return sep.join(items) if items else "无"
    if isinstance(raw, str):
        return raw.strip() or "无"
    return "无"


async def _build_member_info_text(
    db: AsyncSession,
    user: User,
    family_member_id: Optional[int],
) -> str:
    """把"当前会话归属人"（FamilyMember 或登录用户本人）拼成自然语言档案文本。

    [Bug #2 修 B] 本人统一为 ``is_self=True`` 的 FamilyMember 行；
    若数据库还没回填则降级为登录用户昵称占位，不再读 UserHealthProfile（避免双标）。
    """
    member: Optional[FamilyMember] = None
    if family_member_id:
        result = await db.execute(
            select(FamilyMember).where(
                FamilyMember.id == family_member_id,
                FamilyMember.user_id == user.id,
            )
        )
        member = result.scalar_one_or_none()
    else:
        # 兜底：拿登录用户的 is_self=True 行（若有）
        try:
            result = await db.execute(
                select(FamilyMember).where(
                    FamilyMember.user_id == user.id,
                    FamilyMember.is_self.is_(True),  # type: ignore[attr-defined]
                )
            )
            member = result.scalar_one_or_none()
        except Exception:
            member = None

    if member is None:
        return f"咨询对象：{user.nickname or '用户本人'}（暂无完整档案）"

    parts: List[str] = []
    name = member.nickname or "未命名"
    rel = getattr(member, "relationship_type", None) or ""
    parts.append(f"姓名：{name}")
    if rel:
        parts.append(f"关系：{rel}")
    age = _calc_age(getattr(member, "birthday", None))
    if age is not None:
        parts.append(f"年龄：{age} 岁")
    if getattr(member, "gender", None):
        parts.append(f"性别：{member.gender}")
    if getattr(member, "height", None):
        parts.append(f"身高：{member.height} cm")
    if getattr(member, "weight", None):
        parts.append(f"体重：{member.weight} kg")
    if getattr(member, "medical_histories", None):
        parts.append(f"慢性病/既往史：{_safe_list_join(member.medical_histories)}")
    if getattr(member, "allergies", None):
        parts.append(f"过敏史：{_safe_list_join(member.allergies)}")
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────
# 工具：OCR
# ──────────────────────────────────────────────────────────────────────────


async def _download_image(url: str, timeout: float = 10.0) -> Optional[bytes]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.content:
                return resp.content
    except Exception as e:
        logger.warning("report_interpret_engine: download image failed url=%s err=%s", url, e)
    return None


async def _run_ocr_for_urls(image_urls: List[str], db: AsyncSession) -> str:
    """对所有图片串行跑 OCR，合并文本。复用 ocr_service 中的实现。"""
    try:
        from app.services.ocr_service import check_image_quality, smart_ocr_recognize
    except Exception as e:
        logger.warning("report_interpret_engine: ocr_service unavailable: %s", e)
        return ""

    texts: List[str] = []
    for url in image_urls:
        data = await _download_image(url)
        if not data:
            continue
        try:
            quality = check_image_quality(data)
            if not quality.get("ok", True):
                continue
            text, _provider = await smart_ocr_recognize(data, db, None)
            if text:
                texts.append(text)
        except Exception as e:
            logger.warning("report_interpret_engine: OCR failed url=%s err=%s", url, e)
            continue
    return "\n\n---\n\n".join(texts) if texts else ""


# ──────────────────────────────────────────────────────────────────────────
# 工具：是否疑似体检报告（OCR 文本启发式）
# ──────────────────────────────────────────────────────────────────────────


def _is_probably_report(ocr_text: str) -> bool:
    """根据 OCR 关键词命中率粗判：是否疑似体检/化验报告。"""
    if not ocr_text or len(ocr_text.strip()) < 20:
        return False
    hits = sum(1 for kw in _REPORT_KEYWORDS if kw in ocr_text)
    return hits >= 2


# ──────────────────────────────────────────────────────────────────────────
# Prompt 模板装载（DB > 默认）
# ──────────────────────────────────────────────────────────────────────────


async def _load_report_prompt(db: AsyncSession) -> str:
    """优先取 DB 中启用的 ``checkup_report_interpret`` 模板；否则回退到默认。"""
    try:
        from sqlalchemy import desc

        q = await db.execute(
            select(PromptTemplate)
            .where(
                PromptTemplate.prompt_type == "checkup_report_interpret",
                PromptTemplate.is_active.is_(True),
            )
            .order_by(desc(PromptTemplate.updated_at))
            .limit(1)
        )
        tpl = q.scalar_one_or_none()
        if tpl and tpl.content:
            return tpl.content
    except Exception as e:
        logger.warning("report_interpret_engine: load prompt failed: %s", e)
    from app.services.prompts import DEFAULT_REPORT_INTERPRET_PROMPT
    return DEFAULT_REPORT_INTERPRET_PROMPT


# ──────────────────────────────────────────────────────────────────────────
# 主流程：SSE 流式
# ──────────────────────────────────────────────────────────────────────────


async def run_report_interpret_stream(
    *,
    image_urls: List[str],
    user: User,
    family_member_id: Optional[int],
    report_title: Optional[str],
    report_date: Optional[str],
    db: AsyncSession,
) -> AsyncIterator[Dict[str, Any]]:
    """SSE 流式执行报告解读引擎，逐段推送 progress / delta / done 事件。

    yield 出的事件字典格式与 drug_identify_engine 对齐：
      ``{"type": "progress", "stage": "...", "text": "..."}``
      ``{"type": "delta",    "content": "..."}``
      ``{"type": "done",     "content": "...", "meta": {...}}``
    """
    if not image_urls:
        yield {"type": "progress", "stage": "no_image", "text": "未收到图片"}
        retake_text = "未收到图片，请重新上传一张清晰的体检/化验报告图片。"
        yield {"type": "delta", "content": retake_text}
        yield {
            "type": "done",
            "content": retake_text,
            "meta": {
                "message_type": "report_interpret_retake",
                "card_type": "report_retake",
                "reason": "no_image",
                "family_member_id": family_member_id,
            },
        }
        return

    yield {"type": "progress", "stage": "received", "text": "正在识别报告内容…"}

    # 1) 并行：OCR + 档案文本拼装
    ocr_task = asyncio.create_task(_run_ocr_for_urls(image_urls, db))
    member_info_task = asyncio.create_task(
        _build_member_info_text(db, user, family_member_id)
    )
    ocr_text, member_info = await asyncio.gather(ocr_task, member_info_task)

    if not ocr_text or not _is_probably_report(ocr_text):
        # OCR 失败 / 文本太少 / 不像报告 → 兜底气泡
        yield {"type": "progress", "stage": "ocr_failed", "text": "未能识别这张图片"}
        retake_text = (
            "未能识别这张图片。请确认图片清晰、且为体检/化验单后重新上传。"
        )
        yield {"type": "delta", "content": retake_text}
        yield {
            "type": "done",
            "content": retake_text,
            "meta": {
                "message_type": "report_interpret_retake",
                "card_type": "report_retake",
                "reason": "ocr_failed" if not ocr_text else "not_report",
                "ocr_text": ocr_text,
                "image_urls": image_urls,
                "family_member_id": family_member_id,
            },
        }
        return

    yield {"type": "progress", "stage": "ocr_done", "text": "OCR 完成，正在解读…"}

    # 2) 装载报告解读专属 prompt 模板，按字段渲染
    prompt_tpl = await _load_report_prompt(db)
    today_str = datetime.now().date().strftime("%Y-%m-%d")
    final_title = (report_title or "").strip() or f"{today_str} 体检报告"
    final_date = (report_date or "").strip() or today_str
    try:
        first_user_content = prompt_tpl.format(
            member_info=member_info or "（档案信息不完整）",
            report_ocr_text=ocr_text,
            report_date=final_date,
            report_title=final_title,
        )
    except Exception as e:
        logger.error("report_interpret_engine: prompt format failed: %s", e)
        first_user_content = (
            f"{prompt_tpl}\n\n# 咨询对象档案\n{member_info}\n\n"
            f"# 报告标题：{final_title}\n# 报告日期：{final_date}\n\n"
            f"# 体检报告 OCR 文本\n{ocr_text}"
        )

    # 3) 调用 LLM 流式吐回
    from app.services.ai_service import call_ai_model_stream

    accumulated = ""
    try:
        async for chunk in call_ai_model_stream(
            messages=[{"role": "user", "content": first_user_content}],
            system_prompt="",
            db=db,
        ):
            ctype = chunk.get("type")
            content = chunk.get("content", "") or ""
            if ctype == "delta" and content:
                # call_ai_model_stream 的 delta 是增量（_full 在内部维护，但此处 content 是这一片段）
                # 与 ai_service 实现对齐：delta.content 是单次新增的 piece
                accumulated += content
                yield {"type": "delta", "content": content}
            elif ctype == "done":
                final_text = chunk.get("content") or accumulated
                accumulated = final_text or accumulated
                meta: Dict[str, Any] = {
                    "message_type": "report_interpret_card",
                    "card_type": "report_interpret",
                    "image_urls": image_urls,
                    "ocr_text": ocr_text,
                    "family_member_id": family_member_id,
                    "report_title": final_title,
                    "report_date": final_date,
                }
                yield {
                    "type": "done",
                    "content": accumulated or "（解读结果为空）",
                    "meta": meta,
                }
                return
    except Exception as e:
        logger.error("report_interpret_engine: LLM call failed: %s", e)
        err_text = "AI 解读服务暂时不可用，请稍后重试。"
        yield {"type": "delta", "content": err_text}
        yield {
            "type": "done",
            "content": err_text,
            "meta": {
                "message_type": "report_interpret_retake",
                "card_type": "report_retake",
                "reason": "llm_unavailable",
                "family_member_id": family_member_id,
            },
        }
        return

    # 兜底：流提前结束但未收到 done
    meta = {
        "message_type": "report_interpret_card",
        "card_type": "report_interpret",
        "image_urls": image_urls,
        "ocr_text": ocr_text,
        "family_member_id": family_member_id,
        "report_title": final_title,
        "report_date": final_date,
    }
    yield {"type": "done", "content": accumulated or "（解读结果为空）", "meta": meta}


__all__ = [
    "REPORT_INTERPRET_INTENT",
    "REPORT_INTERPRET_BUTTON_TYPES",
    "is_report_interpret_intent",
    "run_report_interpret_stream",
]
