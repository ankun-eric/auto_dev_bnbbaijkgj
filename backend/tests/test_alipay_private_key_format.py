"""[Bug 修复 2026-05-05] 支付宝应用私钥归一化回归测试（兼容多种形态）。

修复后的归一化逻辑（PRD §3.2）支持以下 6 种合法输入形态，全部应通过：

  1. PKCS#8 中间 Base64（无头尾）           —— ``应用私钥PKCS8.txt``
  2. PKCS#8 完整 PEM（含 BEGIN PRIVATE KEY）—— 用户复制时一起带上头尾
  3. PKCS#1 中间 Base64（无头尾）           —— ``应用私钥RSA2048.txt``
  4. PKCS#1 完整 PEM（含 BEGIN RSA PRIVATE KEY）
  5. 任一以上形态 + 不可见字符（BOM/零宽/全角空格/换行/Tab）
  6. 公钥误粘贴 → 给出针对性报错

非法 / 错粘贴情况：

  - 公钥（PUBLIC KEY）→ ``ERROR_LOOKS_LIKE_PUBLIC_KEY``
  - 乱码 / 空 → ``ERROR_INVALID_FORMAT``
  - 内容被截断（base64 长度对得上但解析失败）→ ``ERROR_INCOMPLETE_BASE64``
"""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.utils.rsa_key import (
    ERROR_HAS_PEM_HEADERS,
    ERROR_INCOMPLETE_BASE64,
    ERROR_INVALID_FORMAT,
    ERROR_LOOKS_LIKE_PUBLIC_KEY,
    InvalidRSAPrivateKeyError,
    USER_FRIENDLY_ERROR,
    normalize_rsa_private_key,
    validate_rsa_private_key,
)


# ─────────────── 准备测试密钥 ───────────────


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def pkcs8_pem(rsa_key):
    return rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


@pytest.fixture(scope="module")
def pkcs1_pem(rsa_key):
    return rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


@pytest.fixture(scope="module")
def public_pem(rsa_key):
    return rsa_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _pem_body_to_naked_b64(pem: str) -> str:
    """从 PEM 字符串中抽出中间的裸 base64 内容（去掉 BEGIN/END 头与换行）。"""
    lines = [
        ln for ln in pem.strip().splitlines()
        if not ln.startswith("-----")
    ]
    return "".join(lines)


@pytest.fixture(scope="module")
def pkcs8_naked(pkcs8_pem):
    return _pem_body_to_naked_b64(pkcs8_pem)


@pytest.fixture(scope="module")
def pkcs1_naked(pkcs1_pem):
    return _pem_body_to_naked_b64(pkcs1_pem)


def _assert_valid_pkcs8_pem(out: str):
    """断言：返回值为合法的 PKCS#8 PEM 字符串，且能再次被加载为 RSA 私钥。"""
    assert "-----BEGIN PRIVATE KEY-----" in out
    assert "-----END PRIVATE KEY-----" in out
    key = serialization.load_pem_private_key(out.encode("utf-8"), password=None)
    assert isinstance(key, rsa.RSAPrivateKey)


# ─────────────── 形态 1：PKCS#8 中间 Base64（无头尾） ───────────────


def test_form1_pkcs8_naked_base64_pass(pkcs8_naked):
    """形态 1：PKCS#8 中间 Base64（应用私钥PKCS8.txt 直接复制）→ 通过。"""
    out = normalize_rsa_private_key(pkcs8_naked)
    _assert_valid_pkcs8_pem(out)


def test_form1_idempotent_normalize(pkcs8_naked):
    """形态 1 衍生：归一化后再次归一化应保持等价（已是 PKCS#8 PEM 完整形态）。"""
    once = normalize_rsa_private_key(pkcs8_naked)
    twice = normalize_rsa_private_key(once)
    assert once.strip() == twice.strip()


# ─────────────── 形态 2：PKCS#8 完整 PEM（含 BEGIN PRIVATE KEY） ───────────────


def test_form2_full_pkcs8_pem_pass(pkcs8_pem):
    """形态 2：含 ``-----BEGIN PRIVATE KEY-----`` 完整 PKCS#8 PEM → 通过（自动剥离头尾）。"""
    out = normalize_rsa_private_key(pkcs8_pem)
    _assert_valid_pkcs8_pem(out)


# ─────────────── 形态 3：PKCS#1 中间 Base64（无头尾，RSA2048.txt） ───────────────


def test_form3_pkcs1_naked_base64_pass(pkcs1_naked):
    """形态 3：PKCS#1 中间 Base64（应用私钥RSA2048.txt 直接复制）→ 通过。

    这是本次 Bug 的核心场景：上一版会直接报错"应用私钥格式不被支持，请用 PKCS8.txt"，
    修复后必须自动包装为 PKCS#1 PEM 加载，再统一转为 PKCS#8 入库。
    """
    out = normalize_rsa_private_key(pkcs1_naked)
    _assert_valid_pkcs8_pem(out)


# ─────────────── 形态 4：PKCS#1 完整 PEM（含 BEGIN RSA PRIVATE KEY） ───────────────


def test_form4_full_pkcs1_pem_pass(pkcs1_pem):
    """形态 4：含 ``-----BEGIN RSA PRIVATE KEY-----`` 完整 PKCS#1 PEM → 通过。"""
    out = normalize_rsa_private_key(pkcs1_pem)
    _assert_valid_pkcs8_pem(out)


# ─────────────── 形态 5：含不可见字符的任一以上形态 ───────────────


def test_form5_pkcs8_naked_with_whitespace_and_newlines(pkcs8_naked):
    """形态 5a：PKCS#8 中间 Base64 + 多余空格/换行 → 通过。"""
    noisy = "  " + "\n".join(
        pkcs8_naked[i : i + 20] + "\t " for i in range(0, len(pkcs8_naked), 20)
    )
    out = normalize_rsa_private_key(noisy)
    _assert_valid_pkcs8_pem(out)


def test_form5_pkcs8_naked_with_invisible_chars(pkcs8_naked):
    """形态 5b：PKCS#8 中间 Base64 + BOM/零宽/全角空格 → 通过。"""
    polluted = (
        "\ufeff   "
        + pkcs8_naked[:50]
        + "\u200b"
        + pkcs8_naked[50:100]
        + "\u3000"
        + pkcs8_naked[100:]
        + "\u00a0"
    )
    out = normalize_rsa_private_key(polluted)
    _assert_valid_pkcs8_pem(out)


def test_form5_pkcs1_naked_with_invisible_chars(pkcs1_naked):
    """形态 5c：PKCS#1 中间 Base64 + 不可见字符 → 通过。"""
    polluted = (
        "\ufeff"
        + pkcs1_naked[:30]
        + "\u200b\u3000\u00a0"
        + pkcs1_naked[30:]
    )
    out = normalize_rsa_private_key(polluted)
    _assert_valid_pkcs8_pem(out)


def test_form5_full_pkcs8_with_bom(pkcs8_pem):
    """形态 5d：PKCS#8 完整 PEM 前面有 BOM → 通过。"""
    polluted = "\ufeff" + pkcs8_pem
    out = normalize_rsa_private_key(polluted)
    _assert_valid_pkcs8_pem(out)


# ─────────────── 形态 6：公钥误粘贴 → 针对性报错 ───────────────


def test_public_key_full_pem_rejected(public_pem):
    """形态 6a：公钥完整 PEM（BEGIN PUBLIC KEY）→ "您粘贴的是公钥"针对性报错。"""
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(public_pem)
    assert ERROR_LOOKS_LIKE_PUBLIC_KEY in str(exc_info.value)


def test_public_key_naked_base64_rejected(public_pem):
    """形态 6b：公钥的中间 Base64（无头尾）→ "您粘贴的是公钥"针对性报错。"""
    naked = _pem_body_to_naked_b64(public_pem)
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(naked)
    assert ERROR_LOOKS_LIKE_PUBLIC_KEY in str(exc_info.value)


# ─────────────── 非法输入：乱码 / 空 / 截断 ───────────────


def test_garbage_string_rejected():
    """乱码字符串 → ``ERROR_INVALID_FORMAT``。"""
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key("this is not a private key at all !!!")
    assert ERROR_INVALID_FORMAT in str(exc_info.value)


def test_random_short_base64_rejected():
    """合法 base64 但长度太短（明显不是 RSA 2048）→ ``ERROR_INVALID_FORMAT``。"""
    fake_b64 = base64.b64encode(b"hello world this is not an rsa key payload").decode()
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(fake_b64)
    assert ERROR_INVALID_FORMAT in str(exc_info.value)


def test_truncated_pkcs8_naked_rejected(pkcs8_naked):
    """长度对得上但内容被截断（粘贴时丢了一段）→ ``ERROR_INCOMPLETE_BASE64``。"""
    # 取 PKCS#8 base64 的前 1100 字符（接近原长，但损坏了内部结构）
    truncated = pkcs8_naked[:1100] + pkcs8_naked[1200:]
    # 截断后长度仍接近 PKCS#8 base64 的长度（>800），落入「不完整」分支
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(truncated)
    msg = str(exc_info.value)
    # 截断的内容也可能落入 INVALID_FORMAT（取决于具体长度），都接受
    assert (
        ERROR_INCOMPLETE_BASE64 in msg
        or ERROR_INVALID_FORMAT in msg
    )


def test_empty_input_rejected():
    """空字符串 / 仅空白 → ``ERROR_INVALID_FORMAT``。"""
    for empty in ("", "   \n  ", "\t\t"):
        with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
            normalize_rsa_private_key(empty)
        assert ERROR_INVALID_FORMAT in str(exc_info.value)


def test_only_begin_end_lines_rejected():
    """仅 BEGIN/END 两行（中间空）→ ``ERROR_INVALID_FORMAT``（含头尾但无 base64 内容）。"""
    payload = "-----BEGIN PRIVATE KEY-----\n-----END PRIVATE KEY-----"
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(payload)
    assert ERROR_INVALID_FORMAT in str(exc_info.value)


# ─────────────── validate_rsa_private_key 不抛异常版本 ───────────────


def test_validate_returns_ok_true_for_pkcs8_naked(pkcs8_naked):
    ok, normalized, reason = validate_rsa_private_key(pkcs8_naked)
    assert ok is True
    assert normalized is not None
    assert "-----BEGIN PRIVATE KEY-----" in normalized
    assert reason == ""


def test_validate_returns_ok_true_for_pkcs1_naked(pkcs1_naked):
    """核心场景：PKCS#1 中间 Base64 → ok=True，归一化为 PKCS#8 PEM。"""
    ok, normalized, reason = validate_rsa_private_key(pkcs1_naked)
    assert ok is True, f"expected ok=True, got reason={reason}"
    assert normalized is not None
    assert "-----BEGIN PRIVATE KEY-----" in normalized
    # 归一化后必须能被加载
    key = serialization.load_pem_private_key(normalized.encode("utf-8"), password=None)
    assert isinstance(key, rsa.RSAPrivateKey)
    assert reason == ""


def test_validate_returns_ok_true_for_full_pkcs8_pem(pkcs8_pem):
    """含头尾的 PKCS#8 完整 PEM → ok=True（自动剥离头尾）。"""
    ok, normalized, reason = validate_rsa_private_key(pkcs8_pem)
    assert ok is True, f"expected ok=True, got reason={reason}"
    assert normalized is not None
    assert "-----BEGIN PRIVATE KEY-----" in normalized


def test_validate_returns_ok_true_for_full_pkcs1_pem(pkcs1_pem):
    """含头尾的 PKCS#1 完整 PEM → ok=True（cryptography 自动识别）。"""
    ok, normalized, reason = validate_rsa_private_key(pkcs1_pem)
    assert ok is True, f"expected ok=True, got reason={reason}"
    assert normalized is not None
    assert "-----BEGIN PRIVATE KEY-----" in normalized


def test_validate_returns_ok_false_for_public_key(public_pem):
    """validate 接到公钥时，返回 ok=False、reason 为公钥分支化文案。"""
    ok, normalized, reason = validate_rsa_private_key(public_pem)
    assert ok is False
    assert normalized is None
    assert reason == ERROR_LOOKS_LIKE_PUBLIC_KEY


def test_validate_returns_ok_false_for_garbage():
    ok, normalized, reason = validate_rsa_private_key("garbage value@@@")
    assert ok is False
    assert normalized is None
    assert reason == ERROR_INVALID_FORMAT


# ─────────────── 文案合规检查 ───────────────


def test_error_invalid_format_text_is_friendly():
    """通用「无法识别」报错文案：清晰说明可粘贴 PKCS8.txt 或 RSA2048.txt 任一。"""
    assert "PKCS8.txt" in ERROR_INVALID_FORMAT
    assert "RSA2048.txt" in ERROR_INVALID_FORMAT
    assert "任一" in ERROR_INVALID_FORMAT


def test_error_public_key_text_is_friendly():
    """公钥分支化文案：明确告知"您粘贴的是公钥不是私钥"。"""
    assert "公钥" in ERROR_LOOKS_LIKE_PUBLIC_KEY
    assert "私钥" in ERROR_LOOKS_LIKE_PUBLIC_KEY


def test_error_incomplete_text_is_friendly():
    """截断分支化文案：提示"内容看起来不完整"。"""
    assert "不完整" in ERROR_INCOMPLETE_BASE64


def test_user_friendly_error_alias_points_to_invalid_format():
    """USER_FRIENDLY_ERROR 兼容别名应指向 ERROR_INVALID_FORMAT。"""
    assert USER_FRIENDLY_ERROR == ERROR_INVALID_FORMAT


def test_legacy_error_has_pem_headers_constant_still_exists():
    """ERROR_HAS_PEM_HEADERS 兼容常量仍可被导入（避免老调用方 ImportError）。"""
    assert isinstance(ERROR_HAS_PEM_HEADERS, str)
