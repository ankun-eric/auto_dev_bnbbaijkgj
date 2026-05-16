import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import AIModelConfig

logger = logging.getLogger(__name__)

# [BUG_FIX_用药识别千图一答 2026-05-16] 多模态视觉支持
# 该正则用于从纯文本 content 中扫描图片 URL，并自动升级为 OpenAI 多模态 content 数组，
# 让"纯文本"接口（如 chat 流）也能在用户上传图片时让模型真正"看见"图片，
# 而非把图片 URL 当成普通字符串发给文本模型——后者正是"千图一答"Bug 的根因。
_IMAGE_URL_RE = re.compile(
    r"(https?://[^\s\u4e00-\u9fff\)\]\}><\"'，。、；：！？]+?\.(?:png|jpe?g|gif|webp|bmp|heic|heif|tiff))",
    re.IGNORECASE,
)


def extract_image_urls(text: str) -> List[str]:
    """从一段文本中按顺序提取图片 URL（去重，保持出现顺序）。

    判断标准：以 http/https 开头且以常见图片后缀结尾。这是对前端
    `pickAndUploadThenSend` 把 OSS/COS 图片 URL 拼进 content 的兜底解析。
    """
    if not text or not isinstance(text, str):
        return []
    seen = set()
    urls: List[str] = []
    for m in _IMAGE_URL_RE.finditer(text):
        u = m.group(1)
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def build_vision_message_content(text: str, image_urls: List[str]) -> Union[str, List[Dict[str, Any]]]:
    """把「文本 + 图片 URL 列表」组装为 OpenAI 兼容的多模态 content 数组。

    - 无图片：返回原文本（保持纯文本协议向后兼容）
    - 有图片：返回 [{type:"image_url",image_url:{url}}*, {type:"text",text}]
              图片放在前面，文本放最后，遵循主流视觉模型最佳实践
    """
    if not image_urls:
        return text or ""
    parts: List[Dict[str, Any]] = []
    for url in image_urls:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    if text:
        parts.append({"type": "text", "text": text})
    return parts


def upgrade_messages_to_multimodal(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """遍历 messages，将所有 user 消息的 content 中"裸图片 URL"自动升级为多模态结构。

    输入示例（旧）：
        {"role":"user","content":"[用户上传的图片 1 张]\n1. https://x/a.jpg\n\n请帮我识别"}
    升级后：
        {"role":"user","content":[
            {"type":"image_url","image_url":{"url":"https://x/a.jpg"}},
            {"type":"text","text":"...原始文本..."}
        ]}

    若 content 已经是 list（调用方已经主动构造好多模态结构），原样保留。
    """
    upgraded: List[Dict[str, Any]] = []
    for m in messages or []:
        role = m.get("role")
        content = m.get("content")
        # 仅对 user 消息做扫描升级；system / assistant 消息照原样
        if role != "user" or not isinstance(content, str):
            upgraded.append(m)
            continue
        urls = extract_image_urls(content)
        if not urls:
            upgraded.append(m)
            continue
        new_content = build_vision_message_content(content, urls)
        upgraded.append({**m, "content": new_content})
    return upgraded


async def _get_active_model_config(db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    if db:
        result = await db.execute(select(AIModelConfig).where(AIModelConfig.is_active == True))
        config = result.scalar_one_or_none()
        if config:
            return {
                "base_url": config.base_url,
                "model": config.model_name,
                "api_key": config.api_key_encrypted or "",
                "max_tokens": config.max_tokens or 4096,
                "temperature": config.temperature if config.temperature is not None else 0.7,
            }
    return {
        "base_url": settings.AI_BASE_URL,
        "model": settings.AI_MODEL_NAME,
        "api_key": settings.AI_API_KEY,
        "max_tokens": 4096,
        "temperature": 0.7,
    }


async def call_ai_model(
    messages: List[Dict[str, str]],
    system_prompt: str = "",
    db: Optional[AsyncSession] = None,
    return_usage: bool = False,
) -> Any:
    """Call the AI model.

    When *return_usage* is True the function returns a dict:
        {"content": str, "model": str, "usage": {"prompt_tokens": int, "completion_tokens": int} | None}
    Otherwise it returns a plain string (backward compatible).
    """
    config = await _get_active_model_config(db)
    if not config["base_url"] or not config["model"]:
        fallback = "AI服务未配置，请联系管理员配置AI模型。"
        if return_usage:
            return {"content": fallback, "model": config["model"], "usage": None}
        return fallback

    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    # [BUG_FIX_用药识别千图一答 2026-05-16] 自动把 user 消息里裸图片 URL 升级为多模态结构，
    # 让模型真正"看见"图片，而不是只读到一段网址字符串然后凭空编一个常见药。
    all_messages = upgrade_messages_to_multimodal(all_messages)

    url = config["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config["api_key"]:
        headers["Authorization"] = f"Bearer {config['api_key']}"

    payload = {
        "model": config["model"],
        "messages": all_messages,
        "temperature": float(config.get("temperature", 0.7)),
        "max_tokens": int(config.get("max_tokens", 4096)),
    }

    max_attempts = 3
    retry_delay = 2
    last_exception: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                if return_usage:
                    usage = data.get("usage")
                    return {
                        "content": content,
                        "model": config["model"],
                        "usage": usage,
                    }
                return content
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            last_exception = e
            logger.warning(
                "AI model call attempt %d/%d failed (url=%s, model=%s): %s",
                attempt, max_attempts, url, config["model"], e,
            )
            if attempt < max_attempts:
                await asyncio.sleep(retry_delay)
        except httpx.HTTPStatusError as e:
            last_exception = e
            logger.error(
                "AI model call HTTP error (url=%s, model=%s, status=%s): %s",
                url, config["model"], e.response.status_code, e,
            )
            if e.response.status_code >= 500 and attempt < max_attempts:
                await asyncio.sleep(retry_delay)
                continue
            break
        except Exception as e:
            last_exception = e
            logger.error(
                "AI model call unexpected error (url=%s, model=%s): %s",
                url, config["model"], e, exc_info=True,
            )
            break

    error_msg = f"AI服务调用失败: {str(last_exception)}"
    logger.error("AI model call failed after %d attempts: %s", max_attempts, last_exception)
    if return_usage:
        return {"content": error_msg, "model": config["model"], "usage": None}
    raise Exception(error_msg)


async def call_ai_model_stream(
    messages: List[Dict[str, str]],
    system_prompt: str = "",
    db: Optional[AsyncSession] = None,
):
    """Yield SSE-compatible delta chunks from the AI model via streaming."""
    config = await _get_active_model_config(db)
    if not config["base_url"] or not config["model"]:
        yield {"type": "delta", "content": "AI服务未配置，请联系管理员配置AI模型。"}
        yield {"type": "done", "content": "AI服务未配置，请联系管理员配置AI模型。"}
        return

    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    # [BUG_FIX_用药识别千图一答 2026-05-16] 流式接口同样要做多模态升级
    all_messages = upgrade_messages_to_multimodal(all_messages)

    url = config["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config["api_key"]:
        headers["Authorization"] = f"Bearer {config['api_key']}"

    payload = {
        "model": config["model"],
        "messages": all_messages,
        "temperature": float(config.get("temperature", 0.7)),
        "max_tokens": int(config.get("max_tokens", 4096)),
        "stream": True,
    }

    full_content = ""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content_piece = delta.get("content", "")
                        if content_piece:
                            full_content += content_piece
                            yield {"type": "delta", "content": content_piece}
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue
        yield {"type": "done", "content": full_content}
    except Exception as e:
        logger.error("AI stream call failed: %s", e)
        error_msg = f"AI服务调用失败: {str(e)}"
        if not full_content:
            yield {"type": "delta", "content": error_msg}
        yield {"type": "done", "content": full_content or error_msg}


async def analyze_checkup_report(ocr_text: str, user_profile: Optional[Dict] = None, db: Optional[AsyncSession] = None) -> str:
    system_prompt = (
        "你是一位专业的健康顾问AI，擅长解读体检报告。请根据提供的体检报告OCR文本，"
        "分析各项指标，指出异常项，并给出健康建议。回复请用中文，结构清晰。"
    )
    profile_info = ""
    if user_profile:
        profile_info = f"\n用户信息: 性别{user_profile.get('gender','未知')}, 年龄相关生日{user_profile.get('birthday','未知')}, 身高{user_profile.get('height','未知')}cm, 体重{user_profile.get('weight','未知')}kg"

    messages = [{"role": "user", "content": f"请分析以下体检报告内容:\n{ocr_text}{profile_info}"}]
    return await call_ai_model(messages, system_prompt, db)


async def symptom_analysis(symptoms: str, history: Optional[str] = None, db: Optional[AsyncSession] = None) -> str:
    system_prompt = (
        "你是一位专业的AI健康助手，具备全科医学知识。用户将描述症状，请你进行初步分析，"
        "给出可能的病因、建议就诊科室和日常注意事项。声明仅供参考，不构成医疗诊断。"
    )
    content = f"我的症状是: {symptoms}"
    if history:
        content += f"\n既往病史: {history}"
    messages = [{"role": "user", "content": content}]
    return await call_ai_model(messages, system_prompt, db)


async def tcm_analysis(
    tongue_data: Optional[str] = None,
    face_data: Optional[str] = None,
    constitution_data: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> Dict[str, str]:
    system_prompt = (
        "你是一位资深的中医AI辨证专家，精通中医体质辨识、舌诊、面诊。"
        "请根据提供的信息进行综合辨证分析，判断体质类型，并给出调理建议。"
        "回复请用JSON格式: {\"constitution_type\": \"...\", \"tongue_analysis\": \"...\", "
        "\"face_analysis\": \"...\", \"syndrome_analysis\": \"...\", \"health_plan\": \"...\"}"
    )
    parts = []
    if tongue_data:
        parts.append(f"舌象描述: {tongue_data}")
    if face_data:
        parts.append(f"面色描述: {face_data}")
    if constitution_data:
        parts.append(f"体质问卷结果: {constitution_data}")

    messages = [{"role": "user", "content": "\n".join(parts) if parts else "请进行基础体质分析"}]
    result = await call_ai_model(messages, system_prompt, db)

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {
            "constitution_type": "待分析",
            "tongue_analysis": tongue_data or "",
            "face_analysis": face_data or "",
            "syndrome_analysis": result,
            "health_plan": "",
        }


async def drug_query(drug_name: str, user_profile: Optional[Dict] = None, db: Optional[AsyncSession] = None) -> str:
    system_prompt = (
        "你是一位专业的药学AI顾问。请根据用户查询的药品名称，提供药品的基本信息，"
        "包括主要成分、适应症、用法用量、不良反应、禁忌症、注意事项等。"
        "如果用户提供了个人健康信息，请结合其情况给出个性化建议。"
    )
    content = f"请查询药品: {drug_name}"
    if user_profile:
        allergies = user_profile.get("allergies", [])
        medications = user_profile.get("medications", [])
        if allergies:
            content += f"\n我的过敏史: {', '.join(allergies)}"
        if medications:
            content += f"\n我正在服用的药物: {', '.join(medications)}"
    messages = [{"role": "user", "content": content}]
    return await call_ai_model(messages, system_prompt, db)


async def generate_health_plan(user_profile: Dict[str, Any], plan_type: Optional[str] = None, goals: Optional[str] = None, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    system_prompt = (
        "你是一位专业的AI健康规划师。请根据用户的健康档案信息，生成个性化的健康计划。"
        "回复请用JSON格式: {\"plan_name\": \"...\", \"plan_type\": \"...\", "
        "\"content\": {\"overview\": \"...\", \"goals\": [...], \"daily_tasks\": [...]}, "
        "\"tasks\": [{\"task_name\": \"...\", \"task_type\": \"...\", \"task_time\": \"...\", \"points_reward\": 10}]}"
    )
    profile_str = json.dumps(user_profile, ensure_ascii=False, default=str)
    content = f"我的健康档案: {profile_str}"
    if plan_type:
        content += f"\n计划类型: {plan_type}"
    if goals:
        content += f"\n我的目标: {goals}"
    messages = [{"role": "user", "content": content}]
    result = await call_ai_model(messages, system_prompt, db)

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {
            "plan_name": plan_type or "健康计划",
            "plan_type": plan_type or "comprehensive",
            "content": {"overview": result, "goals": [], "daily_tasks": []},
            "tasks": [],
        }


async def ai_customer_service(message: str, context: Optional[List[Dict[str, str]]] = None, db: Optional[AsyncSession] = None) -> str:
    system_prompt = (
        "你是「宾尼小康」AI健康管家的智能客服助手。请热情友好地回答用户问题，"
        "涵盖平台功能介绍、服务咨询、订单问题、会员权益、健康知识等。"
        "如果问题超出你的能力范围，请建议用户转接人工客服。"
    )
    messages = context or []
    messages.append({"role": "user", "content": message})
    return await call_ai_model(messages, system_prompt, db)


async def drug_interaction_check(drugs: List[str], db: Optional[AsyncSession] = None) -> str:
    system_prompt = (
        "你是一位专业的药学AI顾问。请分析以下药物之间是否存在相互作用，"
        "包括药物-药物相互作用、是否可以同时服用、需要注意的时间间隔等。"
    )
    content = f"请检查以下药物的相互作用: {', '.join(drugs)}"
    messages = [{"role": "user", "content": content}]
    return await call_ai_model(messages, system_prompt, db)


async def identify_drug_from_image(
    image_description: str,
    db: Optional[AsyncSession] = None,
    image_urls: Optional[List[str]] = None,
    ocr_text: Optional[str] = None,
) -> str:
    """[BUG_FIX_用药识别千图一答 2026-05-16] 真正的"看图识药"接口。

    重构要点：
    1. 必须接受 ``image_urls`` 参数，把真正的图片 URL 通过 OpenAI 多模态 content
       数组发给模型，让模型能"看到"图片，而不是只看到一段文字描述。
    2. 同时允许传入 ``ocr_text``：先用 OCR 把药盒文字提取出来作为强信号，
       视觉特征 + 文字 双输入，识别准确率远高于"凭印象瞎猜"。
    3. 兼容性：若调用方没传 image_urls，则按旧版语义仅基于文本描述工作，
       但会从 image_description 里尝试再扫一遍 URL（兜底）。
    """
    # 兜底：如果调用方没明确传 image_urls，但 image_description 里能扫出 URL，自动捡起来
    auto_urls = extract_image_urls(image_description or "")
    final_urls = list(image_urls or []) + [u for u in auto_urls if u not in (image_urls or [])]

    system_prompt = (
        "你是一位资深的药品识别 AI 助手。用户上传了药盒/药品包装的真实图片，"
        "请基于图片中的视觉内容（包装外观、配色、Logo）和 OCR 文字（药名、规格、厂商、批号等），"
        "尽你所能识别出药品，并给出结构化、客观、谨慎的回答。\n\n"
        "## 必须遵守的输出规则\n"
        "1. 必须**真正基于图片中可见的内容**作答；如果图片不清晰、不是药品或无法识别，必须直接说明"
        "「无法识别，请重拍/换角度」，**严禁凭印象虚构常见药品**。\n"
        "2. 不同图片应给出不同的识别结果，不允许对所有图片返回完全相同的固定话术。\n"
        "3. 涉及处方药、特殊管制药品时必须额外提示"
        "「该药为处方药，请遵医嘱使用」。\n"
        "4. 结尾统一附加："
        "「AI 识别结果仅供参考，具体用药请遵医嘱」。\n\n"
        "## 推荐输出结构（Markdown）\n"
        "- 药品名称：通用名 / 商品名\n"
        "- 药品分类：处方药 / 非处方药 / 保健食品\n"
        "- 主要成分 / 规格\n"
        "- 适应症\n"
        "- 用法用量\n"
        "- 注意事项 / 禁忌\n"
    )

    # 组装用户消息：先把 OCR 文字 + 描述一并附上，再把图片以多模态形式塞进去
    user_text_parts: List[str] = []
    if ocr_text:
        user_text_parts.append(f"[OCR 识别到的药盒文字]\n{ocr_text}")
    if image_description and image_description.strip() and image_description not in user_text_parts:
        user_text_parts.append(image_description.strip())
    user_text_parts.append("请基于以上图片真实视觉内容和 OCR 文字识别此药品。如果不是药品图或看不清，请直接说明无法识别。")
    user_text = "\n\n".join(user_text_parts)

    if final_urls:
        # 直接构造多模态 content，确保不依赖 upgrade 兜底
        content: Union[str, List[Dict[str, Any]]] = build_vision_message_content(user_text, final_urls)
    else:
        content = user_text

    messages = [{"role": "user", "content": content}]
    return await call_ai_model(messages, system_prompt, db)


async def identify_drug_structured(
    image_urls: List[str],
    ocr_text: Optional[str] = None,
    user_profile: Optional[Dict[str, Any]] = None,
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """[BUG_FIX_用药识别千图一答 2026-05-16] 结构化多药识别接口。

    返回 dict 结构（参考修复方案 §4.2.④ MedicineRecognitionResult）：

    .. code-block:: json

        {
          "recognized": true,
          "confidence": 0.85,
          "medicines": [{
            "name": "...",
            "brand": "...",
            "spec": "...",
            "manufacturer": "...",
            "category": "...",
            "ingredients": "...",
            "usage": "...",
            "indications": "...",
            "precautions": "...",
            "contraindications": "..."
          }],
          "raw_ocr_text": "...",
          "next_action": "show_card" | "pick_candidate" | "retake",
          "summary_markdown": "...",
          "disclaimer": "..."
        }

    如果传入多张图，会综合所有图的视觉特征 + OCR 文字做联合识别，
    可识别同图多药或多图同药。
    """
    if not image_urls:
        return {
            "recognized": False,
            "confidence": 0.0,
            "medicines": [],
            "raw_ocr_text": ocr_text or "",
            "next_action": "retake",
            "summary_markdown": "未收到任何图片，请重新上传药盒图。",
            "disclaimer": "AI 识别结果仅供参考，具体用药请遵医嘱。",
        }

    system_prompt = (
        "你是一位资深的药品识别 AI 助手，具备视觉理解能力。"
        "用户上传了一张或多张药盒/药品包装的真实图片，"
        "请基于图片中的视觉内容（包装外观、配色、Logo、盒型）和 OCR 文字"
        "（药名、规格、厂商、批号）联合识别图中的所有药品。\n\n"
        "## 严格的输出协议\n"
        "你必须**只输出合法的 JSON**（不要 markdown 代码块标记，不要任何前后缀文字）。\n"
        "JSON 结构如下：\n"
        "{\n"
        '  "recognized": true | false,\n'
        '  "confidence": 0.0~1.0,\n'
        '  "medicines": [\n'
        "    {\n"
        '      "name": "药品通用名",\n'
        '      "brand": "商品名（如有）",\n'
        '      "spec": "规格，如 0.5g x 24 粒",\n'
        '      "manufacturer": "生产厂商",\n'
        '      "category": "处方药/非处方药/保健食品/其他",\n'
        '      "ingredients": "主要成分",\n'
        '      "usage": "用法用量",\n'
        '      "indications": "适应症",\n'
        '      "precautions": "注意事项",\n'
        '      "contraindications": "禁忌"\n'
        "    }\n"
        "  ],\n"
        '  "raw_ocr_text": "原始 OCR 文字（如有）",\n'
        '  "next_action": "show_card" | "pick_candidate" | "retake",\n'
        '  "summary_markdown": "面向用户的 Markdown 总结，供 AI 对话直接展示",\n'
        '  "disclaimer": "AI 识别结果仅供参考，具体用药请遵医嘱"\n'
        "}\n\n"
        "## 关键判断规则\n"
        "- 如果图片不清晰、不是药品、或视觉与 OCR 都无法支撑识别 → "
        "  `recognized=false`、`confidence<0.4`、`medicines=[]`、`next_action='retake'`、"
        "  `summary_markdown` 用一句话友好提示用户重拍/换角度。\n"
        "- 如果识别置信度不够高 → `next_action='pick_candidate'`，"
        "  在 medicines 数组里给出 2~3 个最像的候选，让用户确认。\n"
        "- 严禁在缺失视觉信息时虚构常见药品（如阿莫西林、布洛芬等）。\n"
        "- 不同输入图片应得出不同结果，绝不允许"
        "  对所有图片返回相同药品。\n"
        "- 若同一图含多个药品，medicines 应分别列出；多图同一药品则合并为一项。\n"
    )

    user_text_parts: List[str] = []
    if ocr_text:
        user_text_parts.append(f"[OCR 识别到的药盒文字]\n{ocr_text}")
    if user_profile:
        try:
            user_text_parts.append(
                f"[用户健康档案参考]\n{json.dumps(user_profile, ensure_ascii=False)}"
            )
        except Exception:
            pass
    user_text_parts.append(
        f"请识别以下 {len(image_urls)} 张图片中的药品，按系统要求的 JSON 协议返回。"
    )
    user_text = "\n\n".join(user_text_parts)

    content = build_vision_message_content(user_text, image_urls)
    messages = [{"role": "user", "content": content}]
    raw = await call_ai_model(messages, system_prompt, db)

    # 解析 JSON（带 markdown code fence 兜底）
    try:
        text = (raw or "").strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:] if lines else lines
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("not a dict")
    except Exception:
        # 兜底：解析失败时降级为 retake，给出可见的错误说明
        parsed = {
            "recognized": False,
            "confidence": 0.0,
            "medicines": [],
            "raw_ocr_text": ocr_text or "",
            "next_action": "retake",
            "summary_markdown": "AI 识别失败，请重新拍摄药盒清晰图后再试。",
            "disclaimer": "AI 识别结果仅供参考，具体用药请遵医嘱。",
            "raw_text": raw,
        }

    # 字段兜底
    parsed.setdefault("recognized", False)
    parsed.setdefault("confidence", 0.0)
    parsed.setdefault("medicines", [])
    parsed.setdefault("raw_ocr_text", ocr_text or "")
    parsed.setdefault("next_action", "retake")
    parsed.setdefault(
        "disclaimer",
        "AI 识别结果仅供参考，具体用药请遵医嘱。",
    )
    if not parsed.get("summary_markdown"):
        if parsed.get("recognized") and parsed.get("medicines"):
            lines = ["### 识别结果"]
            for i, m in enumerate(parsed["medicines"], 1):
                if not isinstance(m, dict):
                    continue
                lines.append(
                    f"**{i}. {m.get('name') or '未知药品'}**"
                    + (f"（{m['brand']}）" if m.get("brand") else "")
                )
                if m.get("spec"):
                    lines.append(f"- 规格：{m['spec']}")
                if m.get("category"):
                    lines.append(f"- 分类：{m['category']}")
                if m.get("indications"):
                    lines.append(f"- 适应症：{m['indications']}")
                if m.get("usage"):
                    lines.append(f"- 用法用量：{m['usage']}")
                if m.get("precautions"):
                    lines.append(f"- 注意事项：{m['precautions']}")
                if m.get("contraindications"):
                    lines.append(f"- 禁忌：{m['contraindications']}")
                lines.append("")
            lines.append(f"\n> {parsed['disclaimer']}")
            parsed["summary_markdown"] = "\n".join(lines)
        else:
            parsed["summary_markdown"] = (
                "未能识别出药品，请重新拍摄一张清晰的药盒正面图（光线明亮、避免反光、文字可读）后再试。"
            )

    return parsed


_ENHANCED_REPORT_PROMPT = (
    "你是一位专业的健康顾问AI，擅长解读体检报告。请根据提供的体检报告OCR文本，"
    "提取各项指标并给出结构化JSON解读结果。\n\n"
    "## 输出要求\n"
    "回复必须是且仅是合法JSON（不要包含 ```json 标记），严格遵循以下格式:\n"
    "{\n"
    '  "healthScore": {\n'
    '    "score": <0-100整数，综合健康评分>,\n'
    '    "level": "<优秀/良好/正常/偏低/较差>",\n'
    '    "comment": "<对整体健康状况的一句话评语>"\n'
    "  },\n"
    '  "summary": {\n'
    '    "totalItems": <检查项目总数>,\n'
    '    "abnormalCount": <异常项目数，riskLevel>=3>,\n'
    '    "excellentCount": <优秀项目数，riskLevel==1>,\n'
    '    "normalCount": <正常项目数，riskLevel==2>\n'
    "  },\n"
    '  "categories": [\n'
    "    {\n"
    '      "name": "分类名称（如血常规、肝功能等）",\n'
    '      "emoji": "<该分类对应的Emoji图标，如🩸、🫀、🦴、🧬、💉、🔬、🫁、🧪、👁️、🦷>",\n'
    '      "items": [\n'
    "        {\n"
    '          "name": "指标名称",\n'
    '          "value": "检测值",\n'
    '          "unit": "单位",\n'
    '          "referenceRange": "参考范围",\n'
    '          "riskLevel": <1-5整数>,\n'
    '          "riskName": "<优秀/正常/轻度异常/中度异常/严重异常>",\n'
    '          "detail": {\n'
    '            "explanation": "该指标的含义和作用（200-300字）",\n'
    '            "possibleCauses": "可能原因分析（200-300字）",\n'
    '            "dietAdvice": "饮食建议（200-300字）",\n'
    '            "exerciseAdvice": "运动建议（200-300字）",\n'
    '            "lifestyleAdvice": "生活方式建议（200-300字）",\n'
    '            "recheckAdvice": "复查建议",\n'
    '            "medicalAdvice": "就医建议，包括推荐科室"\n'
    "          }\n"
    "        }\n"
    "      ]\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "## 风险等级说明\n"
    "- 1=优秀：指标在最佳范围内\n"
    "- 2=正常：指标在参考范围内\n"
    "- 3=轻度异常：指标略超出参考范围\n"
    "- 4=中度异常：指标明显偏离参考范围\n"
    "- 5=严重异常：指标严重偏离，需要立即关注\n\n"
    "## Emoji映射参考\n"
    "血常规🩸 心脏🫀 肝功能🧪 肾功能💧 血脂🧈 血糖🍬 甲状腺🦋 "
    "肿瘤标志物🔬 尿常规🧫 骨骼🦴 肺功能🫁 眼科👁️ 口腔🦷 基因🧬\n\n"
    "## 重要\n"
    "- 每项detail中的建议字段请写200-300字，内容丰富具体\n"
    "- riskLevel为1或2时，detail可以简短或设为null\n"
    "- riskLevel为3-5时，detail的所有字段都必须填写\n"
    "- 综合评分应综合考虑所有异常项的严重程度"
)

_DEFAULT_DISCLAIMER = "以上解读仅供健康参考，不构成医疗诊断或治疗建议，如有异常请及时就医。"


async def analyze_report_structured(
    ocr_text: str,
    user_profile: Optional[Dict] = None,
    db: Optional[AsyncSession] = None,
    custom_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a structured JSON interpretation of a checkup report (enhanced format)."""
    system_prompt = custom_prompt or _ENHANCED_REPORT_PROMPT

    profile_info = ""
    if user_profile:
        profile_info = (
            f"\n用户信息: 性别{user_profile.get('gender','未知')}, "
            f"年龄相关生日{user_profile.get('birthday','未知')}, "
            f"身高{user_profile.get('height','未知')}cm, "
            f"体重{user_profile.get('weight','未知')}kg"
        )

    messages = [{"role": "user", "content": f"请结构化解读以下体检报告:\n{ocr_text}{profile_info}"}]
    result = await call_ai_model(messages, system_prompt, db)

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            first_nl = cleaned.index("\n")
            cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        parsed = {
            "healthScore": {"score": 0, "level": "待分析", "comment": result[:200] if result else "AI解析失败"},
            "summary": {"totalItems": 0, "abnormalCount": 0, "excellentCount": 0, "normalCount": 0},
            "categories": [],
        }

    if "disclaimer" not in parsed or not parsed.get("disclaimer"):
        parsed["disclaimer"] = _DEFAULT_DISCLAIMER

    return parsed


async def analyze_report_compare(
    report1_json: Dict,
    report2_json: Dict,
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Generate a comparison between two report analysis JSONs via AI."""
    system_prompt = (
        "你是一位专业的健康顾问AI。用户提供了两次体检报告的结构化JSON数据，"
        "请对比两次报告的各项指标变化，并生成结构化的对比分析。\n\n"
        "回复必须是且仅是合法JSON（不要包含 ```json 标记），格式如下:\n"
        "{\n"
        '  "aiSummary": "3-5句话总结两次体检的整体变化趋势",\n'
        '  "scoreDiff": {\n'
        '    "comment": "对评分变化的简短评语"\n'
        "  },\n"
        '  "indicators": [\n'
        "    {\n"
        '      "name": "指标名称",\n'
        '      "change": "变化描述，如 升高0.5、降低1.2、无变化",\n'
        '      "direction": "better/worse/same/new",\n'
        '      "suggestion": "针对该指标变化的个性化建议（改善的给予鼓励，恶化的给出行动建议）"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "direction字段说明:\n"
        "- better: 指标向好的方向变化\n"
        "- worse: 指标向差的方向变化\n"
        "- same: 基本无变化\n"
        "- new: 新增指标，上次没有\n"
    )

    data = json.dumps(
        {"previousReport": report1_json, "currentReport": report2_json},
        ensure_ascii=False,
        default=str,
    )
    messages = [{"role": "user", "content": f"请对比以下两次体检报告:\n{data}"}]
    result = await call_ai_model(messages, system_prompt, db)

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            first_nl = cleaned.index("\n")
            cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        parsed = {
            "aiSummary": result[:500] if result else "AI对比分析失败",
            "scoreDiff": None,
            "indicators": [],
        }

    return parsed


async def analyze_trend(
    indicator_name: str,
    trend_data: List[Dict[str, Any]],
    db: Optional[AsyncSession] = None,
) -> str:
    """AI trend analysis for a specific indicator over time."""
    system_prompt = (
        "你是一位专业的健康顾问AI。请根据用户某项体检指标的历史趋势数据，"
        "分析变化趋势，给出健康建议。回复用中文纯文本，不要用JSON。"
    )
    data_str = json.dumps(trend_data, ensure_ascii=False, default=str)
    messages = [
        {"role": "user", "content": f"请分析指标「{indicator_name}」的历史趋势:\n{data_str}"}
    ]
    return await call_ai_model(messages, system_prompt, db)
