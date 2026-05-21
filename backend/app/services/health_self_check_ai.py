"""[PRD-HSC-AI-REAL-V1 2026-05-21] 健康自查 AI 解读服务

负责将健康自查答卷转换为结构化的 AI 解读：组装上下文 → 替换占位符 → 调 LLM
→ 解析 JSON → 失败兜底降级。

接入策略：
- 使用 `app.services.ai_service.call_ai_model(...)`，与 AI 对话首页同一套配置
  （`ai_model_configs` 表中 `is_active=True` 的模型）。
- 模板从 `questionnaire_template.ai_prompt_template` 取（运营/医生可后台配置）。
- 占位符统一为中文，正文与速查表保持一致。

输出协议（与 prompt 约束一致）：
    {
        "interpretation": "...",
        "home_care_tips": ["..."],
        "red_flags": ["..."]
    }

兜底策略：
- LLM 调用失败 / JSON 解析失败 → 调 `build_fallback_template(context)` 返回基于
  用户填写部位/症状的轻定制确定性模板，状态置 'degraded'。
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ─── A+++ 关键字段集合（仅这些字段变化才提示 profile_outdated） ───
PROFILE_KEY_FIELDS = ["age", "gender", "chronic_diseases", "allergies", "medications", "family_history"]

# ─── 中文占位符匹配（含中文字符、字母、数字、下划线） ───
_ZH_PLACEHOLDER_RE = re.compile(r"\{([\u4e00-\u9fa5A-Za-z0-9_]+)\}")


def render_zh_placeholders(template: str, context: Dict[str, Any]) -> str:
    """中文占位符替换器。找不到的 key 保留原样，便于运营排查。"""
    if not template:
        return ""

    def _sub(m: re.Match) -> str:  # type: ignore[type-arg]
        key = m.group(1)
        v = context.get(key)
        if v is None:
            return m.group(0)
        return str(v)

    return _ZH_PLACEHOLDER_RE.sub(_sub, template)


# ─── 工具函数 ───

def _join_or_none(value: Any) -> str:
    """将 JSON 字段（list/str/None）拼接为可读字符串，空则返回"无"。"""
    if value is None or value == "" or value == []:
        return "无"
    if isinstance(value, list):
        items = [str(x).strip() for x in value if x is not None and str(x).strip()]
        if not items:
            return "无"
        return "、".join(items)
    if isinstance(value, dict):
        items = [f"{k}:{v}" for k, v in value.items() if v]
        if not items:
            return "无"
        return "、".join(items)
    s = str(value).strip()
    return s or "无"


def _calc_age(birth: Any) -> Optional[int]:
    if not birth:
        return None
    try:
        if isinstance(birth, datetime):
            bd = birth.date()
        elif isinstance(birth, date):
            bd = birth
        elif isinstance(birth, str):
            bd = datetime.strptime(birth[:10], "%Y-%m-%d").date()
        else:
            return None
        today = date.today()
        years = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        return years if years >= 0 else None
    except Exception:  # noqa: BLE001
        return None


def _safe_json_loads(raw: str) -> Optional[dict]:
    """容错解析：剥离 ```json``` 包装。返回 dict 或 None。"""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        # 剥离 ``` 或 ```json
        lines = text.split("\n")
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return None
    except Exception:  # noqa: BLE001
        # 二次尝试：截取首个 { ... } 块
        try:
            start = text.find("{")
            end = text.rfind("}")
            if 0 <= start < end:
                data = json.loads(text[start : end + 1])
                if isinstance(data, dict):
                    return data
        except Exception:  # noqa: BLE001
            pass
        return None


# ─── 档案与答卷上下文加载 ───

async def load_health_profile(db: AsyncSession, user_id: int) -> Optional[Any]:
    try:
        from app.models.models import UserHealthProfile
        row = (
            await db.execute(
                select(UserHealthProfile).where(UserHealthProfile.user_id == user_id)
            )
        ).scalar_one_or_none()
        return row
    except Exception as e:  # noqa: BLE001
        logger.warning("load_health_profile(user_id=%s) failed: %s", user_id, e)
        return None


def snapshot_key_fields(profile: Optional[Any], *, age: Optional[int], gender: Optional[str]) -> Dict[str, Any]:
    """生成关键字段快照（用于 A+++ 比对）。"""
    if profile is None:
        return {
            "age": age,
            "gender": gender,
            "chronic_diseases": None,
            "allergies": None,
            "medications": None,
            "family_history": None,
        }
    return {
        "age": age,
        "gender": gender,
        "chronic_diseases": getattr(profile, "chronic_diseases", None),
        "allergies": getattr(profile, "allergies", None),
        "medications": getattr(profile, "medications", None),
        "family_history": getattr(profile, "family_history", None),
    }


def is_profile_outdated(current: Dict[str, Any], snapshot: Optional[Dict[str, Any]]) -> bool:
    """A+++ 比对：关键字段变化才算 outdated；快照为空 / 全等 → False。"""
    if not snapshot or not isinstance(snapshot, dict):
        return False
    try:
        for k in PROFILE_KEY_FIELDS:
            if current.get(k) != snapshot.get(k):
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _extract_body_part_and_symptoms(answers: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    """从 answer items 抽取 部位 / 症状列表 / 持续时间。

    答题 item 形如 {dimension:"部位"/"症状"/"持续时间"/..., value: "xxx" or [..]}
    """
    body_part = ""
    symptoms: List[str] = []
    duration = ""
    for item in answers or []:
        dim = (item.get("dimension") or item.get("title") or "").strip()
        val = item.get("value")
        if isinstance(val, list):
            disp = "、".join(str(v) for v in val if v is not None and str(v) != "")
        elif val is None:
            disp = ""
        else:
            disp = str(val)
        if not disp:
            continue
        if dim in ("部位", "身体部位"):
            body_part = disp
        elif dim in ("症状", "症状列表"):
            symptoms.append(disp)
        elif dim in ("持续时间", "时长"):
            duration = disp
        elif dim in ("性质", "严重程度", "备注"):
            symptoms.append(f"{dim}：{disp}")
    return body_part or "未填写", "；".join(symptoms) if symptoms else "未填写", duration or "未填写"


# ─── 兜底模板 ───

def build_fallback_template(context: Dict[str, Any]) -> Dict[str, Any]:
    """AI 失败 / JSON 解析失败时的确定性兜底模板。

    与 prompt 约束的输出协议字段一致：interpretation / home_care_tips / red_flags
    并根据用户填写的部位/症状做关键词替换，避免完全无关。
    """
    bp = context.get("部位") or "症状部位"
    sym = context.get("症状列表") or "您描述的症状"
    dur = context.get("持续时间") or "持续时间"

    interpretation = (
        f"本次健康自查针对【{bp}】的不适已被系统记录，主要症状描述为：{sym}（{dur}）。\n\n"
        "结合一般临床经验，类似不适常见原因可能与：\n"
        "1. 局部劳损、姿势不当或受凉；\n"
        "2. 近期作息、饮食、情绪波动；\n"
        "3. 既往慢性病或药物副作用；\n"
        "4. 偶发性的功能紊乱等相关。\n\n"
        "建议先按下方「居家处理建议」尝试 1~3 天自我调节；"
        "若症状持续无改善、明显加重或出现下方「就医警示」中的红线信号，"
        "请及时前往正规医疗机构就诊，进行进一步评估。"
    )

    home_care_tips = [
        f"今日起减少{bp}相关的高强度活动，保证 7-8 小时充足睡眠",
        "饮食清淡，避免辛辣、油炸、酒精与咖啡因",
        f"根据{bp}症状性质选择对应方式：热敷 / 冷敷 / 休息 / 抬高患处",
        "每 2-4 小时给症状重新打分（0-10），观察趋势",
        "如确诊基础病，请按既往医嘱继续治疗，记录症状变化",
    ]
    red_flag_signals = [
        f"{bp}症状持续 2 周以上无改善",
        f"{bp}症状明显影响日常工作、学习、睡眠",
        "出现剧烈疼痛、意识模糊、持续呕吐、剧烈头痛等急性表现",
        "服药后无效或出现皮疹、心悸、严重胃肠道反应",
        "老人 / 儿童 / 孕妇 / 慢病患者出现该新症状",
    ]
    return {
        "interpretation": interpretation,
        "home_care_tips": home_care_tips,
        "red_flags": red_flag_signals,
    }


# ─── 主流程：生成 AI 解读 ───

async def build_context(
    db: AsyncSession,
    *,
    user_id: int,
    answer: Any,
    subject_name: str,
    subject_member: Optional[Any] = None,
    current_user: Optional[Any] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """组装 prompt 上下文 + 关键字段快照。

    返回 (context_dict, snapshot_dict)。
    """
    profile = await load_health_profile(db, user_id)

    # 年龄 / 性别：优先取家人档案；缺则取当前用户
    age: Optional[int] = None
    gender: Optional[str] = None
    if subject_member is not None:
        bd = (
            getattr(subject_member, "birthday", None)
            or getattr(subject_member, "birth_date", None)
        )
        age = _calc_age(bd)
        if not age and getattr(subject_member, "age", None):
            try:
                age = int(subject_member.age)  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001
                age = None
        gender = getattr(subject_member, "gender", None)
    if (not age) and current_user is not None:
        bd2 = getattr(current_user, "birth_date", None) or getattr(current_user, "birthday", None)
        age = _calc_age(bd2)
    if (not gender) and current_user is not None:
        gender = getattr(current_user, "gender", None)

    # 答题信息
    body_part, symptoms, duration = _extract_body_part_and_symptoms(answer.answers or [])

    context: Dict[str, Any] = {
        "档案信息": subject_name or "用户",
        "档案年龄": str(age) if age is not None else "未填写",
        "档案性别": gender or "未填写",
        "档案既往病史": _join_or_none(getattr(profile, "chronic_diseases", None) if profile else None),
        "档案过敏史": _join_or_none(getattr(profile, "allergies", None) if profile else None),
        "档案在用药物": _join_or_none(getattr(profile, "medications", None) if profile else None),
        "档案家族病史": _join_or_none(getattr(profile, "family_history", None) if profile else None),
        "部位": body_part,
        "症状列表": symptoms,
        "持续时间": duration,
    }

    snapshot = snapshot_key_fields(profile, age=age, gender=gender)
    return context, snapshot


async def call_ai_for_interpretation(
    db: AsyncSession,
    *,
    prompt: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """调用大模型并解析 JSON。

    返回 (parsed_dict, raw_text or err_msg)：
    - 成功：(dict, raw_text)
    - 失败：(None, err_msg)
    """
    try:
        from app.services.ai_service import call_ai_model

        # 健康自查是结构化输出，温度可低一点；这里仍用模型默认值，不强行设置
        messages = [{"role": "user", "content": prompt}]
        raw = await call_ai_model(messages, system_prompt="", db=db)
    except Exception as e:  # noqa: BLE001
        logger.warning("[hsc-ai] call_ai_model raised: %s", e)
        return None, f"AI 调用异常：{str(e)[:120]}"

    if not raw or not isinstance(raw, str):
        return None, "AI 返回为空"
    parsed = _safe_json_loads(raw)
    if parsed is None:
        return None, "AI 返回非合法 JSON"
    # 字段校验
    interp = parsed.get("interpretation")
    tips = parsed.get("home_care_tips")
    flags = parsed.get("red_flags")
    if not (isinstance(interp, str) and interp.strip()):
        return None, "AI 返回缺少 interpretation"
    if not (isinstance(tips, list) and len(tips) >= 1):
        return None, "AI 返回缺少 home_care_tips 数组"
    if not (isinstance(flags, list) and len(flags) >= 1):
        return None, "AI 返回缺少 red_flags 数组"
    # 规整：限制条数与长度
    tips_norm = [str(t).strip() for t in tips if str(t).strip()][:6]
    flags_norm = [str(f).strip() for f in flags if str(f).strip()][:6]
    return (
        {
            "interpretation": interp.strip(),
            "home_care_tips": tips_norm or [str(t) for t in tips][:6],
            "red_flags": flags_norm or [str(f) for f in flags][:6],
        },
        raw,
    )


__all__ = [
    "PROFILE_KEY_FIELDS",
    "render_zh_placeholders",
    "load_health_profile",
    "snapshot_key_fields",
    "is_profile_outdated",
    "build_context",
    "call_ai_for_interpretation",
    "build_fallback_template",
]
