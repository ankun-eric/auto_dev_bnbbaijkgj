"""[BUG-HSC-FIX-V2-20260521] B-7 通用占位符渲染器

设计要点：
- 21 项占位符全量清单（含 10 项新增）
- 取不到值时**统一渲染为 "未填写"**（不报错、不抛异常）
- placeholder catalog 元数据用于前端速查表（admin-web 编辑抽屉）
- 完全无状态、纯函数实现

支持的占位符（key / label / scope_tag / source / example）：
  通用：user_name/user_gender/user_age/family_member_name/family_member_relation
       /family_member_age/family_member_gender/health_profile
  档案类：chronic_diseases/allergies/medications/surgery_history/family_history
        /height/weight/bmi/blood_type
  仅健康自查：body_parts/symptoms/duration/description
  分型：main_type/secondary_types/scores（沿用旧的 _render_business_placeholders）
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional


PLACEHOLDER_UNFILLED = "未填写"


# ─────────────────────────────────────────────────────────────────
# 占位符元数据：供 admin-web 编辑抽屉的速查表使用
# ─────────────────────────────────────────────────────────────────
PLACEHOLDER_CATALOG: list[dict[str, str]] = [
    # 通用
    {"key": "user_name", "label": "本人姓名", "scope_tag": "通用", "source": "user.nickname", "example": "张小白"},
    {"key": "user_gender", "label": "本人性别", "scope_tag": "通用", "source": "user.gender", "example": "男"},
    {"key": "user_age", "label": "本人年龄", "scope_tag": "通用", "source": "user.birthday 推算", "example": "32"},
    {"key": "family_member_name", "label": "家人姓名", "scope_tag": "通用", "source": "family_members.nickname", "example": "妈妈"},
    {"key": "family_member_relation", "label": "与本人关系", "scope_tag": "通用", "source": "family_members.relationship_type", "example": "母亲"},
    {"key": "family_member_age", "label": "家人年龄", "scope_tag": "通用", "source": "family_members.birthday 推算", "example": "58"},
    {"key": "family_member_gender", "label": "家人性别", "scope_tag": "通用", "source": "family_members.gender", "example": "女"},
    # 档案类
    {"key": "chronic_diseases", "label": "慢病列表", "scope_tag": "档案类", "source": "health_profile.chronic_diseases", "example": "高血压、糖尿病"},
    {"key": "allergies", "label": "过敏史", "scope_tag": "档案类", "source": "health_profile.allergies", "example": "青霉素、海鲜"},
    {"key": "medications", "label": "长期用药", "scope_tag": "档案类", "source": "health_profile.medications", "example": "氨氯地平 5mg/日"},
    {"key": "surgery_history", "label": "手术史", "scope_tag": "档案类", "source": "health_profile.surgery_history", "example": "2018 年阑尾切除"},
    {"key": "family_history", "label": "家族病史", "scope_tag": "档案类", "source": "health_profile.family_history", "example": "父亲糖尿病"},
    {"key": "height", "label": "身高 cm", "scope_tag": "档案类", "source": "health_profile.height", "example": "175"},
    {"key": "weight", "label": "体重 kg", "scope_tag": "档案类", "source": "health_profile.weight", "example": "68"},
    {"key": "bmi", "label": "BMI", "scope_tag": "档案类", "source": "height/weight 计算", "example": "22.2"},
    {"key": "blood_type", "label": "血型", "scope_tag": "档案类", "source": "health_profile.blood_type", "example": "O 型"},
    {"key": "health_profile", "label": "健康档案摘要", "scope_tag": "通用", "source": "health_profile 汇总", "example": "32 岁 男 / BMI 22.2 / 慢病：无"},
    # 仅健康自查
    {"key": "body_parts", "label": "本次自查部位", "scope_tag": "仅健康自查", "source": "本次问卷答题", "example": "腹部"},
    {"key": "symptoms", "label": "本次自查症状", "scope_tag": "仅健康自查", "source": "本次问卷答题", "example": "胀痛、反酸"},
    {"key": "duration", "label": "持续时间", "scope_tag": "仅健康自查", "source": "本次问卷答题", "example": "2 天"},
    {"key": "description", "label": "用户补充描述", "scope_tag": "仅健康自查", "source": "本次问卷答题", "example": "受凉后加重"},
]


def _safe(val: Any) -> str:
    """统一空值兜底：None / 空字符串 / 空列表 → 未填写。"""
    if val is None:
        return PLACEHOLDER_UNFILLED
    if isinstance(val, str):
        s = val.strip()
        return s or PLACEHOLDER_UNFILLED
    if isinstance(val, (list, tuple)):
        items = [str(x).strip() for x in val if x is not None and str(x).strip()]
        return "、".join(items) if items else PLACEHOLDER_UNFILLED
    if isinstance(val, dict):
        if not val:
            return PLACEHOLDER_UNFILLED
        parts = [f"{k}:{v}" for k, v in val.items() if v not in (None, "")]
        return "；".join(parts) if parts else PLACEHOLDER_UNFILLED
    return str(val) if str(val).strip() else PLACEHOLDER_UNFILLED


def _calc_age(birthday: Any) -> Optional[int]:
    """从 birthday（date / datetime / 'YYYY-MM-DD'）推算年龄。"""
    if not birthday:
        return None
    try:
        if isinstance(birthday, datetime):
            b = birthday.date()
        elif isinstance(birthday, date):
            b = birthday
        elif isinstance(birthday, str):
            b = datetime.strptime(birthday[:10], "%Y-%m-%d").date()
        else:
            return None
        today = date.today()
        age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        return age if age >= 0 else None
    except Exception:  # noqa: BLE001
        return None


def _calc_bmi(height_cm: Any, weight_kg: Any) -> Optional[float]:
    try:
        if not height_cm or not weight_kg:
            return None
        h = float(height_cm) / 100.0
        w = float(weight_kg)
        if h <= 0 or w <= 0:
            return None
        return round(w / (h * h), 1)
    except Exception:  # noqa: BLE001
        return None


def build_placeholder_values(
    *,
    user: Any = None,
    family_member: Any = None,
    health_profile: Any = None,
    hsc_answer_fields: Optional[list[dict[str, Any]]] = None,
) -> dict[str, str]:
    """构造 21 项占位符的最终字符串值。取不到的统一返回"未填写"。

    参数：
      - user: User ORM 对象（含 nickname / gender / birthday 等）
      - family_member: FamilyMember ORM 对象（含 nickname / relationship_type / gender / birthday 等）
      - health_profile: dict-like 或 ORM 对象（含 chronic_diseases / allergies / medications / surgery_history / family_history / height / weight / blood_type）
      - hsc_answer_fields: list[{label, value}] 健康自查答题的字段列表
    """
    v: dict[str, str] = {}

    # 通用 — 本人
    v["user_name"] = _safe(getattr(user, "nickname", None))
    v["user_gender"] = _safe(getattr(user, "gender", None))
    v["user_age"] = _safe(_calc_age(getattr(user, "birthday", None)))

    # 通用 — 家人
    if family_member is not None:
        v["family_member_name"] = _safe(getattr(family_member, "nickname", None))
        v["family_member_relation"] = _safe(getattr(family_member, "relationship_type", None))
        v["family_member_gender"] = _safe(getattr(family_member, "gender", None))
        v["family_member_age"] = _safe(_calc_age(getattr(family_member, "birthday", None)))
    else:
        v["family_member_name"] = PLACEHOLDER_UNFILLED
        v["family_member_relation"] = PLACEHOLDER_UNFILLED
        v["family_member_gender"] = PLACEHOLDER_UNFILLED
        v["family_member_age"] = PLACEHOLDER_UNFILLED

    # 档案类
    def _hp(key: str) -> Any:
        if health_profile is None:
            return None
        if isinstance(health_profile, dict):
            return health_profile.get(key)
        return getattr(health_profile, key, None)

    height_val = _hp("height")
    weight_val = _hp("weight")
    v["chronic_diseases"] = _safe(_hp("chronic_diseases"))
    v["allergies"] = _safe(_hp("allergies"))
    v["medications"] = _safe(_hp("medications"))
    v["surgery_history"] = _safe(_hp("surgery_history"))
    v["family_history"] = _safe(_hp("family_history"))
    v["height"] = _safe(height_val)
    v["weight"] = _safe(weight_val)
    bmi = _calc_bmi(height_val, weight_val)
    v["bmi"] = _safe(bmi)
    v["blood_type"] = _safe(_hp("blood_type"))

    # 健康档案摘要：拼接核心信息
    summary_parts: list[str] = []
    if v["user_age"] != PLACEHOLDER_UNFILLED:
        summary_parts.append(f"{v['user_age']}岁")
    if v["user_gender"] != PLACEHOLDER_UNFILLED:
        summary_parts.append(v["user_gender"])
    if v["bmi"] != PLACEHOLDER_UNFILLED:
        summary_parts.append(f"BMI {v['bmi']}")
    if v["chronic_diseases"] != PLACEHOLDER_UNFILLED:
        summary_parts.append(f"慢病：{v['chronic_diseases']}")
    if v["allergies"] != PLACEHOLDER_UNFILLED:
        summary_parts.append(f"过敏：{v['allergies']}")
    v["health_profile"] = " / ".join(summary_parts) if summary_parts else PLACEHOLDER_UNFILLED

    # 仅健康自查
    f_map: dict[str, str] = {}
    for f in hsc_answer_fields or []:
        label = (f.get("label") or "").strip()
        val = f.get("value")
        if isinstance(val, list):
            val_s = "、".join(str(x) for x in val if x is not None and str(x) != "")
        else:
            val_s = "" if val is None else str(val)
        if label:
            f_map[label] = val_s
    v["body_parts"] = _safe(f_map.get("部位"))
    v["symptoms"] = _safe(f_map.get("症状") or f_map.get("主症状"))
    v["duration"] = _safe(f_map.get("持续时间"))
    v["description"] = _safe(f_map.get("备注") or f_map.get("症状补充备注") or f_map.get("补充描述"))

    return v


def render(text: Optional[str], values: dict[str, str]) -> Optional[str]:
    """把 text 里的 {key} 替换为 values[key]，未匹配的占位符保留不变。"""
    if not text:
        return text
    out = text
    for k, val in (values or {}).items():
        if not k:
            continue
        out = out.replace("{" + k + "}", "" if val is None else str(val))
    return out


def render_with_context(
    text: Optional[str],
    *,
    user: Any = None,
    family_member: Any = None,
    health_profile: Any = None,
    hsc_answer_fields: Optional[list[dict[str, Any]]] = None,
) -> Optional[str]:
    """便捷封装：一次性构造 values 并渲染。"""
    if not text:
        return text
    values = build_placeholder_values(
        user=user,
        family_member=family_member,
        health_profile=health_profile,
        hsc_answer_fields=hsc_answer_fields,
    )
    return render(text, values)
