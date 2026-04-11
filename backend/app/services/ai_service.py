import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import AIModelConfig

logger = logging.getLogger(__name__)


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
            async with httpx.AsyncClient(timeout=120.0) as client:
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


async def identify_drug_from_image(image_description: str, db: Optional[AsyncSession] = None) -> str:
    system_prompt = (
        "你是一位专业的药学AI顾问。用户提供了药品的图片描述信息，"
        "请尝试识别该药品，并提供相关信息。"
    )
    messages = [{"role": "user", "content": f"药品图片描述: {image_description}"}]
    return await call_ai_model(messages, system_prompt, db)


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
