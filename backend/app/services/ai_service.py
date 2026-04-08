import json
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import AIModelConfig


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

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
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
    except Exception as e:
        fallback = f"AI服务调用失败: {str(e)}"
        if return_usage:
            return {"content": fallback, "model": config["model"], "usage": None}
        return fallback


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


async def analyze_report_structured(
    ocr_text: str,
    user_profile: Optional[Dict] = None,
    db: Optional[AsyncSession] = None,
    custom_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a structured JSON interpretation of a checkup report."""
    system_prompt = custom_prompt or (
        "你是一位专业的健康顾问AI，擅长解读体检报告。请根据提供的体检报告OCR文本，"
        "提取各项指标并给出结构化JSON解读结果。\n"
        "回复必须是合法JSON，格式如下:\n"
        "{\n"
        '  "categories": [{"category_name": "分类名", "indicators": [{"name": "指标名", '
        '"value": "数值", "unit": "单位", "reference_range": "参考范围", '
        '"status": "normal/abnormal/critical", "advice": "异常建议"}]}],\n'
        '  "abnormal_indicators": [同上indicator格式],\n'
        '  "normal_indicators": [同上indicator格式],\n'
        '  "overall_assessment": "总体评估文字",\n'
        '  "suggestions": ["建议1", "建议2"],\n'
        '  "disclaimer": "以上解读仅供健康参考，不构成医疗诊断或治疗建议，如有异常请及时就医。"\n'
        "}"
    )

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
        parsed = json.loads(result)
    except json.JSONDecodeError:
        parsed = {
            "categories": [],
            "abnormal_indicators": [],
            "normal_indicators": [],
            "overall_assessment": result,
            "suggestions": [],
            "disclaimer": "以上解读仅供健康参考，不构成医疗诊断或治疗建议，如有异常请及时就医。",
        }

    if "disclaimer" not in parsed or not parsed["disclaimer"]:
        parsed["disclaimer"] = "以上解读仅供健康参考，不构成医疗诊断或治疗建议，如有异常请及时就医。"

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
