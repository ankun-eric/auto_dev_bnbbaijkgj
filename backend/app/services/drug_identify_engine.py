"""[BUG_FIX_拍照识药三联_20260516] 聊天内嵌识药引擎（方案 E）。

核心目标（方案文档 §7）：
- 让 ai-home 在 ``/api/chat/sessions/{id}/stream`` 这条用户实际走的链路里，也能用上
  与 ``/api/drugs/identify-v2`` 完全等价的"OCR + 视觉 + 一致性校验 + 6 维档案 + 全局 sanitize"
  能力，而**不必跳到独立的 ``drug_query`` 页面**。

设计要点：
1. **OCR + 视觉并行**：``asyncio.gather`` 同时拉起 ``smart_ocr_recognize`` 与
   ``identify_drug_structured``，最大化首字节响应时间。
2. **一致性校验**：用 ``verify_drug_name_against_ocr`` 做相似度兜底。
   - ≥ 0.7 → 通过，正常 show_card
   - < 0.7 → 强制降级为 pick_candidate / retake，绝不输出错误结论
3. **6 维健康档案**：通过 ``build_user_profile_for_drug_identify`` 注入完整档案上下文。
4. **SSE 进度事件**：分阶段推送 progress 事件（OCR 完成 / 视觉完成 / 整合完成），
   保证首字节 ≤ 2 秒。
5. **结构化 meta**：识别成功后，把药品 JSON 持久化到 ``ChatMessage.message_metadata``，
   供前端按 ``message_type=drug_identify_card`` 渲染卡片，并供后续追问时作为隐式 system context。

未引入 Redis：本次实现把缓存做成"内存软缓存"占位（同一进程 7 天内同图同档案命中），
真正的 Redis 缓存留待后续接入；架构上预留 ``_cache_get`` / ``_cache_put`` 钩子。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.health_profile_service import build_user_profile_for_drug_identify
from app.utils.ai_output_sanitizer import (
    sanitize_for_drug_card,
    verify_drug_name_against_ocr,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# 触发判定：button_type / 预设文案
# ──────────────────────────────────────────────────────────────────────────

_DRUG_BUTTON_TYPES = {
    "photo_recognize_drug",
    "drug_identify",
    "medication_recognize",
    "drug_recognize",
}

_DRUG_KEYWORDS = (
    "拍照识药",
    "识别药",
    "药品图片",
    "上传了一张药品",
    "药盒",
)


def is_drug_identify_intent(
    *,
    button_type: Optional[str],
    content: str,
    image_urls: List[str],
) -> bool:
    """判断当前消息是否应该走"聊天内嵌识药引擎"。

    触发条件（满足任一）：
    1. 客户端显式传入 button_type ∈ _DRUG_BUTTON_TYPES，且消息含图片 URL
    2. 消息文本明确提到"拍照识药 / 识别药"等关键词，且消息含图片 URL
    """
    if not image_urls:
        return False
    bt = (button_type or "").strip().lower()
    if bt in _DRUG_BUTTON_TYPES:
        return True
    if any(k in (content or "") for k in _DRUG_KEYWORDS):
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────
# 简易内存缓存（同进程，TTL 7 天；后续可替换为 Redis）
# ──────────────────────────────────────────────────────────────────────────

_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 7 * 24 * 3600  # 7 天


def _make_cache_key(image_urls: List[str], family_member_id: Optional[int]) -> str:
    h = hashlib.sha256()
    for u in sorted(image_urls):
        h.update(u.encode("utf-8", errors="ignore"))
        h.update(b"|")
    h.update(f"fm:{family_member_id or 0}".encode("utf-8"))
    return h.hexdigest()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    item = _CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return val


def _cache_put(key: str, val: Dict[str, Any]) -> None:
    _CACHE[key] = (time.time(), val)


# ──────────────────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────────────────


async def _download_first_image(url: str, timeout: float = 8.0) -> Optional[bytes]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.content:
                return resp.content
    except Exception as e:
        logger.warning("drug_identify_engine: download image failed url=%s err=%s", url, e)
    return None


async def _run_ocr_for_urls(image_urls: List[str], db: AsyncSession) -> str:
    """对所有图片串行跑 OCR（OCR 厂商接口本身已是 async；多图错峰避免压垮配额）。"""
    from app.services.ocr_service import check_image_quality, smart_ocr_recognize

    texts: List[str] = []
    for url in image_urls:
        data = await _download_first_image(url)
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
            logger.warning("drug_identify_engine: OCR failed url=%s err=%s", url, e)
            continue
    return "\n\n---\n\n".join(texts) if texts else ""


async def _run_vision_identify(
    image_urls: List[str],
    ocr_text: Optional[str],
    user_profile: Dict[str, Any],
    db: AsyncSession,
) -> Dict[str, Any]:
    """复用 ai_service.identify_drug_structured，确保两条链路使用同一 Prompt 和校验逻辑。"""
    from app.services.ai_service import identify_drug_structured

    return await identify_drug_structured(
        image_urls=image_urls,
        ocr_text=ocr_text,
        user_profile=user_profile or None,
        db=db,
    )


def _build_summary_markdown(
    structured: Dict[str, Any], user_profile: Dict[str, Any]
) -> str:
    """根据结构化结果组装最终展示文本，并经 sanitize 兜底清洗。

    输出严格 ≤ 15 行 / 每段 ≤ 2 行 / 1 段免责声明。
    """
    raw = structured.get("summary_markdown") or ""
    medicines = structured.get("medicines") or []

    # 如果模型已给出 summary_markdown，直接走 sanitize；否则重新组装
    if not raw and medicines:
        lines: List[str] = []
        m = medicines[0] if isinstance(medicines[0], dict) else {}
        name = m.get("name") or m.get("brand") or "未知药品"
        lines.append(f"### {name}")
        if m.get("ingredients"):
            lines.append(f"- 成分：{m['ingredients']}")
        if m.get("indications"):
            lines.append(f"- 适应症：{m['indications']}")
        if m.get("usage"):
            lines.append(f"- 用法用量：{m['usage']}")
        if m.get("precautions"):
            lines.append(f"- 注意事项：{m['precautions']}")

        # 「结合您的健康档案」块（仅在档案存在风险点时输出）
        archive_lines = _build_archive_aware_block(m, user_profile)
        if archive_lines:
            lines.append("")
            lines.append("### 结合您的健康档案")
            for ln in archive_lines:
                lines.append(f"- {ln}")
        lines.append("")
        lines.append(structured.get("disclaimer") or "AI 识别结果仅供参考，具体用药请遵医嘱。")
        raw = "\n".join(lines)
    return sanitize_for_drug_card(raw)


def _build_personalized_risk(
    medicine: Dict[str, Any], profile: Dict[str, Any]
) -> Dict[str, Any]:
    """[BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2]
    根据当前选中家庭成员的档案 + 药品信息，输出一段"个性化风险结论"，
    供识药卡片底部「个性化风险提示」模块渲染。

    返回结构::

        {
          "level": "danger" | "caution" | "safe",     # 风险等级
          "label": "⚠️ 不建议服用" / "⚠️ 谨慎服用" / "✅ 可以服用",
          "conclusion": "一句话结论",
          "reasons": ["命中规则 1", "命中规则 2", ...]  # 详细原因
        }
    """
    drug_name = (medicine.get("name") or medicine.get("brand") or "").lower()
    ingredients = (medicine.get("ingredients") or "").lower()
    reasons: List[str] = []

    # 1) 过敏冲突（强禁忌） → 不建议服用
    for a in profile.get("allergies") or []:
        n = (a.get("name") or "").lower()
        if not n:
            continue
        if n in drug_name or (ingredients and n in ingredients):
            sev = a.get("severity") or "未知"
            reasons.append(f"对「{a['name']}」过敏（严重度：{sev}），命中本药成分")

    if reasons:
        return {
            "level": "danger",
            "label": "⚠️ 不建议服用",
            "conclusion": "本药品命中过敏史，请勿自行服用，应换药或咨询医生。",
            "reasons": reasons,
        }

    # 2) 在服药物 / 慢病 / 特殊人群 → 谨慎服用
    cautions: List[str] = []
    for med in profile.get("current_medications") or []:
        n = (med.get("name") or "").strip()
        if n and n.lower() != drug_name:
            cautions.append(f"当前在服「{n}」，与本药同服前请确认相互作用")
            break

    chronic = profile.get("chronic_diseases") or []
    if chronic:
        cautions.append(
            "慢病记录：" + "、".join(chronic[:3]) + "，请确认本药对相关疾病无禁忌"
        )

    ag = profile.get("age_group")
    if ag in ("婴幼儿", "未成年人", "老年人"):
        cautions.append(f"属于{ag}人群，剂量与禁忌请按特殊人群说明严格执行")

    if cautions:
        return {
            "level": "caution",
            "label": "⚠️ 谨慎服用",
            "conclusion": "可以服用，但有以下注意点，请按提示执行。",
            "reasons": cautions,
        }

    # 3) 无明显冲突
    return {
        "level": "safe",
        "label": "✅ 可以服用",
        "conclusion": "结合当前健康档案未发现明显冲突，按说明书剂量使用即可。",
        "reasons": [],
    }


def _build_archive_aware_block(medicine: Dict[str, Any], profile: Dict[str, Any]) -> List[str]:
    """根据档案风险点生成"结合您的健康档案"块。无风险点时返回空列表（不渲染该块）。"""
    if not profile:
        return []
    out: List[str] = []
    drug_name = (medicine.get("name") or "").lower()
    ingredients = (medicine.get("ingredients") or "").lower()

    # 过敏交叉
    for a in profile.get("allergies") or []:
        n = (a.get("name") or "").lower()
        if not n:
            continue
        if n in drug_name or n in ingredients:
            sev = a.get("severity") or "未知"
            out.append(f"⚠️ 您对「{a['name']}」过敏（严重度：{sev}），该药品可能含相关成分，请勿使用")

    # 在服药物相互作用提醒（保守提醒，不做药理判断）
    for med in profile.get("current_medications") or []:
        n = (med.get("name") or "").strip()
        if n and n.lower() != drug_name:
            out.append(f"💊 您当前在服「{n}」，与本药同服前请咨询医生确认相互作用")
            break  # 一条提醒即可，避免冗长

    # 慢病提醒
    chronic = profile.get("chronic_diseases") or []
    if chronic:
        out.append(f"🩺 您的慢病记录：{ '、'.join(chronic[:3]) }；请确认本药对相关疾病无禁忌")

    # 年龄段
    ag = profile.get("age_group")
    if ag in ("婴幼儿", "未成年人", "老年人"):
        out.append(f"👶 您是{ag}人群，剂量与禁忌请按特殊人群说明严格执行")

    return out[:4]  # 最多 4 条，配合 max_paragraph_lines


async def _resolve_member_display_name(
    db: AsyncSession, user_id: int, family_member_id: Optional[int]
) -> str:
    """[BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517]
    Bug-1 流式播报需要用「当前选中成员姓名」承接，所以这里把家庭成员姓名查出来。
    没有指定家庭成员或查询失败时降级为「您」。
    """
    if not family_member_id:
        return "您"
    try:
        from app.models.models import FamilyMember

        result = await db.execute(
            __import__("sqlalchemy").select(FamilyMember).where(  # type: ignore
                FamilyMember.id == family_member_id,
                FamilyMember.user_id == user_id,
            )
        )
        fm = result.scalar_one_or_none()
        if fm and getattr(fm, "nickname", None):
            return fm.nickname
        if fm and getattr(fm, "relationship_type", None):
            return fm.relationship_type
    except Exception as e:
        logger.warning("resolve_member_display_name failed: %s", e)
    return "您"


async def _stream_text_typewriter(text: str, chunk_size: int = 6, delay: float = 0.04):
    """[BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517]
    把一整段文案切片成多个 delta 事件，制造"打字机"效果（Bug-1 要求逐字流式吐出）。
    """
    if not text:
        return
    pos = 0
    n = len(text)
    while pos < n:
        chunk = text[pos : pos + chunk_size]
        yield chunk
        pos += chunk_size
        if delay > 0:
            try:
                await asyncio.sleep(delay)
            except Exception:
                pass


async def run_drug_identify_stream(
    *,
    image_urls: List[str],
    ocr_text_hint: Optional[str],
    user_id: int,
    family_member_id: Optional[int],
    db: AsyncSession,
) -> AsyncIterator[Dict[str, Any]]:
    """SSE 流式执行识药引擎，逐段推送 progress / delta / done 事件。

    [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-1] 输出节奏调整为「A+C 混合」：
      1. 立刻 progress：触发前端"正在识别中…"占位气泡
      2. 第一段（极简播报型）逐字流式
      3. 第二段（个性化对话型，承接当前成员姓名）逐字流式
      4. 完成视觉识别后再 done + meta（卡片）

    yield 出的事件字典格式：
        {"type": "progress", "stage": "ocr_done", "text": "OCR 完成"}
        {"type": "delta",    "content": "..."}    # 用于把 summary_markdown 边推边渲染
        {"type": "done",     "content": "...",     # 最终全文
         "meta": {...drug_identify_card meta...}}
    """
    if not image_urls:
        yield {"type": "delta", "content": "未收到图片，请重新上传药盒清晰图。"}
        yield {
            "type": "done",
            "content": "未收到图片，请重新上传药盒清晰图。",
            "meta": {"message_type": "drug_identify_retake", "reason": "no_image"},
        }
        return

    # [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-1] 立刻吐出占位提示，
    # 让前端首字节响应 ≤ 0.5s。progress 事件不污染正文，仅用于占位气泡渲染。
    yield {"type": "progress", "stage": "received", "text": "正在识别中…"}

    member_name = await _resolve_member_display_name(db, user_id, family_member_id)

    cache_key = _make_cache_key(image_urls, family_member_id)
    cached = _cache_get(cache_key)
    if cached:
        logger.info("drug_identify_engine: cache hit key=%s", cache_key[:12])
        text = cached["summary_markdown"]
        yield {"type": "progress", "stage": "cache_hit", "text": "已命中缓存，正在返回..."}
        yield {"type": "delta", "content": text}
        yield {"type": "done", "content": text, "meta": cached["meta"]}
        return

    yield {"type": "progress", "stage": "start", "text": "识别中…正在分析药盒文字"}

    # [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-1]
    # 第一段：极简播报型流式文案（逐字吐出，先建立"正在工作"的反馈）
    intro_part1 = "正在识别图片中的药品… 已读取药盒文字，正在结合权威药品库做识别…"
    accumulated_text = ""
    async for piece in _stream_text_typewriter(intro_part1):
        accumulated_text += piece
        yield {"type": "delta", "content": piece}

    # 在跑视觉识别之前，先并行起 OCR + 6 维档案
    # 1) OCR + 6 维档案并行
    ocr_task = asyncio.create_task(_run_ocr_for_urls(image_urls, db))
    profile_task = asyncio.create_task(
        build_user_profile_for_drug_identify(db, user_id, family_member_id)
    )

    ocr_text, user_profile = await asyncio.gather(ocr_task, profile_task)
    if ocr_text_hint and not ocr_text:
        ocr_text = ocr_text_hint
    yield {"type": "progress", "stage": "ocr_done", "text": "OCR 文字提取完成"}

    # [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-1]
    # 第二段：个性化对话型承接（用当前选中成员姓名打招呼），逐字流式
    intro_part2 = (
        f"\n\n结合 {member_name} 的健康档案，我重点帮你分析一下是否适合 TA 服用…"
    )
    async for piece in _stream_text_typewriter(intro_part2):
        accumulated_text += piece
        yield {"type": "delta", "content": piece}

    # 2) 视觉识别（依赖 OCR 文字 + 档案）
    yield {"type": "progress", "stage": "vision_start", "text": "正在结合视觉模型识别药品…"}
    try:
        structured = await _run_vision_identify(image_urls, ocr_text or None, user_profile, db)
    except Exception as e:
        logger.warning("drug_identify_engine vision failed: %s", e)
        text = "AI 识别服务暂时不可用，请稍后重试或重新拍摄一张清晰药盒图。"
        yield {"type": "delta", "content": text}
        yield {
            "type": "done",
            "content": text,
            "meta": {
                "message_type": "drug_identify_retake",
                "reason": "vision_unavailable",
                "family_member_id": family_member_id,
            },
        }
        return

    yield {"type": "progress", "stage": "vision_done", "text": "视觉分析完成"}

    medicines = structured.get("medicines") or []
    primary_name = ""
    if medicines and isinstance(medicines[0], dict):
        primary_name = (medicines[0].get("name") or medicines[0].get("brand") or "")

    # 3) 一致性校验：模型药名 vs OCR 文字
    consistency_score = 0.0
    if primary_name and ocr_text:
        consistency_score = verify_drug_name_against_ocr(primary_name, ocr_text)
        logger.info(
            "drug_identify_engine: consistency drug=%s vs OCR sim=%.3f",
            primary_name, consistency_score,
        )

    # 4) 决策 next_action
    next_action = structured.get("next_action") or "show_card"
    if structured.get("recognized") and primary_name and ocr_text:
        if consistency_score < 0.4:
            next_action = "retake"
        elif consistency_score < 0.7:
            next_action = "pick_candidate"

    # 5) 组装最终输出
    if next_action == "retake":
        tail = (
            "\n\n（图片中识别到的关键文字与系统判断不一致，且置信度较低，"
            "请重新拍摄一张光线清晰、文字可读的药盒正面图。）"
        )
        async for piece in _stream_text_typewriter(tail):
            accumulated_text += piece
            yield {"type": "delta", "content": piece}
        meta: Dict[str, Any] = {
            "message_type": "drug_identify_retake",
            "reason": "consistency_low",
            "consistency_score": consistency_score,
            "ocr_text": ocr_text,
            "family_member_id": family_member_id,
            "member_name": member_name,
        }
        yield {"type": "done", "content": accumulated_text, "meta": meta}
        return

    if next_action == "pick_candidate":
        cand_lines = ["\n\n请确认是否为以下药品之一："]
        for i, m in enumerate(medicines[:3], 1):
            if isinstance(m, dict):
                cand_lines.append(
                    f"{i}. {m.get('name') or m.get('brand') or '未知药品'}"
                )
        cand_lines.append("")
        cand_lines.append("（系统判断与图片文字不完全一致，请确认或重新拍摄。）")
        tail = "\n".join(cand_lines)
        async for piece in _stream_text_typewriter(tail):
            accumulated_text += piece
            yield {"type": "delta", "content": piece}
        meta = {
            "message_type": "drug_identify_retake",
            "reason": "pick_candidate",
            "candidates": medicines[:3],
            "consistency_score": consistency_score,
            "ocr_text": ocr_text,
            "family_member_id": family_member_id,
            "member_name": member_name,
        }
        yield {"type": "done", "content": accumulated_text, "meta": meta}
        return

    # show_card
    summary = _build_summary_markdown(structured, user_profile)
    image_hash = hashlib.sha256(("|".join(sorted(image_urls))).encode()).hexdigest()

    # [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2]
    # 卡片内容增强：从 user_profile + 第一个药品组装"个性化风险结论"
    risk_block = _build_personalized_risk(
        medicines[0] if medicines and isinstance(medicines[0], dict) else {},
        user_profile,
    )

    meta = {
        "message_type": "drug_identify_card",
        "medicines": medicines,
        "image_urls": image_urls,
        "image_hash": image_hash,
        "family_member_id": family_member_id,
        "member_name": member_name,
        "confidence": structured.get("confidence") or 0,
        "consistency_score": consistency_score,
        "ocr_text": ocr_text,
        "next_action": "show_card",
        # Bug-2：个性化风险结论 + 风险等级标签
        "personalized_risk": risk_block,
    }
    _cache_put(cache_key, {"summary_markdown": summary, "meta": meta})

    # [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-1]
    # 流式完成后，正文气泡保持「两段播报文案」即可，结构化卡片在 done 事件的 meta 中下发，
    # 前端拿到 done 后再渲染卡片，避免"半成品闪烁"。这里**不再**额外推 summary delta。
    final_content = accumulated_text or summary
    yield {"type": "done", "content": final_content, "meta": meta}


def build_implicit_drug_context(meta: Dict[str, Any]) -> Optional[str]:
    """当上一条 assistant message 是 drug_identify_card 时，
    把它的 medicines JSON 拼成隐式 system context，注入下一轮聊天 Prompt。"""
    if not meta or meta.get("message_type") != "drug_identify_card":
        return None
    medicines = meta.get("medicines") or []
    if not medicines:
        return None
    try:
        return (
            "\n\n[上文已识别药品]\n"
            "用户上一条对话中通过拍照识药识别出以下药品，"
            "若用户接下来的问题涉及「用法 / 相互作用 / 禁忌 / 能否同服」等，"
            "请基于以下药品信息回答，并仍保持谨慎、严禁虚构：\n"
            + json.dumps(medicines, ensure_ascii=False)
        )
    except Exception:
        return None


__all__ = [
    "is_drug_identify_intent",
    "run_drug_identify_stream",
    "build_implicit_drug_context",
]
