"""
[PRD-432] AI 回答顶部「咨询对象档案」折叠卡片
- GET /api/v1/consultant/{id}/profile_card  返回卡片所需 7 项字段 + 完整度 + 最近更新时间 + 风险摘要
- GET /api/v1/consultant/{id}/medications   返回该咨询对象的长期用药列表（卡片抽屉用）

实现要点:
- 咨询对象 = FamilyMember（id 为 family_members.id）。本人 (is_self=True) 也是 FamilyMember。
- 7 项字段: 性别、年龄、身高、体重、既往病史、过敏史、长期用药
- "无" 标记: 通过新增字段 past_history_is_none / allergy_is_none / medication_is_none（表迁移在 main.py 启动时做）
- 长期用药使用现有 MedicationReminder 表 - 因当前未按 family_member 拆分，长期用药仅对本人 (is_self=True) 提供数据；
  对其他咨询对象暂返回空列表（前端会显示空状态）
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    FamilyMember,
    HealthProfile,
    MedicationReminder,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/consultant", tags=["咨询对象档案卡片 PRD-432"])


def _calc_age(birthday: Optional[date]) -> Optional[int]:
    if not birthday:
        return None
    today = date.today()
    age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    return max(age, 0)


async def _get_member_with_self_fallback(
    db: AsyncSession, user: User, consultant_id: int
) -> Optional[FamilyMember]:
    """
    返回该用户名下 family_member（含本人 is_self），若 consultant_id 为 0 则取本人。
    """
    if consultant_id == 0:
        result = await db.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == user.id,
                FamilyMember.is_self == True,  # noqa: E712
                FamilyMember.status == "active",
            )
        )
        return result.scalar_one_or_none()

    result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.id == consultant_id,
            FamilyMember.user_id == user.id,
        )
    )
    return result.scalar_one_or_none()


async def _get_health_profile(
    db: AsyncSession, user: User, member: FamilyMember
) -> Optional[HealthProfile]:
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == user.id,
            HealthProfile.family_member_id == member.id,
        )
    )
    hp = result.scalar_one_or_none()
    if hp:
        return hp
    if member.is_self:
        result = await db.execute(
            select(HealthProfile).where(
                HealthProfile.user_id == user.id,
                HealthProfile.family_member_id.is_(None),
            )
        )
        return result.scalar_one_or_none()
    return None


async def _get_long_term_meds(
    db: AsyncSession, user: User, member: FamilyMember
) -> List[Dict[str, Any]]:
    """
    长期用药列表。当前 MedicationReminder 仅按 user_id 维度，故仅对本人 (is_self=True) 返回数据；
    其他咨询对象返回空列表（前端走"未填写"分支）。
    """
    if not member.is_self:
        return []
    result = await db.execute(
        select(MedicationReminder)
        .where(
            MedicationReminder.user_id == user.id,
            MedicationReminder.status == "active",
        )
        .order_by(MedicationReminder.created_at.asc())
    )
    items: List[Dict[str, Any]] = []
    for r in result.scalars().all():
        days = 0
        if r.created_at:
            try:
                days = (datetime.utcnow() - r.created_at).days
            except Exception:
                days = 0
        freq_text = r.time_period or ""
        if r.remind_time:
            freq_text = f"{r.time_period or ''} {r.remind_time}".strip()
        items.append(
            {
                "id": r.id,
                "medicine_name": r.medicine_name or "",
                "dosage": r.dosage or "",
                "frequency": freq_text,
                "used_days": days,
            }
        )
    return items


def _ensure_dialect_flag_columns_synced() -> None:
    """no-op，表结构迁移由 main.py 启动钩子统一处理"""
    pass


def _build_summary_text(gender: Optional[str], age: Optional[int], past_history: List[str]) -> str:
    parts: List[str] = [gender if gender else "未填", f"{age}岁" if age is not None else "未填"]
    if past_history:
        first = past_history[0]
        rest = len(past_history) - 1
        if rest > 0:
            parts.append(f"{first} 等 {len(past_history)} 项")
        else:
            parts.append(first)
        text_full = "·".join(parts)
        if len(text_full) > 18 and len(past_history) > 1:
            parts[-1] = f"{first} 等 {len(past_history)} 项"
    return "·".join(parts)


def _to_history_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v).strip()]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        return [s]
    return [str(value)]


def _empty_self_profile_card_payload() -> Dict[str, Any]:
    """
    [PRD-448 v1.2 §4.3] 本人态档案兜底响应：
    当 id=0 但当前用户尚未建立 is_self=True 的 FamilyMember 或本人健康档案空白时，
    必须 200 + 返回基础结构体（name="本人" + 其他字段空），不能返回 404 / 空对象，
    否则前端会因 `!data` 走 `return null` 分支，导致本人态又看不到胶囊（回到老问题）。
    """
    return {
        "consultant_id": 0,
        "nickname": "本人",
        "avatar_url": "",
        "is_self": True,
        "fields": {
            "gender": {"value": "", "filled": False},
            "age": {"value": None, "filled": False},
            "height": {"value": "", "filled": False},
            "weight": {"value": "", "filled": False},
            "past_history": {"value": [], "filled": False, "is_none": False},
            "allergy": {"value": [], "filled": False, "is_none": False},
            "long_term_meds": {
                "value_brief": "",
                "count": 0,
                "filled": False,
                "is_none": False,
            },
        },
        "completeness": {"filled_count": 0, "total": 7, "percent": 0},
        "summary_text": "未填·未填",
        "last_updated_at": None,
        "updated_within_30d": False,
    }


@router.get("/{consultant_id}/profile_card")
async def get_profile_card(
    consultant_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    返回 PRD-432 「咨询对象档案折叠卡片」所需的全部数据。
    consultant_id=0 表示"本人"兜底。

    [PRD-448 v1.2] 本人态（id=0）档案兜底：当未建立本人 FamilyMember / 本人健康档案
    完全空白时，必须 200 + 返回基础结构体（name="本人" + 其他字段空），不能返回 404，
    否则前端 ProfileCard `!data` 分支会 return null，导致本人态胶囊不显示（回归老问题）。
    """
    member = await _get_member_with_self_fallback(db, current_user, consultant_id)
    if not member:
        # [PRD-448 v1.2 §4.3] 本人态兜底：id=0 且未建立 is_self=True 的 FamilyMember
        # 时不返 404，返回基础空结构，让前端胶囊正常渲染 + 显示"档案完整度 0%"引导。
        if consultant_id == 0:
            return _empty_self_profile_card_payload()
        raise HTTPException(status_code=404, detail="咨询对象不存在")

    hp = await _get_health_profile(db, current_user, member)

    gender = (hp.gender if hp else None) or member.gender
    birthday = (hp.birthday if hp else None) or member.birthday
    height_v = (hp.height if hp else None) or member.height
    weight_v = (hp.weight if hp else None) or member.weight

    raw_past = (hp.medical_histories if hp and hp.medical_histories else None) or member.medical_histories
    raw_allergy = (hp.allergies if hp and hp.allergies else None) or member.allergies
    past_list = _to_history_list(raw_past)
    allergy_list = _to_history_list(raw_allergy)

    # 读取 is_none 标记字段（容错：列不存在/无值时统一为 0）
    past_is_none = 0
    allergy_is_none = 0
    medication_is_none = 0
    try:
        if hp:
            row = await db.execute(
                text(
                    "SELECT past_history_is_none, allergy_is_none, medication_is_none "
                    "FROM health_profiles WHERE id = :id"
                ),
                {"id": hp.id},
            )
            r = row.first()
            if r:
                past_is_none = int(r[0] or 0)
                allergy_is_none = int(r[1] or 0)
                medication_is_none = int(r[2] or 0)
    except Exception as e:
        logger.debug(f"is_none flag columns missing or unreadable: {e}")

    meds = await _get_long_term_meds(db, current_user, member)

    age = _calc_age(birthday)

    age_filled = age is not None
    gender_filled = bool(gender)
    height_filled = bool(height_v)
    weight_filled = bool(weight_v)
    past_filled = bool(past_list) or bool(past_is_none)
    allergy_filled = bool(allergy_list) or bool(allergy_is_none)
    meds_filled = len(meds) > 0 or bool(medication_is_none)

    filled_count = sum(
        [
            1 if gender_filled else 0,
            1 if age_filled else 0,
            1 if height_filled else 0,
            1 if weight_filled else 0,
            1 if past_filled else 0,
            1 if allergy_filled else 0,
            1 if meds_filled else 0,
        ]
    )
    total = 7
    percent = int(round(filled_count / total * 100))

    summary_text = _build_summary_text(gender, age, past_list)

    last_updated_at: Optional[datetime] = None
    candidates = []
    if hp and hp.updated_at:
        candidates.append(hp.updated_at)
    if member.created_at:
        candidates.append(member.created_at)
    if candidates:
        last_updated_at = max(candidates)

    updated_within_30d = False
    if last_updated_at:
        try:
            updated_within_30d = (datetime.utcnow() - last_updated_at).days <= 30
        except Exception:
            updated_within_30d = False

    long_term_meds_value_brief = ""
    if medication_is_none and not meds:
        long_term_meds_value_brief = "无"
    elif meds:
        names = [m["medicine_name"] for m in meds if m.get("medicine_name")]
        if len(names) > 2:
            long_term_meds_value_brief = f"{', '.join(names[:2])} 等 {len(names)} 项"
        else:
            long_term_meds_value_brief = ", ".join(names)
    else:
        long_term_meds_value_brief = ""

    return {
        "consultant_id": member.id,
        "nickname": member.nickname or "本人",
        "avatar_url": "",
        "is_self": bool(member.is_self),
        "fields": {
            "gender": {"value": gender or "", "filled": gender_filled},
            "age": {"value": age, "filled": age_filled},
            "height": {
                "value": f"{int(height_v)}cm" if height_v else "",
                "filled": height_filled,
            },
            "weight": {
                "value": f"{int(weight_v)}kg" if weight_v else "",
                "filled": weight_filled,
            },
            "past_history": {
                "value": past_list,
                "filled": past_filled,
                "is_none": bool(past_is_none),
            },
            "allergy": {
                "value": allergy_list,
                "filled": allergy_filled,
                "is_none": bool(allergy_is_none),
            },
            "long_term_meds": {
                "value_brief": long_term_meds_value_brief,
                "count": len(meds),
                "filled": meds_filled,
                "is_none": bool(medication_is_none),
            },
        },
        "completeness": {
            "filled_count": filled_count,
            "total": total,
            "percent": percent,
        },
        "summary_text": summary_text,
        "last_updated_at": last_updated_at.isoformat() + "Z" if last_updated_at else None,
        "updated_within_30d": updated_within_30d,
    }


@router.get("/{consultant_id}/medications")
async def get_consultant_medications(
    consultant_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    PRD-432 长期用药抽屉所需的列表。
    """
    member = await _get_member_with_self_fallback(db, current_user, consultant_id)
    if not member:
        raise HTTPException(status_code=404, detail="咨询对象不存在")

    items = await _get_long_term_meds(db, current_user, member)

    medication_is_none = 0
    try:
        result = await db.execute(
            select(HealthProfile).where(
                HealthProfile.user_id == current_user.id,
                HealthProfile.family_member_id == member.id,
            )
        )
        hp = result.scalar_one_or_none()
        if hp:
            row = await db.execute(
                text("SELECT medication_is_none FROM health_profiles WHERE id = :id"),
                {"id": hp.id},
            )
            r = row.first()
            if r:
                medication_is_none = int(r[0] or 0)
    except Exception:
        pass

    return {
        "consultant_id": member.id,
        "nickname": member.nickname or "本人",
        "items": items,
        "is_none": bool(medication_is_none),
        "total": len(items),
    }


@router.put("/{consultant_id}/profile_flags")
async def update_profile_flags(
    consultant_id: int,
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新"无"标记: past_history_is_none / allergy_is_none / medication_is_none。
    payload 形如 {"past_history_is_none": 1, "allergy_is_none": 0, "medication_is_none": 1}
    """
    member = await _get_member_with_self_fallback(db, current_user, consultant_id)
    if not member:
        raise HTTPException(status_code=404, detail="咨询对象不存在")

    hp = await _get_health_profile(db, current_user, member)
    if not hp:
        hp = HealthProfile(user_id=current_user.id, family_member_id=member.id)
        db.add(hp)
        await db.flush()

    fields = ("past_history_is_none", "allergy_is_none", "medication_is_none")
    sets = []
    params: Dict[str, Any] = {"id": hp.id}
    for f in fields:
        if f in payload:
            sets.append(f"{f} = :{f}")
            params[f] = 1 if payload.get(f) else 0
    if sets:
        try:
            await db.execute(
                text(f"UPDATE health_profiles SET {', '.join(sets)} WHERE id = :id"),
                params,
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"update_profile_flags failed (column may be missing): {e}")
            raise HTTPException(status_code=500, detail="服务器繁忙，请稍后再试")

    return {"message": "ok", "consultant_id": member.id}
