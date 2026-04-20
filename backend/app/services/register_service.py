from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import HealthProfile, SystemConfig, User
from app.services.member_code import allocate_unique_member_code

DEFAULT_REGISTER_SETTINGS = {
    "enable_self_registration": True,
    "wechat_register_mode": "authorize_member",
    "register_page_layout": "vertical",
    "show_profile_completion_prompt": True,
    "member_card_no_rule": "incremental",
}

BOOL_KEYS = {"enable_self_registration", "show_profile_completion_prompt"}
ENUM_OPTIONS = {
    "wechat_register_mode": {"authorize_member", "fill_profile"},
    "register_page_layout": {"vertical", "horizontal"},
    "member_card_no_rule": {"incremental", "random"},
}


def _parse_bool(value: str | bool | None, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_register_settings(raw_settings: dict | None = None) -> dict:
    raw_settings = raw_settings or {}
    settings = dict(DEFAULT_REGISTER_SETTINGS)

    for key, default_value in DEFAULT_REGISTER_SETTINGS.items():
        value = raw_settings.get(key, default_value)
        if key in BOOL_KEYS:
            settings[key] = _parse_bool(value, default_value)
        elif key in ENUM_OPTIONS:
            value = str(value or default_value)
            settings[key] = value if value in ENUM_OPTIONS[key] else default_value
        else:
            settings[key] = value

    return settings


async def get_register_settings(db: AsyncSession) -> dict:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.like("register_%"))
    )
    raw_settings = {}
    for config in result.scalars().all():
        raw_settings[config.config_key.removeprefix("register_")] = config.config_value
    return normalize_register_settings(raw_settings)


async def save_register_settings(db: AsyncSession, raw_settings: dict) -> dict:
    current_settings = await get_register_settings(db)
    merged_settings = {**current_settings, **(raw_settings or {})}
    settings = normalize_register_settings(merged_settings)
    for key, value in settings.items():
        config_key = f"register_{key}"
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_key == config_key)
        )
        config = result.scalar_one_or_none()
        serialized = str(value)
        if config:
            config.config_value = serialized
        else:
            db.add(
                SystemConfig(
                    config_key=config_key,
                    config_value=serialized,
                    config_type="register",
                    description=key,
                )
            )
    return settings


async def generate_member_card_no(db: AsyncSession, rule: str) -> str:
    """Bug #6 修复：统一使用新会员码规则（6 位、去易混淆字符、大写）。
    ``rule`` 参数仅为向后兼容保留，不再影响新码生成规则。
    """
    return await allocate_unique_member_code(db)


async def ensure_member_card_no(
    db: AsyncSession,
    user: User,
    settings: dict | None = None,
) -> bool:
    if user.member_card_no:
        return False

    register_settings = settings or await get_register_settings(db)
    user.member_card_no = await generate_member_card_no(
        db, register_settings["member_card_no_rule"]
    )
    return True


async def is_profile_completed(db: AsyncSession, user_id: int) -> bool:
    result = await db.execute(
        select(HealthProfile)
        .where(HealthProfile.user_id == user_id)
        .order_by(HealthProfile.id.desc())
        .limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return False
    return all(
        value is not None
        for value in (profile.gender, profile.birthday, profile.height, profile.weight)
    )
