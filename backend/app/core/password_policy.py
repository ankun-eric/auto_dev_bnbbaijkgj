"""密码 / JWT 通用工具

- 密码强度校验：≥8 位，必须同时包含字母 + 数字
- JWT 黑名单：用于"修改密码后强制踢出当前 / 全部 token"
  使用进程内字典 + TTL；多 worker 时建议替换为 Redis
- "强制改密"标记：内存 set；登录后端不查 DB 即可知道用户首次登录是否需要强制改密
  （配合 must_change_password 字段持久化双保险）
"""
from __future__ import annotations

import hashlib
import re
import time
from threading import Lock
from typing import Optional

PASSWORD_MIN_LEN = 8
_PASSWORD_REGEX_LETTER = re.compile(r"[A-Za-z]")
_PASSWORD_REGEX_DIGIT = re.compile(r"\d")


class PasswordValidationError(ValueError):
    """密码强度不足"""


def validate_password_strength(password: str, *, message: str = "新密码至少 8 位，且需包含字母和数字") -> None:
    if not isinstance(password, str) or len(password) < PASSWORD_MIN_LEN:
        raise PasswordValidationError(message)
    if not _PASSWORD_REGEX_LETTER.search(password):
        raise PasswordValidationError(message)
    if not _PASSWORD_REGEX_DIGIT.search(password):
        raise PasswordValidationError(message)


# ────────── JWT 黑名单 ──────────

_JWT_BLACKLIST: dict[str, float] = {}  # token_hash -> expire_at
_USER_TOKEN_VERSION: dict[int, int] = {}  # user_id -> 最近一次"全端踢出"的标记时间戳
_MUTEX = Lock()
_DEFAULT_TTL = 24 * 60 * 60


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def revoke_token(token: str, ttl_seconds: int = _DEFAULT_TTL) -> None:
    if not token:
        return
    with _MUTEX:
        _JWT_BLACKLIST[_hash_token(token)] = time.time() + ttl_seconds
        # 顺手清理过期项
        if len(_JWT_BLACKLIST) % 50 == 0:
            now = time.time()
            for k in list(_JWT_BLACKLIST.keys()):
                if _JWT_BLACKLIST[k] < now:
                    _JWT_BLACKLIST.pop(k, None)


def is_token_revoked(token: Optional[str]) -> bool:
    if not token:
        return False
    with _MUTEX:
        exp = _JWT_BLACKLIST.get(_hash_token(token))
    if exp is None:
        return False
    if exp < time.time():
        return False
    return True


def revoke_all_tokens_for_user(user_id: int) -> None:
    """全端踢出：通过 user_id -> 时间戳。get_current_user 校验 token iat < cutoff 时判定失效。

    需要 token payload 包含 iat（python-jose 默认不写入），因此这里采用：
    - 修改密码 / 重置密码场景：登录态 token 的失效通过黑名单 + 强制重新登录提示
    - 由于 token 本身无 iat 写入，多端踢出依赖前端立刻清除 + 服务端拒绝 当前 token；
      其它端的旧 token 在 ACCESS_TOKEN_EXPIRE_MINUTES 后自然过期。
    """
    with _MUTEX:
        _USER_TOKEN_VERSION[user_id] = int(time.time())


def get_user_revoke_timestamp(user_id: int) -> int:
    with _MUTEX:
        return _USER_TOKEN_VERSION.get(user_id, 0)


# ────────── must_change_password 内存快表 ──────────
_MUST_CHANGE: set[int] = set()


def mark_must_change_password(user_id: int) -> None:
    _MUST_CHANGE.add(user_id)


def clear_must_change_password(user_id: int) -> None:
    _MUST_CHANGE.discard(user_id)


def is_must_change_password(user_id: int) -> bool:
    return user_id in _MUST_CHANGE
