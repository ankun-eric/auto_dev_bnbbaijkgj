import logging
import random
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_identity_codes_for_user,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.models.models import (
    AccountIdentity,
    FamilyMember,
    HealthProfile,
    IdentityType,
    MerchantProfile,
    MerchantStoreMembership,
    RelationType,
    User,
    UserRole,
    VerificationCode,
)

from app.schemas.merchant import MerchantProfileResponse, MerchantProfileUpdate, SessionContextResponse
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
from app.services.sms_service import send_sms
from app.utils.user_no_generator import generate_unique_user_no

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])


async def ensure_self_family_member(db: AsyncSession, user_id: int) -> None:
    result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == user_id,
            FamilyMember.is_self == True,  # noqa: E712
        )
    )
    if result.scalar_one_or_none():
        return

    relation_type_id = None
    rt_result = await db.execute(
        select(RelationType).where(RelationType.name == "本人")
    )
    rt = rt_result.scalar_one_or_none()
    if rt:
        relation_type_id = rt.id

    db.add(FamilyMember(
        user_id=user_id,
        relationship_type="本人",
        nickname="本人",
        is_self=True,
        status="active",
        relation_type_id=relation_type_id,
    ))
    await db.flush()


async def ensure_self_health_profile(db: AsyncSession, user_id: int) -> None:
    member_result = await db.execute(
        select(FamilyMember).where(
            FamilyMember.user_id == user_id,
            FamilyMember.is_self == True,  # noqa: E712
        )
    )
    self_member = member_result.scalar_one_or_none()

    result = await db.execute(
        select(HealthProfile)
        .where(HealthProfile.user_id == user_id)
        .order_by(HealthProfile.id.asc())
    )
    profiles = result.scalars().all()
    if profiles:
        existing = profiles[0]
        if self_member and existing.family_member_id != self_member.id:
            existing.family_member_id = self_member.id
            await db.flush()
        return

    db.add(HealthProfile(
        user_id=user_id,
        family_member_id=self_member.id if self_member else None,
    ))
    await db.flush()


async def ensure_identity(db: AsyncSession, user_id: int, identity_type: IdentityType) -> None:
    result = await db.execute(
        select(AccountIdentity).where(
            AccountIdentity.user_id == user_id,
            AccountIdentity.identity_type == identity_type,
        )
    )
    identity = result.scalar_one_or_none()
    if identity:
        identity.status = "active"
        identity.updated_at = datetime.utcnow()
        return
    db.add(AccountIdentity(user_id=user_id, identity_type=identity_type))


async def ensure_default_identity_for_legacy_user(db: AsyncSession, user: User) -> None:
    if user.role != UserRole.user:
        return
    identity_codes = await get_identity_codes_for_user(db, user.id)
    if not identity_codes:
        await ensure_identity(db, user.id, IdentityType.user)


async def build_session_context(db: AsyncSession, user: User) -> SessionContextResponse:
    await ensure_default_identity_for_legacy_user(db, user)
    identity_codes = await get_identity_codes_for_user(db, user.id)
    can_access_user = IdentityType.user.value in identity_codes
    can_access_merchant = (
        IdentityType.merchant_owner.value in identity_codes
        or IdentityType.merchant_staff.value in identity_codes
    )
    if not can_access_user and not can_access_merchant:
        raise HTTPException(status_code=403, detail="账号未配置可用身份")

    merchant_identity_type = None
    if IdentityType.merchant_owner.value in identity_codes:
        merchant_identity_type = "owner"
    elif IdentityType.merchant_staff.value in identity_codes:
        merchant_identity_type = "staff"

    if can_access_user and can_access_merchant:
        default_entry = "select_role"
    elif can_access_merchant:
        default_entry = "merchant"
    else:
        default_entry = "user"

    merchant_store_count = 0
    if can_access_merchant:
        count_result = await db.execute(
            select(func.count(MerchantStoreMembership.id)).where(
                MerchantStoreMembership.user_id == user.id,
                MerchantStoreMembership.status == "active",
            )
        )
        merchant_store_count = count_result.scalar() or 0

    return SessionContextResponse(
        identity_codes=sorted(identity_codes),
        can_access_user=can_access_user,
        can_access_merchant=can_access_merchant,
        is_dual_identity=can_access_user and can_access_merchant,
        default_entry=default_entry,
        merchant_identity_type=merchant_identity_type,
        show_role_switch=can_access_user and can_access_merchant,
        merchant_store_count=merchant_store_count,
    )


async def get_merchant_profile_response(db: AsyncSession, user: User) -> MerchantProfileResponse | None:
    session_context = await build_session_context(db, user)
    if not session_context.can_access_merchant:
        return None
    result = await db.execute(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile:
        return MerchantProfileResponse.model_validate(profile)
    return MerchantProfileResponse(nickname=user.nickname, avatar=user.avatar)


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

    user_no = await generate_unique_user_no(db)
    user = User(
        phone=data.phone,
        password_hash=get_password_hash(data.password),
        nickname=data.nickname or f"用户{data.phone[-4:]}",
        user_no=user_no,
    )

    if data.referrer_no:
        ref_result = await db.execute(
            select(User).where(User.user_no == data.referrer_no)
        )
        referrer = ref_result.scalar_one_or_none()
        if referrer and referrer.user_no != user_no:
            user.referrer_no = data.referrer_no

    await ensure_member_card_no(db, user, register_settings)
    db.add(user)
    await db.flush()
    await ensure_identity(db, user.id, IdentityType.user)
    try:
        await ensure_self_family_member(db, user.id)
    except Exception as e:
        logger.error("Failed to create self family member for user %s: %s", user.id, e)
    try:
        await ensure_self_health_profile(db, user.id)
    except Exception as e:
        logger.error("Failed to create self health profile for user %s: %s", user.id, e)

    result_user = await db.execute(select(User).where(User.id == user.id))
    user = result_user.scalar_one()

    needs_profile_completion = (
        register_settings["show_profile_completion_prompt"]
        and not await is_profile_completed(db, user.id)
    )
    token = create_access_token({"sub": str(user.id)})
    session_context = await build_session_context(db, user)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        is_new_user=True,
        needs_profile_completion=needs_profile_completion,
        session_context=session_context,
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
    await ensure_default_identity_for_legacy_user(db, user)
    await ensure_member_card_no(db, user, register_settings)
    token = create_access_token({"sub": str(user.id)})
    session_context = await build_session_context(db, user)
    needs_profile_completion = (
        session_context.can_access_user
        and register_settings["show_profile_completion_prompt"]
        and not await is_profile_completed(db, user.id)
    )
    merchant_profile = await get_merchant_profile_response(db, user)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        needs_profile_completion=needs_profile_completion,
        session_context=session_context,
        merchant_profile=merchant_profile,
    )


@router.post("/sms-code")
async def send_sms_code(data: SMSCodeRequest, db: AsyncSession = Depends(get_db)):
    register_settings = await get_register_settings(db)
    if data.type in {"login", "register"} and not register_settings["enable_self_registration"]:
        result = await db.execute(select(User).where(User.phone == data.phone))
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="当前暂未开放自助注册")

    TEST_PHONES = {"13800138000", "13800000001", "13800000002"}
    is_test = data.phone in TEST_PHONES

    if not is_test:
        recent = await db.execute(
            select(VerificationCode)
            .where(
                VerificationCode.phone == data.phone,
                VerificationCode.created_at > datetime.utcnow() - timedelta(seconds=60),
            )
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        if recent.scalar_one_or_none():
            raise HTTPException(status_code=429, detail="发送过于频繁，请60秒后重试")

    code = "123456" if is_test else "".join(random.choices(string.digits, k=6))
    expires_at = datetime.utcnow() + timedelta(minutes=5)

    if not is_test:
        try:
            await send_sms(data.phone, code, db=db)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    vc = VerificationCode(
        phone=data.phone,
        code=code,
        type=data.type,
        expires_at=expires_at,
    )
    db.add(vc)
    await db.flush()

    return {"message": "验证码已发送"}


@router.post("/sms-login", response_model=TokenResponse)
async def sms_login(data: SMSLoginRequest, db: AsyncSession = Depends(get_db)):
    register_settings = await get_register_settings(db)
    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.phone == data.phone,
            VerificationCode.code == data.code,
            VerificationCode.expires_at > datetime.utcnow(),
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    vc = result.scalar_one_or_none()
    if not vc:
        logger.warning(
            "SMS login failed: phone=%s, now=%s (submitted code not logged)",
            data.phone, datetime.utcnow(),
        )
        debug_result = await db.execute(
            select(VerificationCode)
            .where(VerificationCode.phone == data.phone)
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        debug_vc = debug_result.scalar_one_or_none()
        if debug_vc:
            logger.warning(
                "Latest VC for phone=%s: expires_at=%s, created_at=%s (code not logged)",
                data.phone, debug_vc.expires_at, debug_vc.created_at,
            )
        raise HTTPException(status_code=400, detail="验证码无效或已过期")

    result = await db.execute(select(User).where(User.phone == data.phone))
    user = result.scalar_one_or_none()
    is_new_user = False
    if not user:
        if not register_settings["enable_self_registration"]:
            raise HTTPException(status_code=403, detail="当前暂未开放自助注册")
        user_no = await generate_unique_user_no(db)
        user = User(phone=data.phone, nickname=f"用户{data.phone[-4:]}", user_no=user_no)

        if data.referrer_no:
            ref_result = await db.execute(
                select(User).where(User.user_no == data.referrer_no)
            )
            referrer = ref_result.scalar_one_or_none()
            if referrer and referrer.user_no != user_no:
                user.referrer_no = data.referrer_no

        await ensure_member_card_no(db, user, register_settings)
        db.add(user)
        await db.flush()
        await ensure_identity(db, user.id, IdentityType.user)
        try:
            await ensure_self_family_member(db, user.id)
        except Exception as e:
            logger.error("Failed to create self family member for user %s: %s", user.id, e)
        try:
            await ensure_self_health_profile(db, user.id)
        except Exception as e:
            logger.error("Failed to create self health profile for user %s: %s", user.id, e)
        result_user = await db.execute(select(User).where(User.id == user.id))
        user = result_user.scalar_one()
        is_new_user = True

    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")

    await ensure_default_identity_for_legacy_user(db, user)
    await ensure_member_card_no(db, user, register_settings)
    token = create_access_token({"sub": str(user.id)})
    session_context = await build_session_context(db, user)
    needs_profile_completion = (
        session_context.can_access_user
        and register_settings["show_profile_completion_prompt"]
        and not await is_profile_completed(db, user.id)
    )
    merchant_profile = await get_merchant_profile_response(db, user)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        is_new_user=is_new_user,
        needs_profile_completion=needs_profile_completion,
        session_context=session_context,
        merchant_profile=merchant_profile,
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


@router.get("/session-context", response_model=SessionContextResponse)
async def get_session_context(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_session_context(db, current_user)


@router.get("/merchant-profile", response_model=MerchantProfileResponse)
async def get_merchant_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session_context = await build_session_context(db, current_user)
    if not session_context.can_access_merchant:
        raise HTTPException(status_code=403, detail="暂无商家权限")
    profile = await get_merchant_profile_response(db, current_user)
    return profile or MerchantProfileResponse()


@router.put("/merchant-profile", response_model=MerchantProfileResponse)
async def update_merchant_profile(
    data: MerchantProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session_context = await build_session_context(db, current_user)
    if not session_context.can_access_merchant:
        raise HTTPException(status_code=403, detail="暂无商家权限")

    result = await db.execute(select(MerchantProfile).where(MerchantProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = MerchantProfile(user_id=current_user.id)
        db.add(profile)
        await db.flush()
    if data.nickname is not None:
        profile.nickname = data.nickname
    if data.avatar is not None:
        profile.avatar = data.avatar
    profile.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(profile)
    return MerchantProfileResponse.model_validate(profile)
