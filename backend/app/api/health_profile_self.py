"""
[PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人健康档案完善——弹窗与抽屉对应后端接口

PRD 要点：
- GET  /api/health-profile/self  ：返回本人档案 + needComplete + missingFields
- PUT  /api/health-profile/self  ：保存本人档案，强校验 name/gender/birthday 三项必填
- name 占位文案"本人"等视为空；可与历史 /api/health/profile 接口共存
"""
from datetime import date, datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import HealthProfile, User

router = APIRouter(prefix="/api/health-profile", tags=["健康档案-本人完善"])


# ── 占位姓名（视为空） ──
PLACEHOLDER_NAMES = {"本人", "我", "self", "Self", "ME", "Me", "me", ""}


class HealthProfileSelfUpdate(BaseModel):
    """[PRD §7.2] 本人档案完善保存请求"""
    name: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[date] = None
    avatar: Optional[str] = None
    phone: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    blood_type: Optional[str] = None
    # 折叠区其它选填字段（兼容已有 schema）
    smoking: Optional[str] = None
    drinking: Optional[str] = None
    exercise_habit: Optional[str] = None
    sleep_habit: Optional[str] = None
    diet_habit: Optional[str] = None
    chronic_diseases: Optional[List[Any]] = None
    medical_histories: Optional[List[Any]] = None
    allergies: Optional[List[Any]] = None
    genetic_diseases: Optional[List[Any]] = None


def _is_name_empty(name: Optional[str]) -> bool:
    """[PRD §3] name 为空或为占位文案 视为空"""
    if name is None:
        return True
    stripped = str(name).strip()
    if not stripped:
        return True
    if stripped in PLACEHOLDER_NAMES:
        return True
    return False


def _compute_missing_fields(profile: Optional[HealthProfile]) -> List[str]:
    """[PRD §3] 计算缺失字段（仅看 health_profiles 本人那条），保留作为 v2 内部步骤
    [BUG_FIX 2026-05-29] 该函数仍保留供 v2 复用与回滚开关；接口默认走 v2。
    """
    missing: List[str] = []
    if profile is None:
        return ["name", "gender", "birthday"]
    if _is_name_empty(profile.name):
        missing.append("name")
    if not profile.gender or not str(profile.gender).strip():
        missing.append("gender")
    if profile.birthday is None:
        missing.append("birthday")
    return missing


async def _compute_missing_fields_v2(
    db: AsyncSession,
    user_id: int,
    profile: Optional[HealthProfile],
) -> List[str]:
    """[BUG_FIX 2026-05-29] 放宽判定：跨 health_profiles / family_members(is_self) / users 取并集

    任一来源补齐字段即视为"已完善"，避免旧用户因数据落库位置差异被误弹。
    判定口径仍要求 name/gender/birthday 三项均非空，仅放宽**取数来源**。
    """
    name_ok = bool(profile is not None and not _is_name_empty(profile.name))
    gender_ok = bool(profile is not None and profile.gender and str(profile.gender).strip())
    birthday_ok = bool(profile is not None and profile.birthday is not None)

    if not (name_ok and gender_ok and birthday_ok):
        try:
            from app.models.models import FamilyMember
            result = await db.execute(
                select(FamilyMember).where(
                    FamilyMember.user_id == user_id,
                    FamilyMember.is_self.is_(True),
                )
            )
            sm = result.scalar_one_or_none()
            if sm is not None:
                if not name_ok and sm.nickname and not _is_name_empty(sm.nickname):
                    name_ok = True
                if not gender_ok and sm.gender and str(sm.gender).strip():
                    gender_ok = True
                if not birthday_ok and sm.birthday is not None:
                    birthday_ok = True
        except Exception:
            pass

    if not (name_ok and gender_ok and birthday_ok):
        try:
            result = await db.execute(select(User).where(User.id == user_id))
            u = result.scalar_one_or_none()
            if u is not None:
                if not name_ok:
                    rn = getattr(u, "real_name", None) or getattr(u, "nickname", None)
                    if rn and not _is_name_empty(rn):
                        name_ok = True
                if not gender_ok and getattr(u, "gender", None):
                    gender_ok = True
                if not birthday_ok and getattr(u, "birthday", None) is not None:
                    birthday_ok = True
        except Exception:
            pass

    missing: List[str] = []
    if not name_ok:
        missing.append("name")
    if not gender_ok:
        missing.append("gender")
    if not birthday_ok:
        missing.append("birthday")
    return missing


async def _serialize_profile_v2(
    db: AsyncSession, profile: Optional[HealthProfile], current_user: User
) -> dict:
    """[BUG_FIX 2026-05-29] 异步序列化版本：missing 计算走 v2 跨表并集"""
    missing = await _compute_missing_fields_v2(db, current_user.id, profile)
    if profile is None:
        return {
            "id": f"u_{current_user.id}",
            "name": "本人",
            "gender": None,
            "birthday": None,
            "avatar": "",
            "phone": current_user.phone or "",
            "height": None,
            "weight": None,
            "blood_type": None,
            "needComplete": len(missing) > 0,
            "missingFields": missing,
        }
    name_for_display = profile.name if profile.name else "本人"
    return {
        "id": f"u_{current_user.id}",
        "profile_id": profile.id,
        "name": name_for_display,
        "gender": profile.gender,
        "birthday": profile.birthday.isoformat() if profile.birthday else None,
        "avatar": "",
        "phone": current_user.phone or "",
        "height": profile.height,
        "weight": profile.weight,
        "blood_type": profile.blood_type,
        "smoking": profile.smoking,
        "drinking": profile.drinking,
        "exercise_habit": profile.exercise_habit,
        "sleep_habit": profile.sleep_habit,
        "diet_habit": profile.diet_habit,
        "chronic_diseases": profile.chronic_diseases or [],
        "medical_histories": profile.medical_histories or [],
        "allergies": profile.allergies or [],
        "genetic_diseases": profile.genetic_diseases or [],
        "needComplete": len(missing) > 0,
        "missingFields": missing,
    }


def _serialize_profile(profile: Optional[HealthProfile], current_user: User) -> dict:
    """[PRD §7.1] 序列化本人档案 + needComplete + missingFields"""
    if profile is None:
        return {
            "id": f"u_{current_user.id}",
            "name": "本人",
            "gender": None,
            "birthday": None,
            "avatar": "",
            "phone": current_user.phone or "",
            "height": None,
            "weight": None,
            "blood_type": None,
            "needComplete": True,
            "missingFields": ["name", "gender", "birthday"],
        }
    missing = _compute_missing_fields(profile)
    name_for_display = profile.name if profile.name else "本人"
    return {
        "id": f"u_{current_user.id}",
        "profile_id": profile.id,
        "name": name_for_display,
        "gender": profile.gender,
        "birthday": profile.birthday.isoformat() if profile.birthday else None,
        "avatar": "",
        "phone": current_user.phone or "",
        "height": profile.height,
        "weight": profile.weight,
        "blood_type": profile.blood_type,
        "smoking": profile.smoking,
        "drinking": profile.drinking,
        "exercise_habit": profile.exercise_habit,
        "sleep_habit": profile.sleep_habit,
        "diet_habit": profile.diet_habit,
        "chronic_diseases": profile.chronic_diseases or [],
        "medical_histories": profile.medical_histories or [],
        "allergies": profile.allergies or [],
        "genetic_diseases": profile.genetic_diseases or [],
        "needComplete": len(missing) > 0,
        "missingFields": missing,
    }


async def _get_self_profile(db: AsyncSession, user_id: int) -> Optional[HealthProfile]:
    """获取本人健康档案：family_member_id IS NULL 的那一条"""
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == user_id,
            HealthProfile.family_member_id.is_(None),
        )
    )
    return result.scalar_one_or_none()


@router.get("/self")
async def get_self_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §7.1] 获取本人健康档案 + needComplete + missingFields

    返回字段说明：
    - needComplete：name/gender/birthday 任一为空（含 name=="本人" 占位）即为 true
    - missingFields：缺失字段名列表
    """
    profile = await _get_self_profile(db, current_user.id)
    # [BUG_FIX 2026-05-29] 走 v2 跨三表（health_profiles / family_members(is_self) / users）取并集
    data = await _serialize_profile_v2(db, profile, current_user)
    return {"code": 0, "data": data}


@router.put("/self")
async def update_self_profile(
    data: HealthProfileSelfUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD §7.2] 保存本人健康档案，强校验 name/gender/birthday 三项必填"""
    field_errors: dict = {}
    name_raw = data.name
    if _is_name_empty(name_raw):
        field_errors["name"] = "请填写姓名"
    else:
        nstrip = str(name_raw).strip()
        if len(nstrip) > 20:
            field_errors["name"] = "姓名长度需 1~20"

    if not data.gender or str(data.gender).strip() not in {"男", "女", "male", "female", "M", "F"}:
        field_errors["gender"] = "请选择性别"

    if data.birthday is None:
        field_errors["birthday"] = "请选择出生日期"
    else:
        today = date.today()
        if data.birthday > today:
            field_errors["birthday"] = "出生日期不能晚于今天"
        elif data.birthday < date(1900, 1, 1):
            field_errors["birthday"] = "出生日期不能早于 1900-01-01"

    if field_errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "请补全必填字段", "field_errors": field_errors},
        )

    # 性别归一化：保留中文男/女，便于和现有 HeroCard / member 接口一致
    gender_in = str(data.gender).strip()
    if gender_in in {"male", "M"}:
        gender_norm = "男"
    elif gender_in in {"female", "F"}:
        gender_norm = "女"
    else:
        gender_norm = gender_in

    profile = await _get_self_profile(db, current_user.id)
    if profile is None:
        profile = HealthProfile(user_id=current_user.id, family_member_id=None)
        db.add(profile)

    profile.name = str(name_raw).strip()
    profile.gender = gender_norm
    profile.birthday = data.birthday

    # 可选字段
    optional_fields = [
        "height", "weight", "blood_type",
        "smoking", "drinking", "exercise_habit", "sleep_habit", "diet_habit",
        "chronic_diseases", "medical_histories", "allergies", "genetic_diseases",
    ]
    payload = data.model_dump(exclude_unset=True)
    for f in optional_fields:
        if f in payload:
            setattr(profile, f, payload[f])

    profile.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(profile)

    # 同步本人 FamilyMember.nickname / gender / birthday，使本人 Tab 名变更生效
    try:
        from app.models.models import FamilyMember
        result = await db.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == current_user.id,
                FamilyMember.is_self.is_(True),
            )
        )
        self_member = result.scalar_one_or_none()
        if self_member is not None:
            self_member.nickname = profile.name
            if profile.gender:
                self_member.gender = profile.gender
            if profile.birthday:
                self_member.birthday = profile.birthday
            await db.flush()
    except Exception:
        pass

    # [BUG_FIX 2026-05-29] 保存后用 v2 重算，与 GET 接口口径一致
    missing = await _compute_missing_fields_v2(db, current_user.id, profile)
    profile_data = await _serialize_profile_v2(db, profile, current_user)
    return {
        "code": 0,
        "data": {
            "needComplete": len(missing) > 0,
            "missingFields": missing,
            "profile": profile_data,
        },
    }
