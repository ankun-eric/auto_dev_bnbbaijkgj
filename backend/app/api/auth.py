import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.models.models import User, VerificationCode
from app.schemas.user import (
    RegisterSettingsResponse,
    SMSCodeRequest,
    SMSLoginRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.services.register_service import (
    ensure_member_card_no,
    get_register_settings,
    is_profile_completed,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.get("/register-settings", response_model=RegisterSettingsResponse)
async def register_settings(db: AsyncSession = Depends(get_db)):
    return await get_register_settings(db)


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    register_settings = await get_register_settings(db)
    if not register_settings["enable_self_registration"]:
        raise HTTPException(status_code=403, detail="当前暂未开放自助注册")

    result = await db.execute(select(User).where(User.phone == data.phone))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该手机号已注册")

    user = User(
        phone=data.phone,
        password_hash=get_password_hash(data.password),
        nickname=data.nickname or f"用户{data.phone[-4:]}",
    )
    await ensure_member_card_no(db, user, register_settings)
    db.add(user)
    await db.flush()
    await db.refresh(user)

    needs_profile_completion = (
        register_settings["show_profile_completion_prompt"]
        and not await is_profile_completed(db, user.id)
    )
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        is_new_user=True,
        needs_profile_completion=needs_profile_completion,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.phone == data.phone))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        raise HTTPException(status_code=400, detail="手机号或密码错误")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="手机号或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")

    register_settings = await get_register_settings(db)
    await ensure_member_card_no(db, user, register_settings)
    needs_profile_completion = (
        register_settings["show_profile_completion_prompt"]
        and not await is_profile_completed(db, user.id)
    )
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        needs_profile_completion=needs_profile_completion,
    )


@router.post("/sms-code")
async def send_sms_code(data: SMSCodeRequest, db: AsyncSession = Depends(get_db)):
    register_settings = await get_register_settings(db)
    if data.type in {"login", "register"} and not register_settings["enable_self_registration"]:
        result = await db.execute(select(User).where(User.phone == data.phone))
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="当前暂未开放自助注册")

    code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    vc = VerificationCode(
        phone=data.phone,
        code=code,
        type=data.type,
        expires_at=expires_at,
    )
    db.add(vc)
    await db.flush()

    return {"message": "验证码已发送", "code": code}


@router.post("/sms-login", response_model=TokenResponse)
async def sms_login(data: SMSLoginRequest, db: AsyncSession = Depends(get_db)):
    register_settings = await get_register_settings(db)
    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.phone == data.phone,
            VerificationCode.code == data.code,
            VerificationCode.expires_at > datetime.now(timezone.utc),
        )
        .order_by(VerificationCode.created_at.desc())
    )
    vc = result.scalar_one_or_none()
    if not vc:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")

    result = await db.execute(select(User).where(User.phone == data.phone))
    user = result.scalar_one_or_none()
    is_new_user = False
    if not user:
        if not register_settings["enable_self_registration"]:
            raise HTTPException(status_code=403, detail="当前暂未开放自助注册")
        user = User(phone=data.phone, nickname=f"用户{data.phone[-4:]}")
        await ensure_member_card_no(db, user, register_settings)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        is_new_user = True

    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")

    await ensure_member_card_no(db, user, register_settings)
    needs_profile_completion = (
        register_settings["show_profile_completion_prompt"]
        and not await is_profile_completed(db, user.id)
    )
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        is_new_user=is_new_user,
        needs_profile_completion=needs_profile_completion,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.nickname is not None:
        current_user.nickname = data.nickname
    if data.avatar is not None:
        current_user.avatar = data.avatar
    current_user.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)
