"""[Bug 修复 2026-05-05] 支付宝 RSA 私钥格式自适应工具。

背景：支付宝官方密钥工具会同时生成两个文件：
  - 应用私钥RSA2048.txt → PKCS#1 格式（裸 base64）
  - 应用私钥PKCS8.txt   → PKCS#8 格式（裸 base64）
现代密码学库（python-alipay-sdk + cryptography）默认按 PKCS#8 解析私钥，
若用户误粘 PKCS#1 内容（含/不含 PEM 头），底层会抛 `RSA key format is not supported`。

本模块提供两个对外函数：
  - normalize_rsa_private_key(raw): 将任意形态私钥统一标准化为 PKCS#8 PEM 字符串
  - validate_rsa_private_key(raw):  仅校验，不抛异常（保存环节使用）

支持的输入形态：
  1) PKCS#8 + PEM 头（"-----BEGIN PRIVATE KEY-----" ...）         （理想形态）
  2) PKCS#8 + 裸 base64                                           （应用私钥PKCS8.txt）
  3) PKCS#1 + PEM 头（"-----BEGIN RSA PRIVATE KEY-----" ...）
  4) PKCS#1 + 裸 base64                                           （应用私钥RSA2048.txt）
"""
from __future__ import annotations

import base64
import re
from typing import Optional, Tuple

# Cryptography 在本项目已被引入（python-alipay-sdk 依赖），无需新增依赖
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


# ─────────────── 友好错误文案 ───────────────

USER_FRIENDLY_ERROR = (
    "「应用私钥」格式不被支持。请使用支付宝开放平台「密钥工具」生成的 "
    "「应用私钥PKCS8.txt」文件中的内容（注意：不是「应用私钥RSA2048.txt」）。"
)


class InvalidRSAPrivateKeyError(ValueError):
    """私钥格式无法识别 / 解析失败时抛出。文案对终端用户友好。"""


# ─────────────── 内部工具 ───────────────


_PEM_BEGIN_RE = re.compile(r"-----BEGIN [A-Z ]+-----")
_PEM_END_RE = re.compile(r"-----END [A-Z ]+-----")


def _strip(s: str) -> str:
    return (s or "").strip().replace("\r\n", "\n").replace("\r", "\n")


def _has_pem_headers(s: str) -> bool:
    return bool(_PEM_BEGIN_RE.search(s) and _PEM_END_RE.search(s))


def _wrap_base64_lines(b64: str, width: int = 64) -> str:
    """对长 base64 字符串按 64 字符换行，返回 PEM body。"""
    cleaned = re.sub(r"\s+", "", b64 or "")
    return "\n".join(cleaned[i : i + width] for i in range(0, len(cleaned), width))


def _wrap_pkcs1_pem(b64_body: str) -> str:
    return (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        + _wrap_base64_lines(b64_body)
        + "\n-----END RSA PRIVATE KEY-----\n"
    )


def _wrap_pkcs8_pem(b64_body: str) -> str:
    return (
        "-----BEGIN PRIVATE KEY-----\n"
        + _wrap_base64_lines(b64_body)
        + "\n-----END PRIVATE KEY-----\n"
    )


def _looks_like_base64(s: str) -> bool:
    """粗略判断是否为 base64：仅包含 A-Z a-z 0-9 + / = 和空白字符。"""
    cleaned = re.sub(r"\s+", "", s or "")
    if not cleaned:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/=]+", cleaned))


def _try_load_pem(pem: str) -> Optional[rsa.RSAPrivateKey]:
    """尝试用 cryptography 加载 PEM 私钥；失败返回 None。"""
    try:
        key = serialization.load_pem_private_key(
            pem.encode("utf-8"), password=None
        )
        if isinstance(key, rsa.RSAPrivateKey):
            return key
        return None
    except Exception:  # noqa: BLE001
        return None


def _serialize_to_pkcs8_pem(key: rsa.RSAPrivateKey) -> str:
    """把 RSAPrivateKey 序列化为标准 PKCS#8 PEM 字符串。"""
    pem_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem_bytes.decode("utf-8")


# ─────────────── 对外接口 ───────────────


def normalize_rsa_private_key(raw: str) -> str:
    """把任意形态的 RSA 私钥标准化为 PKCS#8 PEM 字符串。

    标准化策略：
      - 如果输入含 PEM 头，直接用 cryptography 加载（同时支持 PKCS#1 与 PKCS#8 的 PEM）
      - 如果输入是裸 base64：
          先尝试包装为 PKCS#8 PEM 加载；失败再包装为 PKCS#1 PEM 加载
      - 加载成功后统一序列化为 PKCS#8 PEM 输出
      - 任何形式都失败 → 抛 InvalidRSAPrivateKeyError(USER_FRIENDLY_ERROR)
    """
    if not raw or not raw.strip():
        raise InvalidRSAPrivateKeyError("应用私钥不能为空")

    s = _strip(raw)

    # 情形 1：含 PEM 头（PKCS#1 或 PKCS#8）
    if _has_pem_headers(s):
        key = _try_load_pem(s)
        if key is not None:
            return _serialize_to_pkcs8_pem(key)
        # PEM 头存在但仍加载失败 → 直接报友好错误
        raise InvalidRSAPrivateKeyError(USER_FRIENDLY_ERROR)

    # 情形 2：裸 base64（无 PEM 头）
    if not _looks_like_base64(s):
        raise InvalidRSAPrivateKeyError(
            "私钥内容包含非 base64 字符，无法识别。" + USER_FRIENDLY_ERROR
        )

    # 先尝试 PKCS#8（最常用 / 推荐）
    pkcs8_pem = _wrap_pkcs8_pem(s)
    key = _try_load_pem(pkcs8_pem)
    if key is not None:
        return _serialize_to_pkcs8_pem(key)

    # 再尝试 PKCS#1（应用私钥RSA2048.txt 文件内容）
    pkcs1_pem = _wrap_pkcs1_pem(s)
    key = _try_load_pem(pkcs1_pem)
    if key is not None:
        return _serialize_to_pkcs8_pem(key)

    raise InvalidRSAPrivateKeyError(USER_FRIENDLY_ERROR)


def validate_rsa_private_key(raw: str) -> Tuple[bool, Optional[str], str]:
    """仅校验私钥格式，不抛异常。返回 (ok, normalized_pem, reason)。

    - ok=True：normalized_pem 为已标准化的 PKCS#8 PEM；reason 固定为 ""
    - ok=False：normalized_pem 为 None；reason 为给用户的友好文案
    """
    try:
        normalized = normalize_rsa_private_key(raw)
        return True, normalized, ""
    except InvalidRSAPrivateKeyError as e:
        return False, None, str(e)
    except Exception as e:  # noqa: BLE001
        return False, None, f"{USER_FRIENDLY_ERROR}（内部错误：{e}）"
