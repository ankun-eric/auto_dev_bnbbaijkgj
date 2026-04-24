"""回归测试：商家 PC 后台登录 → token → jwt.decode 鉴权链路

覆盖 Bug："商家 PC 后台登录后被 401 踢回登录页"的根因修复：
- `create_access_token` 签发时 sub 必须是字符串，或能自动 str 化
- 签发出的 token 必须能被 `jwt.decode` 正常解码（不能抛 JWTClaimsError: Subject must be a string）
- merchant_v1.py 中 PC 登录签发逻辑必须使用 str(user.id)

这条测试不依赖 HTTP 服务器，直接验证 token 签发 ↔ 校验链路，
CI 中只要跑通本文件即可拦截该类 Bug 回归。
"""
from __future__ import annotations

import os
import sys
import re
from pathlib import Path

import pytest
from jose import jwt, JWTError

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402


def _decode(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def test_create_access_token_with_str_sub_can_be_decoded():
    """基线：sub 为 str 时，token 可正常解码。"""
    token = create_access_token({"sub": "42", "scope": "merchant_pc"})
    payload = _decode(token)
    assert payload["sub"] == "42"
    assert payload["scope"] == "merchant_pc"


def test_create_access_token_auto_stringify_int_sub():
    """防御性加固：即便 sub 被传成 int，也应被自动 str 化，解码不应抛 JWTClaimsError。

    这正是本次 Bug 的反向守护：历史上 merchant_v1.py 传入的是 int，
    必须保证即使将来再有调用方写成 int，token 仍然可被正常解码。
    """
    token = create_access_token({"sub": 42, "scope": "merchant_pc"})
    payload = _decode(token)
    assert payload["sub"] == "42"
    assert isinstance(payload["sub"], str)


def test_merchant_pc_login_source_uses_str_sub():
    """静态源码校验：商家 PC 登录接口必须用 str(user.id) 签发 token。

    防止 merchant_v1.py 里的 `create_access_token({"sub": user.id, ...})` 再次被改回。
    """
    src = (BACKEND_DIR / "app" / "api" / "merchant_v1.py").read_text(encoding="utf-8")
    # 必须存在 str(user.id) 的写法
    assert 'create_access_token({"sub": str(user.id)' in src, (
        "merchant_v1.py 中 PC 登录签发 token 时必须使用 str(user.id)，"
        "这是商家 PC 后台登录 401 Bug 的关键修复点。"
    )
    # 断言文件里不再存在裸 user.id 的 sub 写法
    bad_pattern = re.compile(r'create_access_token\(\s*\{\s*"sub"\s*:\s*user\.id\b')
    assert not bad_pattern.search(src), (
        "检测到 merchant_v1.py 中仍有 `create_access_token({\"sub\": user.id ...})` 的裸 int 写法，"
        "会触发 python-jose 的 `Subject must be a string` 校验失败，导致登录后立即 401。"
    )


def test_get_current_user_accepts_str_numeric_sub(monkeypatch):
    """主链路：签发出的 token 传给 get_current_user 应能被正确解析为 int user_id。"""
    import asyncio
    from app.core import security as security_module

    token = create_access_token({"sub": str(999), "scope": "merchant_pc"})

    # 构造一个假的 User 与假的 db，仅验证 sub 解析路径不抛异常
    class _FakeUser:
        id = 999
        status = "active"

    class _FakeResult:
        def scalar_one_or_none(self_inner):
            return _FakeUser()

    class _FakeDb:
        async def execute(self_inner, *_args, **_kwargs):
            return _FakeResult()

    async def _run():
        user = await security_module.get_current_user(token=token, db=_FakeDb())
        assert user.id == 999

    asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
