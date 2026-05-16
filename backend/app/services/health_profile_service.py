"""[BUG_FIX_拍照识药三联_20260516] 拍照识药专用健康档案构建服务。

方案文档 §3.2 / §7.4.3：
- 旧版 ``user_profile`` 只用 ``gender / allergies / medications`` 三个字段
- 现在升级为 6 维全档案 JSON：年龄段 / 性别 / 慢病 / 过敏（含严重度）/ 在服药物（含剂量频率）/ 体质
- 优先按 ``family_member_id`` 取咨询人档案；缺失时降级为登录用户档案

输出供 Prompt 注入，让"结合您的健康档案"块能基于真实档案给出针对性提醒。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AllergyRecord,
    HealthProfile,
    MedicationRecord,
)


def _calc_age_group(birthday: Optional[date]) -> Optional[str]:
    if not birthday:
        return None
    try:
        today = date.today()
        age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    except Exception:
        return None
    if age < 0:
        return None
    if age < 6:
        return "婴幼儿"
    if age < 18:
        return "未成年人"
    if age < 60:
        return "成人"
    return "老年人"


def _normalize_chronic(diseases: Any) -> List[str]:
    if not diseases:
        return []
    if isinstance(diseases, str):
        return [s.strip() for s in diseases.split(",") if s.strip()]
    if isinstance(diseases, list):
        out: List[str] = []
        for item in diseases:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("disease") or item.get("title")
                if name:
                    out.append(str(name).strip())
        return out
    return []


async def _load_health_profile(
    db: AsyncSession, user_id: int, family_member_id: Optional[int]
) -> Optional[HealthProfile]:
    """优先取咨询人档案；缺失时降级为登录用户档案。"""
    if family_member_id:
        result = await db.execute(
            select(HealthProfile).where(
                HealthProfile.user_id == user_id,
                HealthProfile.family_member_id == family_member_id,
            )
        )
        hp = result.scalar_one_or_none()
        if hp:
            return hp
    # 兜底：登录用户自身档案（family_member_id IS NULL 的"本人"档案）
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == user_id,
            HealthProfile.family_member_id.is_(None),
        )
    )
    hp = result.scalar_one_or_none()
    if hp:
        return hp
    # 再兜底：随便挑一条该 user_id 下的档案
    result = await db.execute(
        select(HealthProfile).where(HealthProfile.user_id == user_id).limit(1)
    )
    return result.scalar_one_or_none()


async def build_user_profile_for_drug_identify(
    db: AsyncSession,
    user_id: int,
    family_member_id: Optional[int] = None,
) -> Dict[str, Any]:
    """构建拍照识药用的 6 维健康档案上下文。

    返回示例::

        {
          "age_group": "成人",
          "gender": "female",
          "chronic_diseases": ["高血压", "糖尿病"],
          "allergies": [
            {"name": "青霉素", "severity": "重度"}
          ],
          "current_medications": [
            {"name": "二甲双胍", "dose": "0.5g", "freq": "bid"}
          ],
          "tcm_constitution": null
        }

    任何字段缺失都会保持 None / [] ，不抛异常。
    """
    profile: Dict[str, Any] = {
        "age_group": None,
        "gender": None,
        "chronic_diseases": [],
        "allergies": [],
        "current_medications": [],
        "tcm_constitution": None,
    }
    try:
        hp = await _load_health_profile(db, user_id, family_member_id)
        if hp:
            profile["age_group"] = _calc_age_group(hp.birthday)
            profile["gender"] = hp.gender
            profile["chronic_diseases"] = _normalize_chronic(hp.chronic_diseases)
    except Exception:
        pass

    # 过敏：合并 allergy_records（带严重度）+ HealthProfile.drug_allergies/food_allergies/other_allergies 文本字段
    allergies: List[Dict[str, str]] = []
    try:
        result = await db.execute(
            select(AllergyRecord).where(AllergyRecord.user_id == user_id)
        )
        for a in result.scalars().all():
            allergies.append(
                {
                    "name": a.allergy_name,
                    "severity": a.severity or "未知",
                    "type": a.allergy_type or "",
                }
            )
    except Exception:
        pass
    try:
        if hp:
            for txt_attr, default_type in (
                ("drug_allergies", "药物"),
                ("food_allergies", "食物"),
                ("other_allergies", "其他"),
            ):
                txt = getattr(hp, txt_attr, None)
                if txt and isinstance(txt, str):
                    for raw in [s.strip() for s in txt.replace("、", ",").split(",") if s.strip()]:
                        if not any(a["name"] == raw for a in allergies):
                            allergies.append(
                                {"name": raw, "severity": "未知", "type": default_type}
                            )
    except Exception:
        pass
    profile["allergies"] = allergies

    # 在服药物：取 status == 'active' 的所有 MedicationRecord
    meds: List[Dict[str, str]] = []
    try:
        result = await db.execute(
            select(MedicationRecord).where(
                MedicationRecord.user_id == user_id,
                MedicationRecord.status == "active",
            )
        )
        for m in result.scalars().all():
            meds.append(
                {
                    "name": m.medicine_name,
                    "dose": m.dosage or "",
                    "freq": m.frequency or "",
                }
            )
    except Exception:
        pass
    profile["current_medications"] = meds

    return profile


__all__ = ["build_user_profile_for_drug_identify"]
