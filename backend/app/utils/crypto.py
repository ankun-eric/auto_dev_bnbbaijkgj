"""[支付配置 PRD v1.0] 敏感字段 AES-256-GCM 加解密 + 掩码工具。

设计要点：
1. 密钥来源：环境变量 PAYMENT_CONFIG_ENCRYPTION_KEY（base64 或 hex 编码 32 字节）；
   未配置时使用项目内固定 fallback 32 字节（仅用于开发/演示，生产环境必须通过
   docker-compose 注入）。
2. 加密格式：`ENC::AES256::<base64(nonce(12) + ciphertext + tag)>`
3. 掩码规则：原文 < 4 → 全 `****`；否则 `****` + 原文末 4 位。
4. 函数全部为同步纯函数，无 IO，方便在 SQLAlchemy 模型 / API 层任意位置调用。
"""
from __future__ import annotations

import base64
import binascii
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# 32 字节 fallback key（仅用于本地/演示；生产请通过环境变量覆盖）
_FALLBACK_KEY_HEX = "8f3b2e1c4a5d6e7f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f"

ENC_PREFIX = "ENC::AES256::"


def _load_key() -> bytes:
    """读取 32 字节密钥。支持 base64 / hex / 原始 32 字节。"""
    raw = os.environ.get("PAYMENT_CONFIG_ENCRYPTION_KEY", "")
    if raw:
        # 优先 base64
        try:
            decoded = base64.b64decode(raw, validate=True)
            if len(decoded) == 32:
                return decoded
        except (binascii.Error, ValueError):
            pass
        # 再试 hex
        try:
            decoded = bytes.fromhex(raw)
            if len(decoded) == 32:
                return decoded
        except ValueError:
            pass
        # 直接当 utf-8 字节
        b = raw.encode("utf-8")
        if len(b) == 32:
            return b
        # 不合法则告警并使用 fallback（不抛异常以免后端启动失败）
        import logging
        logging.getLogger(__name__).warning(
            "PAYMENT_CONFIG_ENCRYPTION_KEY 长度/编码不符合 32 字节要求，使用 fallback key"
        )
    return bytes.fromhex(_FALLBACK_KEY_HEX)


def is_encrypted(value: Optional[str]) -> bool:
    return isinstance(value, str) and value.startswith(ENC_PREFIX)


def encrypt_value(plaintext: Optional[str]) -> Optional[str]:
    """将明文加密为 ENC::AES256::<b64> 字符串。空字符串/None → 直接原样返回。

    若已加密，则不重复加密。
    """
    if plaintext is None:
        return None
    if plaintext == "":
        return ""
    if is_encrypted(plaintext):
        return plaintext
    key = _load_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    blob = base64.b64encode(nonce + ct).decode("ascii")
    return f"{ENC_PREFIX}{blob}"


def decrypt_value(ciphertext: Optional[str]) -> Optional[str]:
    """将 ENC::AES256::... 解密回明文；非加密格式则原样返回。

    解密失败（如密钥变更、数据损坏）时返回空字符串并打警告，不抛异常。
    """
    if ciphertext is None:
        return None
    if not is_encrypted(ciphertext):
        return ciphertext
    body = ciphertext[len(ENC_PREFIX):]
    try:
        raw = base64.b64decode(body)
        nonce, ct = raw[:12], raw[12:]
        key = _load_key()
        aesgcm = AESGCM(key)
        pt = aesgcm.decrypt(nonce, ct, None)
        return pt.decode("utf-8")
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).error("payment_config decrypt failed: %s", e)
        return ""


def mask_value(value: Optional[str]) -> str:
    """末 4 位掩码。空 → 空字符串；< 4 字符全 ****。"""
    if value is None:
        return ""
    s = str(value)
    if s == "":
        return ""
    if len(s) < 4:
        return "****"
    return "****" + s[-4:]


def mask_secret(stored_value: Optional[str]) -> str:
    """对存储值（可能是 ENC::... 也可能是明文）先解密再掩码。"""
    if stored_value is None or stored_value == "":
        return ""
    plain = decrypt_value(stored_value)
    return mask_value(plain)
