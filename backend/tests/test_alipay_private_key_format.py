"""[Bug 修复 2026-05-05] 支付宝应用私钥格式自适应工具回归测试。

覆盖 Bug 修复方案文档 §6 用例 1~4：
  - PKCS#1 裸 base64 → 标准化为 PKCS#8 PEM
  - PKCS#8 裸 base64 → 标准化为 PKCS#8 PEM（幂等）
  - PKCS#1 带 PEM 头  → 标准化为 PKCS#8 PEM
  - PKCS#8 带 PEM 头  → 幂等
  - 乱码 / 非 base64  → 校验失败，返回 ok=False，文案明确指向 PKCS#8.txt
"""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.utils.rsa_key import (
    InvalidRSAPrivateKeyError,
    USER_FRIENDLY_ERROR,
    normalize_rsa_private_key,
    validate_rsa_private_key,
)


# ─────────────── 准备四种形态的同一把密钥（仅本测试模块内复用） ───────────────


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


# ─────────────── 用例 1：PKCS#1 裸 base64 → PKCS#8 PEM ───────────────


def test_normalize_pkcs1_naked_base64_to_pkcs8(pkcs1_naked):
    out = normalize_rsa_private_key(pkcs1_naked)
    assert "-----BEGIN PRIVATE KEY-----" in out
    assert "-----END PRIVATE KEY-----" in out
    # 标准化结果必须能被 cryptography 重新加载
    key = serialization.load_pem_private_key(out.encode("utf-8"), password=None)
    assert isinstance(key, rsa.RSAPrivateKey)


# ─────────────── 用例 2：PKCS#8 裸 base64 → PKCS#8 PEM（幂等） ───────────────


def test_normalize_pkcs8_naked_base64_to_pkcs8(pkcs8_naked):
    out = normalize_rsa_private_key(pkcs8_naked)
    assert "-----BEGIN PRIVATE KEY-----" in out
    # 重复标准化结果应等于原结果（幂等）
    assert normalize_rsa_private_key(out) == out


# ─────────────── 用例 3：PKCS#1 带 PEM 头 → PKCS#8 PEM ───────────────


def test_normalize_pkcs1_pem_headers_to_pkcs8(pkcs1_pem):
    out = normalize_rsa_private_key(pkcs1_pem)
    assert "-----BEGIN PRIVATE KEY-----" in out
    assert "-----BEGIN RSA PRIVATE KEY-----" not in out


def test_normalize_pkcs8_pem_headers_idempotent(pkcs8_pem):
    out = normalize_rsa_private_key(pkcs8_pem)
    assert "-----BEGIN PRIVATE KEY-----" in out
    # 字节级别可能有 trailing newline 差异，但内容一致 → 重复执行结果完全相同
    assert normalize_rsa_private_key(out) == out


# ─────────────── 用例 4：乱码 / 非 base64 → 抛业务异常 ───────────────


def test_normalize_garbage_raises_invalid_error():
    with pytest.raises(InvalidRSAPrivateKeyError):
        normalize_rsa_private_key("this is not a private key at all !!!")


def test_normalize_empty_raises_invalid_error():
    with pytest.raises(InvalidRSAPrivateKeyError):
        normalize_rsa_private_key("")
    with pytest.raises(InvalidRSAPrivateKeyError):
        normalize_rsa_private_key("   \n  ")


def test_normalize_random_base64_that_is_not_a_key():
    """合法 base64 但解码后并非 RSA 私钥（也应当被识别为格式错误）。"""
    fake_b64 = base64.b64encode(b"hello world this is not an rsa key payload").decode()
    with pytest.raises(InvalidRSAPrivateKeyError):
        normalize_rsa_private_key(fake_b64)


# ─────────────── validate_rsa_private_key 不抛异常版本 ───────────────


def test_validate_returns_ok_true_for_valid_pkcs8_naked(pkcs8_naked):
    ok, normalized, reason = validate_rsa_private_key(pkcs8_naked)
    assert ok is True
    assert normalized is not None
    assert "-----BEGIN PRIVATE KEY-----" in normalized
    assert reason == ""


def test_validate_returns_ok_true_for_valid_pkcs1_naked(pkcs1_naked):
    ok, normalized, reason = validate_rsa_private_key(pkcs1_naked)
    assert ok is True
    assert normalized is not None
    assert "-----BEGIN PRIVATE KEY-----" in normalized


def test_validate_returns_ok_false_for_garbage():
    ok, normalized, reason = validate_rsa_private_key("garbage value@@@")
    assert ok is False
    assert normalized is None
    assert "应用私钥PKCS8" in reason or "PKCS#8" in reason or "格式不被支持" in reason


def test_validate_friendly_error_text_contains_filename_hint():
    """友好文案必须明确告诉用户使用 应用私钥PKCS8.txt 文件。"""
    assert "应用私钥PKCS8.txt" in USER_FRIENDLY_ERROR
    assert "应用私钥RSA2048.txt" in USER_FRIENDLY_ERROR
