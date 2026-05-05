"""[需求 2026-05-05] 支付宝应用私钥校验收窄回归测试。

收窄后的校验逻辑（PRD §四）：
  ① 清洗不可见字符
  ② 检测 -----BEGIN----- / -----END-----
        是 → 抛错"请只粘贴中间 Base64 部分..."
        否 → ③ 提取合法 Base64 字符
             → ④ Base64 解码 + ASN.1（PKCS#8）解析
                  成功 → 标准化为 PKCS#8 PEM
                  失败 → 抛错"应用私钥格式不被支持..."

覆盖 PRD §六 全部 8 个用例：
  T1：纯中间 Base64                          → 通过
  T2：中间 Base64 + 多余空格/换行             → 通过
  T3：中间 Base64 + BOM/零宽/全角空格         → 通过
  T4：含 -----BEGIN PRIVATE KEY----- 完整    → 报错 ERROR_HAS_PEM_HEADERS
  T5：含 -----BEGIN RSA PRIVATE KEY----- 完整 → 报错 ERROR_HAS_PEM_HEADERS
  T6：仅 BEGIN/END 两行（中间空）             → 报错 ERROR_HAS_PEM_HEADERS
  T7：公钥（BEGIN PUBLIC KEY）                → 报错 ERROR_HAS_PEM_HEADERS
  T8：乱码字符串                              → 报错 ERROR_INVALID_FORMAT
"""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.utils.rsa_key import (
    ERROR_HAS_PEM_HEADERS,
    ERROR_INVALID_FORMAT,
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


# ─────────────── T1：纯中间 Base64（密钥工具产出） ───────────────


def test_T1_pure_middle_base64_pass(pkcs8_naked):
    """T1：纯中间 Base64（密钥工具产出）→ 通过。"""
    out = normalize_rsa_private_key(pkcs8_naked)
    assert "-----BEGIN PRIVATE KEY-----" in out
    assert "-----END PRIVATE KEY-----" in out
    # 标准化结果必须能被重新加载
    key = serialization.load_pem_private_key(out.encode("utf-8"), password=None)
    assert isinstance(key, rsa.RSAPrivateKey)


def test_T1_idempotent_normalize(pkcs8_naked):
    """T1 衍生：对纯中间 Base64 标准化后再次标准化（带头尾）应抛错——
    因为收窄后已不再接受头尾形态。"""
    normalized = normalize_rsa_private_key(pkcs8_naked)
    # 标准化结果含头尾，再次传入应直接报错
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(normalized)
    assert ERROR_HAS_PEM_HEADERS in str(exc_info.value)


# ─────────────── T2：中间 Base64 + 多余空格/换行 ───────────────


def test_T2_middle_base64_with_whitespace_and_newlines(pkcs8_naked):
    """T2：中间 Base64 + 多余空格/换行 → 通过（清洗后通过）。"""
    noisy = "  " + "\n".join(
        pkcs8_naked[i : i + 20] + "\t " for i in range(0, len(pkcs8_naked), 20)
    )
    out = normalize_rsa_private_key(noisy)
    assert "-----BEGIN PRIVATE KEY-----" in out


# ─────────────── T3：中间 Base64 + BOM/零宽/全角空格 ───────────────


def test_T3_middle_base64_with_invisible_chars(pkcs8_naked):
    """T3：中间 Base64 + BOM/零宽/全角空格 → 通过。"""
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
    assert "-----BEGIN PRIVATE KEY-----" in out


# ─────────────── T4：含 -----BEGIN PRIVATE KEY----- 完整 PKCS#8 PEM ───────────────


def test_T4_full_pkcs8_pem_rejected(pkcs8_pem):
    """T4：含 -----BEGIN PRIVATE KEY----- 完整 PKCS#8 PEM → 报错"请只粘贴中间..."。"""
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(pkcs8_pem)
    assert ERROR_HAS_PEM_HEADERS in str(exc_info.value)


# ─────────────── T5：含 -----BEGIN RSA PRIVATE KEY----- 完整 PKCS#1 PEM ───────────────


def test_T5_full_pkcs1_pem_rejected(pkcs1_pem):
    """T5：含 -----BEGIN RSA PRIVATE KEY----- 完整 PKCS#1 PEM → 报错"请只粘贴中间..."。"""
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(pkcs1_pem)
    assert ERROR_HAS_PEM_HEADERS in str(exc_info.value)


# ─────────────── T6：仅 BEGIN/END 两行（中间空） ───────────────


def test_T6_only_begin_end_lines_rejected():
    """T6：仅 BEGIN/END 两行（中间空）→ 报错"请只粘贴中间..."。"""
    payload = "-----BEGIN PRIVATE KEY-----\n-----END PRIVATE KEY-----"
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(payload)
    assert ERROR_HAS_PEM_HEADERS in str(exc_info.value)


def test_T6_only_begin_line_rejected():
    """T6 衍生：只有 BEGIN 这一行也应短路报错。"""
    payload = "-----BEGIN PRIVATE KEY-----"
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(payload)
    assert ERROR_HAS_PEM_HEADERS in str(exc_info.value)


def test_T6_only_end_line_rejected():
    """T6 衍生：只有 END 这一行也应短路报错。"""
    payload = "-----END PRIVATE KEY-----"
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(payload)
    assert ERROR_HAS_PEM_HEADERS in str(exc_info.value)


# ─────────────── T7：公钥（BEGIN PUBLIC KEY） ───────────────


def test_T7_public_key_rejected(public_pem):
    """T7：公钥（BEGIN PUBLIC KEY）→ 报错"请只粘贴中间..."（因为含头尾标记）。"""
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(public_pem)
    assert ERROR_HAS_PEM_HEADERS in str(exc_info.value)


# ─────────────── T8：乱码字符串 ───────────────


def test_T8_garbage_string_rejected():
    """T8：乱码字符串 → 报错"应用私钥格式不被支持..."。"""
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key("this is not a private key at all !!!")
    assert ERROR_INVALID_FORMAT in str(exc_info.value)


def test_T8_random_base64_not_a_key():
    """T8 衍生：合法 base64 但解码后并非 RSA 私钥 → 报错 ERROR_INVALID_FORMAT。"""
    fake_b64 = base64.b64encode(b"hello world this is not an rsa key payload").decode()
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key(fake_b64)
    assert ERROR_INVALID_FORMAT in str(exc_info.value)


def test_T8_empty_input_rejected():
    """T8 衍生：空字符串 / 仅空白 → 报错 ERROR_INVALID_FORMAT。"""
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key("")
    assert ERROR_INVALID_FORMAT in str(exc_info.value)
    with pytest.raises(InvalidRSAPrivateKeyError) as exc_info:
        normalize_rsa_private_key("   \n  ")
    assert ERROR_INVALID_FORMAT in str(exc_info.value)


# ─────────────── validate_rsa_private_key 不抛异常版本 ───────────────


def test_validate_returns_ok_true_for_valid_pkcs8_naked(pkcs8_naked):
    ok, normalized, reason = validate_rsa_private_key(pkcs8_naked)
    assert ok is True
    assert normalized is not None
    assert "-----BEGIN PRIVATE KEY-----" in normalized
    assert reason == ""


def test_validate_returns_ok_false_with_pem_headers(pkcs8_pem):
    """validate 接到含头尾的输入时，返回 ok=False、reason 为头尾报错。"""
    ok, normalized, reason = validate_rsa_private_key(pkcs8_pem)
    assert ok is False
    assert normalized is None
    assert reason == ERROR_HAS_PEM_HEADERS


def test_validate_returns_ok_false_for_garbage():
    ok, normalized, reason = validate_rsa_private_key("garbage value@@@")
    assert ok is False
    assert normalized is None
    assert reason == ERROR_INVALID_FORMAT


# ─────────────── 文案合规检查 ───────────────


def test_error_pem_header_text_is_concise():
    """含头尾报错文案：必须是单句，提示去掉 BEGIN/END 两行。"""
    assert ERROR_HAS_PEM_HEADERS == "请只粘贴中间 Base64 部分（去掉 BEGIN/END 两行）。"


def test_error_invalid_format_text_is_concise():
    """其他无效报错文案：单句，提示粘贴密钥工具生成的中间 Base64 内容。"""
    assert ERROR_INVALID_FORMAT == "应用私钥格式不被支持。请粘贴密钥工具生成的中间 Base64 内容。"


def test_user_friendly_error_alias_points_to_invalid_format():
    """USER_FRIENDLY_ERROR 兼容别名应指向 ERROR_INVALID_FORMAT。"""
    assert USER_FRIENDLY_ERROR == ERROR_INVALID_FORMAT
