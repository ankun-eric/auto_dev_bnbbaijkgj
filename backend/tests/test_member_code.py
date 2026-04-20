"""Bug #6 单元测试：会员码生成规则。"""
from __future__ import annotations

import pytest

from app.services.member_code import (
    MEMBER_CODE_CHARSET,
    MEMBER_CODE_LENGTH,
    MEMBER_CODE_MAX_RETRIES,
    allocate_unique_member_code,
    generate_member_code,
)

# 易混淆字符：根据规范的 32 位字符集 23456789ABCDEFGHJKLMNPQRSTUVWXYZ
# 共剔除 0/O/1/I 四个字符。
FORBIDDEN_CHARS = set("0O1I")


def test_charset_excludes_easily_confused_chars():
    assert MEMBER_CODE_LENGTH == 6
    assert MEMBER_CODE_CHARSET == "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    assert len(MEMBER_CODE_CHARSET) == 32
    for ch in MEMBER_CODE_CHARSET:
        assert ch not in FORBIDDEN_CHARS
        assert ch == ch.upper()


def test_generate_member_code_length_and_charset():
    for _ in range(500):
        code = generate_member_code()
        assert len(code) == MEMBER_CODE_LENGTH
        for ch in code:
            assert ch in MEMBER_CODE_CHARSET
            assert ch not in FORBIDDEN_CHARS
        assert code == code.upper()


@pytest.mark.asyncio
async def test_allocate_unique_member_code_returns_valid_code(db_session):
    code = await allocate_unique_member_code(db_session)
    assert len(code) == MEMBER_CODE_LENGTH
    assert all(ch in MEMBER_CODE_CHARSET for ch in code)


@pytest.mark.asyncio
async def test_allocate_unique_member_code_raises_when_all_taken(monkeypatch, db_session):
    """冲突重试上限内全部冲突时应抛 RuntimeError。"""
    async def _always_taken(db, code):
        return True

    from app.services import member_code as mc

    monkeypatch.setattr(mc, "_is_code_taken", _always_taken)

    with pytest.raises(RuntimeError):
        await allocate_unique_member_code(db_session, max_retries=MEMBER_CODE_MAX_RETRIES)
