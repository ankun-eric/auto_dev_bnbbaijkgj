"""[微信小程序支付完整接入 v1.0]

微信支付 API v3 服务层模块 — 统一负责：
1. 从「支付配置」表读取微信小程序支付通道参数（mch_id、api_v3_key、cert_serial_no、private_key、appid）
2. 封装微信支付 API v3 HTTP 签名（WECHATPAY2-SHA256-RSA）
3. 提供高层方法：
   - create_jsapi_order：调 POST /v3/pay/transactions/jsapi 生成 prepay_id
   - generate_pay_sign：为小程序 wx.requestPayment() 生成签名参数包
   - query_order_by_out_trade_no：查单（用于测试连接 / 对账）
   - create_refund：调 POST /v3/refund/domestic/refunds 发起退款
   - get_platform_certificates：获取平台证书（用于回调验签）
   - decrypt_callback_resource：解密回调报文（AEAD_AES_256_GCM）
   - verify_callback_sign：验证回调签名

设计要点：
- 签名方式：HTTP Authorization 头使用 WECHATPAY2-SHA256-RSA
- 平台证书缓存：首次启动自动获取，过期前自动更新
- 敏感字段（private_key、api_v3_key）从 DB 解密后使用，不落日志

Reference: 微信支付 API v3 官方文档
"""
from __future__ import annotations

import base64
import json
import logging
import uuid as _uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from app.utils.crypto import (
    DecryptionError,
    decrypt_value,
    is_encrypted,
)

logger = logging.getLogger(__name__)

WECHAT_API_HOST = "https://api.mch.weixin.qq.com"

# ─────────────── 平台证书缓存 ───────────────
# key: serial_no (str), value: {"public_key": PEM str, "expire_time": datetime}
_PLATFORM_CERT_CACHE: dict[str, dict[str, Any]] = {}


def _load_private_key(pem_str: str):
    """从 PEM 字符串加载 RSA 私钥对象。"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key_data = pem_str.strip()
    if not key_data.startswith("-----BEGIN"):
        key_data = "-----BEGIN PRIVATE KEY-----\n" + key_data + "\n-----END PRIVATE KEY-----"
    key_bytes = key_data.encode("utf-8")
    try:
        return serialization.load_pem_private_key(key_bytes, password=None)
    except Exception:
        try:
            return serialization.load_pem_private_key(
                key_bytes.replace(b"PRIVATE KEY", b"RSA PRIVATE KEY"),
                password=None,
            )
        except Exception:
            pass
        raise


def _rsa_sign(private_key_pem: str, sign_str: str) -> str:
    """使用商户私钥做 SHA256withRSA 签名，返回 base64 编码。"""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key = _load_private_key(private_key_pem)
    signature = private_key.sign(
        sign_str.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


def _build_authorization(
    method: str,
    url_path: str,
    body: str,
    mch_id: str,
    cert_serial_no: str,
    private_key_pem: str,
) -> str:
    """构建 WECHATPAY2-SHA256-RSA 签名 Authorization 头。

    签名串格式：
        HTTP方法\n
        URL（不含域名）\n
        时间戳\n
        随机串\n
        请求体\n

    返回签名后的 Authorization 头字符串。
    """
    timestamp = str(int(datetime.utcnow().timestamp()))
    nonce_str = _uuid.uuid4().hex[:32]

    sign_str = f"{method}\n{url_path}\n{timestamp}\n{nonce_str}\n{body}\n"
    signature = _rsa_sign(private_key_pem, sign_str)

    auth = (
        f'WECHATPAY2-SHA256-RSA mchid="{mch_id}",'
        f'nonce_str="{nonce_str}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{cert_serial_no}",'
        f'signature="{signature}"'
    )
    return auth


async def _wechat_request(
    method: str,
    url_path: str,
    body: Optional[dict] = None,
    mch_id: str = "",
    cert_serial_no: str = "",
    private_key_pem: str = "",
    extra_headers: Optional[dict] = None,
    timeout: float = 15.0,
) -> dict:
    """统一的微信支付 API v3 HTTP 请求封装。

    Returns:
        dict: API 响应 JSON 或错误信息
    Raises:
        httpx.HTTPStatusError: HTTP 错误
        ValueError: 参数/签名错误
    """
    url = f"{WECHAT_API_HOST}{url_path}"
    body_str = json.dumps(body, ensure_ascii=False) if body else ""

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "BiniHealth/1.0",
    }

    if mch_id and cert_serial_no and private_key_pem:
        auth = _build_authorization(
            method=method,
            url_path=url_path,
            body=body_str,
            mch_id=mch_id,
            cert_serial_no=cert_serial_no,
            private_key_pem=private_key_pem,
        )
        headers["Authorization"] = auth

    if extra_headers:
        headers.update(extra_headers)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        elif method == "POST":
            resp = await client.post(url, headers=headers, content=body_str)
        elif method == "PUT":
            resp = await client.put(url, headers=headers, content=body_str)
        elif method == "DELETE":
            resp = await client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    try:
        result = resp.json()
    except Exception:
        result = {"raw_body": resp.text}

    if resp.status_code >= 400:
        logger.warning(
            "wechat_pay API error: %s %s → %s, body=%s",
            method, url_path, resp.status_code, result,
        )

    return {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "data": result,
    }


async def _get_runtime_config(db, channel_code: str = "wechat_miniprogram") -> dict:
    """从 DB 获取并解密微信支付通道配置。"""
    from sqlalchemy import select
    from app.models.models import PaymentChannel
    from app.api.payment_config import _decrypt_for_runtime

    res = await db.execute(
        select(PaymentChannel).where(PaymentChannel.channel_code == channel_code)
    )
    ch = res.scalar_one_or_none()
    if ch is None:
        raise ValueError(f"未找到支付通道：{channel_code}")
    if not ch.is_enabled or not ch.is_complete:
        raise ValueError(f"支付通道 {channel_code} 未启用或配置不完整")

    return _decrypt_for_runtime(channel_code, ch.config_json or {})


# ─────────────── 平台证书 ───────────────


async def fetch_platform_certificates(
    mch_id: str,
    cert_serial_no: str,
    private_key_pem: str,
    api_v3_key: str,
) -> list[dict]:
    """获取微信支付平台证书并缓存。

    调用 GET /v3/certificates，解码证书链中的公钥，缓存到内存。
    返回证书列表 [{serial_no, public_key_pem, expire_time}]。
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    resp = await _wechat_request(
        method="GET",
        url_path="/v3/certificates",
        mch_id=mch_id,
        cert_serial_no=cert_serial_no,
        private_key_pem=private_key_pem,
    )

    if resp["status_code"] != 200:
        raise RuntimeError(f"获取平台证书失败: {resp['data']}")

    data = resp["data"]
    certificates = data.get("data", [])
    result = []

    for cert_entry in certificates:
        serial_no = cert_entry.get("serial_no", "")
        encrypt_cert = cert_entry.get("encrypt_certificate", {})
        algorithm = encrypt_cert.get("algorithm", "")
        ciphertext = encrypt_cert.get("ciphertext", "")
        associated_data = encrypt_cert.get("associated_data", "") or ""
        nonce = encrypt_cert.get("nonce", "")

        if algorithm == "AEAD_AES_256_GCM":
            pem_cert = _aes_gcm_decrypt(
                ciphertext=ciphertext,
                key=api_v3_key,
                nonce=nonce,
                associated_data=associated_data,
            )
        else:
            logger.warning("未知证书加密算法: %s", algorithm)
            continue

        cert_obj = x509.load_pem_x509_certificate(pem_cert.encode("utf-8"))
        public_key = cert_obj.public_key()
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        expire_time = cert_obj.not_valid_after_utc

        result.append({
            "serial_no": serial_no,
            "public_key_pem": public_key_pem,
            "expire_time": expire_time,
        })

    for cert_info in result:
        _PLATFORM_CERT_CACHE[cert_info["serial_no"]] = {
            "public_key": cert_info["public_key_pem"],
            "expire_time": cert_info["expire_time"],
        }

    logger.info(
        "微信支付平台证书已更新：共 %d 张，序列号=%s",
        len(result),
        [c["serial_no"] for c in result],
    )
    return result


async def ensure_platform_certificates(
    mch_id: str,
    cert_serial_no: str,
    private_key_pem: str,
    api_v3_key: str,
) -> None:
    """确保平台证书缓存可用（首次获取 / 过期自动更新）。"""
    now = datetime.utcnow()
    need_refresh = True

    if _PLATFORM_CERT_CACHE:
        all_valid = True
        for sn, entry in _PLATFORM_CERT_CACHE.items():
            expire = entry.get("expire_time")
            if expire is None:
                all_valid = False
                break
            if expire.tzinfo is not None:
                expire = expire.replace(tzinfo=None)
            if now + timedelta(hours=1) >= expire:
                all_valid = False
                break
        need_refresh = not all_valid

    if need_refresh:
        await fetch_platform_certificates(
            mch_id=mch_id,
            cert_serial_no=cert_serial_no,
            private_key_pem=private_key_pem,
            api_v3_key=api_v3_key,
        )


def get_platform_public_key(serial_no: str) -> Optional[str]:
    """获取缓存的平台证书公钥（PEM 格式）。"""
    entry = _PLATFORM_CERT_CACHE.get(serial_no)
    if entry:
        return entry.get("public_key")
    return None


# ─────────────── AEAD_AES_256_GCM 解密 ───────────────


def _aes_gcm_decrypt(
    ciphertext: str,
    key: str,
    nonce: str,
    associated_data: str = "",
) -> str:
    """AEAD_AES_256_GCM 解密（用于回调报文解密 和 平台证书解密）。

    key: API v3 密钥（明文）
    ciphertext: base64 编码的密文
    nonce: base64 编码的 nonce
    associated_data: 附加数据（UTF-8 编码）
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    ciphertext_bytes = base64.b64decode(ciphertext)
    nonce_bytes = base64.b64decode(nonce)
    key_bytes = key.encode("utf-8")
    associated_bytes = associated_data.encode("utf-8") if associated_data else b""

    aesgcm = AESGCM(key_bytes)
    plaintext = aesgcm.decrypt(nonce_bytes, ciphertext_bytes, associated_bytes)
    return plaintext.decode("utf-8")


# ─────────────── JSAPI 下单 ───────────────


async def create_jsapi_order(
    *,
    out_trade_no: str,
    total_amount: int,  # 单位：分
    description: str,
    openid: str,
    notify_url: str,
    mch_id: str,
    cert_serial_no: str,
    private_key_pem: str,
    appid: str,
) -> dict:
    """微信支付 JSAPI 下单。

    调用 POST /v3/pay/transactions/jsapi，生成 prepay_id。

    Returns:
        dict: {"prepay_id": "wx..."} 或包含错误信息的响应
    """
    body = {
        "appid": appid,
        "mchid": mch_id,
        "description": description[:127],
        "out_trade_no": out_trade_no,
        "notify_url": notify_url,
        "amount": {
            "total": total_amount,
            "currency": "CNY",
        },
        "payer": {
            "openid": openid,
        },
    }

    resp = await _wechat_request(
        method="POST",
        url_path="/v3/pay/transactions/jsapi",
        body=body,
        mch_id=mch_id,
        cert_serial_no=cert_serial_no,
        private_key_pem=private_key_pem,
    )

    if resp["status_code"] == 200:
        prepay_id = resp["data"].get("prepay_id", "")
        return {"success": True, "prepay_id": prepay_id, "raw": resp["data"]}
    else:
        error_msg = resp["data"].get("message", "未知错误")
        error_code = resp["data"].get("code", "UNKNOWN")
        return {
            "success": False,
            "error_code": error_code,
            "error_message": error_msg,
            "raw": resp["data"],
        }


# ─────────────── 小程序调起支付签名 ───────────────


def generate_pay_sign(
    *,
    prepay_id: str,
    appid: str,
    private_key_pem: str,
) -> dict:
    """为小程序 wx.requestPayment() 生成签名参数包。

    签名串格式：
        appId\n时间戳\n随机串\nprepay_id=xxx\n

    Returns:
        dict: {"appId", "timeStamp", "nonceStr", "package", "signType", "paySign"}
    """
    timestamp = str(int(datetime.utcnow().timestamp()))
    nonce_str = _uuid.uuid4().hex[:32]
    package = f"prepay_id={prepay_id}"

    sign_str = f"{appid}\n{timestamp}\n{nonce_str}\n{package}\n"
    pay_sign = _rsa_sign(private_key_pem, sign_str)

    return {
        "appId": appid,
        "timeStamp": timestamp,
        "nonceStr": nonce_str,
        "package": package,
        "signType": "RSA",
        "paySign": pay_sign,
    }


# ─────────────── 查询订单 ───────────────


async def query_order_by_out_trade_no(
    out_trade_no: str,
    mch_id: str,
    cert_serial_no: str,
    private_key_pem: str,
) -> dict:
    """查询微信支付订单（GET /v3/pay/transactions/out-trade-no/{out_trade_no}）。

    用于测试连接（使用不存在的订单号）和对账。
    """
    url_path = f"/v3/pay/transactions/out-trade-no/{out_trade_no}"
    query = f"?mchid={mch_id}"
    url_path_with_query = url_path + query

    body = ""  # GET 请求体为空
    timestamp = str(int(datetime.utcnow().timestamp()))
    nonce_str = _uuid.uuid4().hex[:32]

    sign_str = f"GET\n{url_path_with_query}\n{timestamp}\n{nonce_str}\n{body}\n"
    signature = _rsa_sign(private_key_pem, sign_str)

    auth = (
        f'WECHATPAY2-SHA256-RSA mchid="{mch_id}",'
        f'nonce_str="{nonce_str}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{cert_serial_no}",'
        f'signature="{signature}"'
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "BiniHealth/1.0",
        "Authorization": auth,
    }

    url = f"{WECHAT_API_HOST}{url_path_with_query}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers)

    try:
        result = resp.json()
    except Exception:
        result = {"raw_body": resp.text}

    return {
        "status_code": resp.status_code,
        "data": result,
    }


# ─────────────── 申请退款 ───────────────


async def create_refund(
    *,
    out_trade_no: str,
    out_refund_no: str,
    total_amount: int,  # 原订单金额，单位：分
    refund_amount: int,  # 退款金额，单位：分
    reason: str = "",
    mch_id: str,
    cert_serial_no: str,
    private_key_pem: str,
) -> dict:
    """微信支付申请退款（POST /v3/refund/domestic/refunds）。

    Args:
        out_trade_no: 原交易订单号
        out_refund_no: 退款单号（商户侧唯一）
        total_amount: 原订单金额（分）
        refund_amount: 退款金额（分）
        reason: 退款原因（可选）
    """
    body = {
        "out_trade_no": out_trade_no,
        "out_refund_no": out_refund_no,
        "amount": {
            "refund": refund_amount,
            "total": total_amount,
            "currency": "CNY",
        },
    }
    if reason:
        body["reason"] = reason[:80]

    resp = await _wechat_request(
        method="POST",
        url_path="/v3/refund/domestic/refunds",
        body=body,
        mch_id=mch_id,
        cert_serial_no=cert_serial_no,
        private_key_pem=private_key_pem,
    )

    if resp["status_code"] == 200:
        data = resp["data"]
        return {
            "success": True,
            "refund_id": data.get("refund_id", ""),
            "out_refund_no": data.get("out_refund_no", ""),
            "status": data.get("status", ""),
            "raw": data,
        }
    else:
        error_msg = resp["data"].get("message", "未知错误")
        error_code = resp["data"].get("code", "UNKNOWN")
        return {
            "success": False,
            "error_code": error_code,
            "error_message": error_msg,
            "raw": resp["data"],
        }


# ─────────────── 回调验证 ───────────────


def verify_callback_sign(
    *,
    timestamp: str,
    nonce_str: str,
    body: str,
    signature: str,
    serial_no: str,
) -> bool:
    """验证微信支付回调签名。

    验签串格式：
        时间戳\n随机串\n请求体\n

    Returns:
        bool: 验签是否通过
    """
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    public_key_pem = get_platform_public_key(serial_no)
    if not public_key_pem:
        logger.warning("未找到平台证书序列号 %s，尝试刷新证书", serial_no)
        return False

    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode("utf-8")
        )
    except Exception as e:
        logger.error("加载平台证书公钥失败: %s", e)
        return False

    sign_str = f"{timestamp}\n{nonce_str}\n{body}\n"
    try:
        sig_bytes = base64.b64decode(signature)
        public_key.verify(
            sig_bytes,
            sign_str.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception as e:
        logger.warning("微信支付回调验签失败: %s", e)
        return False


def decrypt_callback_resource(
    *,
    ciphertext: str,
    nonce: str,
    associated_data: str,
    api_v3_key: str,
) -> dict:
    """解密微信支付回调 resource.ciphertext。

    使用 AEAD_AES_256_GCM 解密。
    key = api_v3_key（明文）
    nonce = resource.nonce
    associated_data = resource.associated_data

    Returns:
        dict: 解密后的业务 JSON（如 transaction 对象）
    """
    plaintext = _aes_gcm_decrypt(
        ciphertext=ciphertext,
        key=api_v3_key,
        nonce=nonce,
        associated_data=associated_data,
    )
    return json.loads(plaintext)
