"""[Bug 修复 2026-05-05] 支付宝应用私钥归一化（兼容多种形态）。

背景与上一版差异
-----------------

上一版（2026-05-05 早些时候）实现把校验范围**收窄**到「仅中间 Base64（PKCS#8）」单一
形态：检测到 ``-----BEGIN----- / -----END-----`` 即短路报错，也不接受 PKCS#1（即
``应用私钥RSA2048.txt`` 那种）裸 Base64。结果：

    运营人员在 admin-web「支付配置」页面把 ``应用私钥RSA2048.txt`` 内容直接粘贴 →
    后端报「应用私钥格式不被支持。请使用「应用私钥PKCS8.txt」（不是 RSA2048.txt）」。

支付宝官方密钥工具会**同时**生成 ``应用私钥PKCS8.txt``（PKCS#8）和
``应用私钥RSA2048.txt``（PKCS#1），让运营人员自己分辨两者既不友好也容易出错。

本次修复：**容错地接受任何一种支付宝官方工具/openssl 命令产出的合法 RSA 私钥**，
统一归一化为 PKCS#8 PEM 字符串入库；下游 ``alipay_service`` 完全不需要改动。

支持的输入形态（PRD §3.2）
--------------------------

1. PKCS#8 中间 Base64（无头尾）          —— ``应用私钥PKCS8.txt`` 直接复制
2. PKCS#8 完整 PEM（含 BEGIN PRIVATE KEY）—— 用户复制时一起带上头尾
3. PKCS#1 中间 Base64（无头尾）          —— ``应用私钥RSA2048.txt`` 直接复制
4. PKCS#1 完整 PEM（含 BEGIN RSA PRIVATE KEY）—— 部分老工具 / openssl 输出
5. 任一以上形态 + 不可见字符（BOM / 零宽 / 全角空格 / 换行 / Tab）
6. 公钥误粘贴 → 给出针对性报错

归一化流程（PRD §4.1）
----------------------

::

    raw
     │ ① 不可见字符清洗
     ▼
    s
     │ ② 含 BEGIN/END？ ──是──▶ 直接交给 cryptography.load_pem_private_key
     │                                  │
     │ ③ 否                              │ 成功 → ⑥ 序列化为 PKCS#8 PEM ✅
     ▼                                  │ 失败 → 检测公钥 → 分支化报错
    payload (合法 base64 字符)           │
     │
     │ ④ 包装为 PKCS#8 PEM 加载  成功 ──▶ ⑥
     │                            失败
     │ ⑤ 兜底包装为 PKCS#1 PEM    成功 ──▶ ⑥
     │  (BEGIN RSA PRIVATE KEY)   失败
     │
     ▼ 检测公钥 / Base64 长度 → 分支化报错

对外 API
--------

- ``normalize_rsa_private_key(raw)``：归一化为 PKCS#8 PEM；失败抛
  ``InvalidRSAPrivateKeyError``
- ``validate_rsa_private_key(raw)``：仅校验，返回 ``(ok, normalized, reason)``，
  保存接口直接使用此函数

向后兼容
--------

为了让既有测试 / 调用方继续可用，保留以下名称（值已按新语义调整）：

- ``USER_FRIENDLY_ERROR``      —— 等于 ``ERROR_INVALID_FORMAT``
- ``ERROR_HAS_PEM_HEADERS``    —— 兼容老用例：值更新为「我们已支持含头尾的 PEM，
  当前文案已不再使用」的占位说明；任何含头尾的合法私钥都会被归一化通过。
- ``ERROR_INVALID_FORMAT``     —— 通用「无法识别」文案
- ``ERROR_LOOKS_LIKE_PUBLIC_KEY`` —— 「您粘贴的是公钥不是私钥」分支化文案
- ``ERROR_INCOMPLETE_BASE64``    —— 「内容看起来不完整」分支化文案

日志安全：任何环节**严禁**把私钥原文落到日志，只允许打印「长度 / 是否含 BEGIN
等元信息」。
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


# ─────────────── 报错文案（分支化） ───────────────

#: 通用「无法识别」文案
ERROR_INVALID_FORMAT = (
    "应用私钥无法识别。请确认您粘贴的是支付宝密钥工具生成的「应用私钥」内容"
    "（PKCS8.txt 或 RSA2048.txt 任一即可）。"
)

#: 「您粘贴的是公钥不是私钥」分支化文案
ERROR_LOOKS_LIKE_PUBLIC_KEY = (
    "您粘贴的内容看起来是「公钥」而不是「私钥」。请检查文件是否为应用私钥（PKCS8.txt 或 RSA2048.txt）。"
)

#: 「内容看起来不完整」分支化文案
ERROR_INCOMPLETE_BASE64 = (
    "私钥内容看起来不完整，请重新完整复制粘贴。"
)

#: 兼容老调用方：保留 USER_FRIENDLY_ERROR 常量（指向通用无效文案）
USER_FRIENDLY_ERROR = ERROR_INVALID_FORMAT

#: 兼容老调用方：保留 ERROR_HAS_PEM_HEADERS 名称。
#: 修复后含头尾的 PEM 会被自动接受、不会触发该报错；保留此常量仅为避免 import 失败。
ERROR_HAS_PEM_HEADERS = ERROR_INVALID_FORMAT


class InvalidRSAPrivateKeyError(ValueError):
    """私钥格式无法识别 / 解析失败时抛出。文案对终端用户友好。"""


# ─────────────── 内部工具 ───────────────


_PEM_BEGIN_RE = re.compile(r"-----BEGIN[^-]*-----")
_PEM_END_RE = re.compile(r"-----END[^-]*-----")
_PEM_PUBLIC_BEGIN_RE = re.compile(r"-----BEGIN[^-]*PUBLIC KEY-----", re.IGNORECASE)

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
    """检测输入中是否出现 -----BEGIN----- 或 -----END----- 关键标记。"""
    return bool(_PEM_BEGIN_RE.search(s) or _PEM_END_RE.search(s))


def _looks_like_public_key(s: str) -> bool:
    """检测输入是否是 BEGIN PUBLIC KEY / BEGIN RSA PUBLIC KEY 形态的公钥。"""
    return bool(_PEM_PUBLIC_BEGIN_RE.search(s or ""))


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


def _wrap_pkcs1_pem(b64_body: str) -> str:
    return (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        + _wrap_base64_lines(b64_body)
        + "\n-----END RSA PRIVATE KEY-----\n"
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


def _try_load_public_pem(pem: str) -> bool:
    """尝试用 cryptography 加载 PEM 公钥；成功返回 True。

    用于把「用户粘了公钥」与「乱码」区分开来，给出针对性报错。
    """
    try:
        serialization.load_pem_public_key(pem.encode("utf-8"))
        return True
    except Exception:  # noqa: BLE001
        return False


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
    """把支付宝应用私钥的任一合法形态归一化为 PKCS#8 PEM 字符串。

    支持形态详见模块文档（PKCS#8/PKCS#1，含头尾或不含头尾，含不可见字符）。

    成功 → 返回标准 PKCS#8 PEM（``-----BEGIN PRIVATE KEY-----`` 包裹的多行字符串）
    失败 → 抛 ``InvalidRSAPrivateKeyError``，并附带分支化文案
    """
    if not raw or not raw.strip():
        raise InvalidRSAPrivateKeyError(ERROR_INVALID_FORMAT)

    # ① 不可见字符清洗
    s = _strip(raw)

    # ② 若含 BEGIN/END，直接尝试用 cryptography 加载（同时支持 PKCS#1/PKCS#8/openssl）
    if _has_pem_headers(s):
        # ②-a 先看是否是公钥误粘贴
        if _looks_like_public_key(s) and _try_load_public_pem(s):
            raise InvalidRSAPrivateKeyError(ERROR_LOOKS_LIKE_PUBLIC_KEY)

        # ②-b 直接当作 PEM 加载（cryptography 自带 PKCS#1/PKCS#8 兼容）
        key = _try_load_pem(s)
        if key is not None:
            return _serialize_to_pkcs8_pem(key)

        # ②-c 部分粘贴会丢失 base64 中间换行，导致直接加载失败；
        #     提取裸 base64 后用 PKCS#8 / PKCS#1 包装兜底
        payload = _extract_base64_payload(s)
        if payload:
            for wrapper in (_wrap_pkcs8_pem, _wrap_pkcs1_pem):
                key = _try_load_pem(wrapper(payload))
                if key is not None:
                    return _serialize_to_pkcs8_pem(key)

        # ②-d 走到这里说明含 PEM 头尾但内容已损坏 / 不是私钥
        raise InvalidRSAPrivateKeyError(ERROR_INVALID_FORMAT)

    # ③ 不含头尾：提取所有合法 Base64 字符
    payload = _extract_base64_payload(s)
    if not payload:
        raise InvalidRSAPrivateKeyError(ERROR_INVALID_FORMAT)

    # 长度太短肯定不是 RSA 2048 的私钥（粗筛，避免误把短串报成「不完整」）
    # PKCS#8 / PKCS#1 RSA 2048 base64 长度均 > 1000
    if len(payload) < 200:
        raise InvalidRSAPrivateKeyError(ERROR_INVALID_FORMAT)

    # ④ 先尝试包装为 PKCS#8 加载
    key = _try_load_pem(_wrap_pkcs8_pem(payload))
    if key is not None:
        return _serialize_to_pkcs8_pem(key)

    # ⑤ 兜底包装为 PKCS#1 加载
    key = _try_load_pem(_wrap_pkcs1_pem(payload))
    if key is not None:
        return _serialize_to_pkcs8_pem(key)

    # ⑥ 检测：是否是公钥的「中间 Base64」？给出针对性报错
    #    PKCS#8 公钥（SubjectPublicKeyInfo）也能用 PUBLIC KEY 头加载
    pub_pem_pkcs8 = (
        "-----BEGIN PUBLIC KEY-----\n"
        + _wrap_base64_lines(payload)
        + "\n-----END PUBLIC KEY-----\n"
    )
    pub_pem_pkcs1 = (
        "-----BEGIN RSA PUBLIC KEY-----\n"
        + _wrap_base64_lines(payload)
        + "\n-----END RSA PUBLIC KEY-----\n"
    )
    if _try_load_public_pem(pub_pem_pkcs8) or _try_load_public_pem(pub_pem_pkcs1):
        raise InvalidRSAPrivateKeyError(ERROR_LOOKS_LIKE_PUBLIC_KEY)

    # ⑦ 长度看起来像 PKCS#8 / PKCS#1 但解析失败 → 提示「不完整」
    if 800 <= len(payload) < 1500:
        raise InvalidRSAPrivateKeyError(ERROR_INCOMPLETE_BASE64)

    # ⑧ 其他情况：通用无法识别
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
