"""
[PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式页面优化 —— 后端支撑模块

本模块为关怀模式优化提供以下能力：
1. 紧急联系人维护（SOS 页「紧急联系人维护」入口）：CRUD
   - 联系人：姓名 + 关系（儿子/女儿/家庭医生等）+ 电话
2. 家庭住址维护（个人信息卡需要、HealthProfile 模型无 address 字段，单独存）
3. 个人信息卡聚合数据（GET /api/care-card/info）
   - 姓名/年龄/出生日期/性别 + 既往病史/过敏史（来自本人档案）+ 家庭住址 + 紧急联系人
4. 个人信息卡二维码：
   - GET  /api/care-card/qr-token  生成一个长期 token（指向本人）
   - GET  /api/care-card/public/{token}  无需鉴权，扫码网页读取卡片完整信息

设计说明：
- 紧急联系人 / 家庭住址用独立动态表（care_card_*），SQLAlchemy 自动建表，不改动既有模型。
- 既往病史/过敏史/姓名/性别/生日 复用本人健康档案（HealthProfile，family_member_id IS NULL）。
- 空字段不隐藏，由前端展示「暂无 / 未填写」，后端统一返回 None / 空列表。
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, get_db
from app.core.security import get_current_user

try:
    from app.models.models import HealthProfile, User  # type: ignore
except Exception:  # pragma: no cover
    HealthProfile = None  # type: ignore
    User = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["关怀模式-个人信息卡与紧急联系人-v1"])


# ───────────────────────── 动态表 ─────────────────────────
class CareEmergencyContact(Base):
    """关怀模式紧急联系人表"""

    __tablename__ = "care_emergency_contacts"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False)
    name = Column(String(64), nullable=False, default="")
    relation = Column(String(32), nullable=False, default="")  # 儿子/女儿/家庭医生...
    phone = Column(String(32), nullable=False, default="")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CareCardExtra(Base):
    """关怀模式个人信息卡补充信息（每用户一条）：家庭住址 + 卡片二维码 token"""

    __tablename__ = "care_card_extra"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, unique=True, nullable=False)
    home_address = Column(Text, default="")
    qr_token = Column(String(64), index=True, default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CareLocationShare(Base):
    """[PRD-CARE-MODE-OPTIM-V4] 静态位置分享记录（发出那一刻的位置，可微信转发好友）

    对方在微信打开小程序后，按 token 读取「静态位置（坐标 + 已解析的可读地址）+ 精简个人信息卡」。
    """

    __tablename__ = "care_location_shares"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False)
    token = Column(String(64), index=True, nullable=False)
    latitude = Column(String(32), default="")
    longitude = Column(String(32), default="")
    address = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)


# ───────────────────────── Pydantic ─────────────────────────
class ContactIn(BaseModel):
    name: Optional[str] = ""
    relation: Optional[str] = ""
    phone: Optional[str] = ""


class HomeAddressIn(BaseModel):
    home_address: Optional[str] = ""


class LocationShareIn(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = ""


# ───────────────────────── 工具函数 ─────────────────────────
def _calc_age(birthday: Optional[date]) -> Optional[int]:
    if not birthday:
        return None
    today = date.today()
    age = today.year - birthday.year - (
        (today.month, today.day) < (birthday.month, birthday.day)
    )
    return age if age >= 0 else None


def _flatten_text_list(items: Any) -> List[str]:
    """把 chronic_diseases / allergies 等 JSON 列表归一化为字符串列表。

    兼容三种形态：['高血压']、[{'name':'高血压'}]、'高血压,糖尿病'。
    """
    out: List[str] = []
    if items is None:
        return out
    if isinstance(items, str):
        for seg in items.replace("，", ",").split(","):
            seg = seg.strip()
            if seg:
                out.append(seg)
        return out
    if isinstance(items, list):
        for it in items:
            if it is None:
                continue
            if isinstance(it, str):
                s = it.strip()
                if s:
                    out.append(s)
            elif isinstance(it, dict):
                v = it.get("name") or it.get("label") or it.get("value") or it.get("text")
                if v and str(v).strip():
                    out.append(str(v).strip())
    return out


async def _get_self_profile(db: AsyncSession, user_id: int) -> Optional["HealthProfile"]:
    if HealthProfile is None:
        return None
    result = await db.execute(
        select(HealthProfile).where(
            HealthProfile.user_id == user_id,
            HealthProfile.family_member_id == 0,
        )
    )
    return result.scalars().first()


async def _get_or_create_extra(db: AsyncSession, user_id: int) -> CareCardExtra:
    res = await db.execute(
        select(CareCardExtra).where(CareCardExtra.user_id == user_id)
    )
    extra = res.scalar_one_or_none()
    if extra is None:
        extra = CareCardExtra(user_id=user_id, home_address="", qr_token=uuid.uuid4().hex)
        db.add(extra)
        await db.flush()
    if not extra.qr_token:
        extra.qr_token = uuid.uuid4().hex
        await db.flush()
    return extra


async def _list_contacts(db: AsyncSession, user_id: int) -> List[CareEmergencyContact]:
    res = await db.execute(
        select(CareEmergencyContact)
        .where(CareEmergencyContact.user_id == user_id)
        .order_by(CareEmergencyContact.sort_order.asc(), CareEmergencyContact.id.asc())
    )
    return list(res.scalars().all())


def _contact_dict(c: CareEmergencyContact) -> Dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name or "",
        "relation": c.relation or "",
        "phone": c.phone or "",
    }


async def _build_card_payload(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """聚合个人信息卡完整数据（供鉴权接口与公开网页共用）。"""
    profile = await _get_self_profile(db, user_id)
    extra = await _get_or_create_extra(db, user_id)
    contacts = await _list_contacts(db, user_id)

    name = None
    gender = None
    birthday_iso = None
    chronic: List[str] = []
    allergies: List[str] = []
    if profile is not None:
        name = profile.name if profile.name and profile.name != "本人" else None
        gender = profile.gender or None
        birthday_iso = profile.birthday.isoformat() if profile.birthday else None
        chronic = _flatten_text_list(getattr(profile, "chronic_diseases", None))
        # medical_histories 也并入既往病史展示
        chronic += _flatten_text_list(getattr(profile, "medical_histories", None))
        allergies = _flatten_text_list(getattr(profile, "allergies", None))
        # 兼容老字段
        allergies += _flatten_text_list(getattr(profile, "drug_allergies", None))
        allergies += _flatten_text_list(getattr(profile, "food_allergies", None))

    age = _calc_age(profile.birthday if profile else None)

    return {
        "name": name,
        "age": age,
        "birthday": birthday_iso,
        "gender": gender,
        "chronic_diseases": chronic,
        "allergies": allergies,
        "home_address": extra.home_address or None,
        "emergency_contacts": [_contact_dict(c) for c in contacts],
        "qr_token": extra.qr_token,
    }


# ───────────────────────── 紧急联系人 CRUD ─────────────────────────
@router.get("/api/care-card/contacts")
async def list_contacts(
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contacts = await _list_contacts(db, current_user.id)
    return {"code": 0, "data": {"items": [_contact_dict(c) for c in contacts]}}


@router.post("/api/care-card/contacts")
async def create_contact(
    data: ContactIn,
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    name = (data.name or "").strip()
    phone = (data.phone or "").strip()
    relation = (data.relation or "").strip()
    if not name and not phone:
        raise HTTPException(status_code=400, detail="姓名和电话不能同时为空")
    existing = await _list_contacts(db, current_user.id)
    contact = CareEmergencyContact(
        user_id=current_user.id,
        name=name,
        relation=relation,
        phone=phone,
        sort_order=len(existing),
    )
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return {"code": 0, "data": _contact_dict(contact)}


@router.put("/api/care-card/contacts/{contact_id}")
async def update_contact(
    contact_id: int,
    data: ContactIn,
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(CareEmergencyContact).where(
            CareEmergencyContact.id == contact_id,
            CareEmergencyContact.user_id == current_user.id,
        )
    )
    contact = res.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="联系人不存在")
    if data.name is not None:
        contact.name = data.name.strip()
    if data.relation is not None:
        contact.relation = data.relation.strip()
    if data.phone is not None:
        contact.phone = data.phone.strip()
    contact.updated_at = datetime.now()
    await db.flush()
    await db.refresh(contact)
    return {"code": 0, "data": _contact_dict(contact)}


@router.delete("/api/care-card/contacts/{contact_id}")
async def delete_contact(
    contact_id: int,
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(CareEmergencyContact).where(
            CareEmergencyContact.id == contact_id,
            CareEmergencyContact.user_id == current_user.id,
        )
    )
    contact = res.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="联系人不存在")
    await db.delete(contact)
    await db.flush()
    return {"code": 0, "data": {"deleted": contact_id}}


# ───────────────────────── 家庭住址 ─────────────────────────
@router.put("/api/care-card/home-address")
async def update_home_address(
    data: HomeAddressIn,
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    extra = await _get_or_create_extra(db, current_user.id)
    extra.home_address = (data.home_address or "").strip()
    extra.updated_at = datetime.now()
    await db.flush()
    return {"code": 0, "data": {"home_address": extra.home_address}}


# ───────────────────────── 个人信息卡聚合 ─────────────────────────
@router.get("/api/care-card/info")
async def get_card_info(
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = await _build_card_payload(db, current_user.id)
    return {"code": 0, "data": payload}


# ───────────────────────── 二维码 token ─────────────────────────
@router.get("/api/care-card/qr-token")
async def get_qr_token(
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    extra = await _get_or_create_extra(db, current_user.id)
    return {"code": 0, "data": {"token": extra.qr_token}}


# ───────────────────────── 公开网页（扫码，无需鉴权）─────────────────────────
@router.get("/api/care-card/public/{token}")
async def get_public_card(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """扫码后网页读取的完整卡片信息，无需登录。"""
    res = await db.execute(
        select(CareCardExtra).where(CareCardExtra.qr_token == token)
    )
    extra = res.scalar_one_or_none()
    if extra is None or not token:
        raise HTTPException(status_code=404, detail="卡片不存在或已失效")
    payload = await _build_card_payload(db, extra.user_id)
    # 公开网页不外泄 token
    payload.pop("qr_token", None)
    return {"code": 0, "data": payload}


# ───────────────────────── 位置分享（静态位置 + 精简信息卡）─────────────────────────
@router.post("/api/care-card/share-location")
async def create_location_share(
    data: LocationShareIn,
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[需求8.3] 生成一次性静态位置分享 token（发出那一刻的位置，更隐私可控）。

    返回 token，前端拼成可微信转发的小程序/网页链接。
    """
    token = uuid.uuid4().hex
    share = CareLocationShare(
        user_id=current_user.id,
        token=token,
        latitude="" if data.latitude is None else f"{data.latitude}",
        longitude="" if data.longitude is None else f"{data.longitude}",
        address=(data.address or "").strip(),
    )
    db.add(share)
    await db.flush()
    return {"code": 0, "data": {"token": token}}


@router.get("/api/care-card/share-location/{token}")
async def get_location_share(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """[需求8.3] 对方在微信打开后读取：静态位置（坐标 + 可读地址）+ 精简个人信息卡。无需登录。"""
    res = await db.execute(
        select(CareLocationShare).where(CareLocationShare.token == token)
    )
    share = res.scalar_one_or_none()
    if share is None or not token:
        raise HTTPException(status_code=404, detail="位置分享不存在或已失效")
    card = await _build_card_payload(db, share.user_id)
    card.pop("qr_token", None)

    def _to_float(v: str):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return {
        "code": 0,
        "data": {
            "location": {
                "latitude": _to_float(share.latitude),
                "longitude": _to_float(share.longitude),
                "address": share.address or None,
            },
            "card": card,
            "shared_at": share.created_at.isoformat() if share.created_at else None,
        },
    }
