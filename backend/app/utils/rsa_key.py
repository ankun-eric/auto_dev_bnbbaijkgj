"""[需求 2026-05-05] 支付宝应用私钥校验工具（收窄至「仅中间 Base64」单一形态）。

背景：支付宝官方密钥工具实际产出的私钥内容仅为「中间 Base64 部分」（无 PEM 头尾）。
此前后台同时兼容多种形态（带 PKCS#1 / PKCS#8 头尾、纯 Base64、含脏字符），
导致报错文案歧义、用户反复踩坑。

本次需求：**收窄校验范围至「仅中间 Base64」单一形态**，让校验更聚焦、报错更精准。

校验流程：
  ① 清洗不可见字符（BOM、零宽空格、全角空格、Tab、换行、普通空格）
  ② 检测是否含 -----BEGIN----- / -----END----- 关键标记
        是 → 抛错："请只粘贴中间 Base64 部分（去掉 BEGIN/END 两行）。"
        否 → ③ 提取所有合法 Base64 字符（A-Z a-z 0-9 + / =）
             → ④ Base64 解码 + ASN.1（PKCS#8）解析
                  成功 → 标准化为 PKCS#8 PEM 入库 ✅
                  失败 → 抛错："应用私钥格式不被支持。请粘贴密钥工具生成的中间 Base64 内容。"

对外函数：
  - normalize_rsa_private_key(raw): 将「中间 Base64」标准化为 PKCS#8 PEM 字符串
  - validate_rsa_private_key(raw):  仅校验，不抛异常（保存环节使用）
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


# ─────────────── 报错文案（收窄后分支化） ───────────────

#: 含 BEGIN/END 头尾时的报错文案（PRD §三）
ERROR_HAS_PEM_HEADERS = (
    "请只粘贴中间 Base64 部分（去掉 BEGIN/END 两行）。"
)

#: 其他无效输入的统一报错文案（PRD §三）
ERROR_INVALID_FORMAT = (
    "应用私钥格式不被支持。请粘贴密钥工具生成的中间 Base64 内容。"
)

#: 兼容老调用方：保留 USER_FRIENDLY_ERROR 常量（指向「其他无效」分支文案）
USER_FRIENDLY_ERROR = ERROR_INVALID_FORMAT


class InvalidRSAPrivateKeyError(ValueError):
    """私钥格式无法识别 / 解析失败时抛出。文案对终端用户友好。"""


# ─────────────── 内部工具 ───────────────


_PEM_BEGIN_RE = re.compile(r"-----BEGIN[^-]*-----")
_PEM_END_RE = re.compile(r"-----END[^-]*-----")

# 常见的不可见 / 易混淆字符（粘贴时极易误带，必须主动清除）
#   \ufeff           UTF-8 BOM
#   \u200b - \u200f  零宽字符（零宽空格、零宽连接符等）
#   \u2028 \u2029    行 / 段落分隔符
#   \u3000           全角空格（中文输入法）
#   \u00a0           不间断空格（从网页复制极常见）
_INVISIBLE_CHARS_RE = re.compile(
    r"[\ufeff\u200b-\u200f\u2028\u2029\u3000\u00a0]"
)

# 合法的 base64 字符集合（不含换行/空白）
_BASE64_CHAR_RE = re.compile(r"[A-Za-z0-9+/=]")


def _strip(s: str) -> str:
    """规范化输入：统一换行符、去除首尾空白、剔除常见不可见字符。"""
    if not s:
        return ""
    cleaned = _INVISIBLE_CHARS_RE.sub(" ", s)
    return cleaned.strip().replace("\r\n", "\n").replace("\r", "\n")


def _has_pem_headers(s: str) -> bool:
    """检测输入中是否出现 -----BEGIN----- 或 -----END----- 关键标记。

    收窄后只要任一出现即视为「含头尾」，立刻短路抛错。
    """
    return bool(_PEM_BEGIN_RE.search(s) or _PEM_END_RE.search(s))


def _wrap_base64_lines(b64: str, width: int = 64) -> str:
    """对长 base64 字符串按 64 字符换行，返回 PEM body。"""
    cleaned = re.sub(r"\s+", "", b64 or "")
    return "\n".join(cleaned[i : i + width] for i in range(0, len(cleaned), width))


def _extract_base64_payload(s: str) -> str:
    """从输入中提取所有合法 base64 字符，拼成连续字符串。"""
    return "".join(_BASE64_CHAR_RE.findall(s or ""))


def _wrap_pkcs8_pem(b64_body: str) -> str:
    return (
        "-----BEGIN PRIVATE KEY-----\n"
        + _wrap_base64_lines(b64_body)
        + "\n-----END PRIVATE KEY-----\n"
    )


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
    """把「中间 Base64」形态的支付宝应用私钥标准化为 PKCS#8 PEM 字符串。

    收窄后的校验流程（PRD §四）：
      ① 清洗不可见字符（BOM、零宽空格、全角空格、Tab、换行、普通空格）
      ② 检测 -----BEGIN----- / -----END----- 关键标记
            是 → 抛错 ERROR_HAS_PEM_HEADERS
            否 → ③ 提取所有合法 Base64 字符
                 → ④ Base64 解码 + ASN.1（PKCS#8）解析
                      成功 → 标准化为 PKCS#8 PEM 入库
                      失败 → 抛错 ERROR_INVALID_FORMAT

    注意：本函数**不再**接受任何含 PEM 头尾的输入；也不再尝试 PKCS#1 兜底包装。
    """
    if not raw or not raw.strip():
        raise InvalidRSAPrivateKeyError(ERROR_INVALID_FORMAT)

    # ① 不可见字符清洗
    s = _strip(raw)

    # ② 头尾检测短路
    if _has_pem_headers(s):
        raise InvalidRSAPrivateKeyError(ERROR_HAS_PEM_HEADERS)

    # ③ 提取所有合法 Base64 字符
    payload = _extract_base64_payload(s)
    if not payload:
        raise InvalidRSAPrivateKeyError(ERROR_INVALID_FORMAT)

    # ④ 包装为 PKCS#8 PEM 后用 cryptography 解析（内部完成 Base64 解码 + ASN.1 解析）
    pkcs8_pem = _wrap_pkcs8_pem(payload)
    key = _try_load_pem(pkcs8_pem)
    if key is not None:
        return _serialize_to_pkcs8_pem(key)

    raise InvalidRSAPrivateKeyError(ERROR_INVALID_FORMAT)


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
        return False, None, f"{ERROR_INVALID_FORMAT}（内部错误：{e}）"
