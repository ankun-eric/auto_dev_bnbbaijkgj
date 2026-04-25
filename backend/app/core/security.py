import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    # 防御性加固：JWT 规范要求 sub 必须是字符串，这里自动把 int / UUID 等对象 str 化，
    # 避免任何新加的登录入口因把 sub 写成非字符串而被 python-jose 的 JWTClaimsError
    # "Subject must be a string" 校验拒绝，从而导致"登录成功但下一个请求立即 401"
    if "sub" in to_encode and to_encode["sub"] is not None and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.models.models import User
    from app.core.password_policy import is_token_revoked

    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    if is_token_revoked(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        raw_sub = payload.get("sub")
        if raw_sub is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭证")
        # 类型兼容：历史 token 可能把 sub 写成整数，这里统一 str(...) 后再 int(...) 解析
        try:
            user_id = int(str(raw_sub))
        except (TypeError, ValueError):
            logger.warning("JWT sub 无法解析为整数 user_id: %r", raw_sub)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭证")
    except JWTError as exc:
        # 写入后端日志，便于以后类似问题 1 分钟内定位
        logger.warning("JWT decode 失败: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭证")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return user


def require_role(*roles: str):
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return current_user
    return role_checker


async def get_identity_codes_for_user(db: AsyncSession, user_id: int) -> set[str]:
    from app.models.models import AccountIdentity

    result = await db.execute(
        select(AccountIdentity.identity_type).where(
            AccountIdentity.user_id == user_id,
            AccountIdentity.status == "active",
        )
    )
    return {
        identity.value if hasattr(identity, "value") else str(identity)
        for identity in result.scalars().all()
    }


def require_identity(*identity_codes: str):
    async def identity_checker(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        user_identity_codes = await get_identity_codes_for_user(db, current_user.id)
        if not any(code in user_identity_codes for code in identity_codes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return current_user

    return identity_checker
