from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import logging
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import OcrCallRecord, OcrCallStatistics, OcrProviderConfig

logger = logging.getLogger(__name__)

BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_OCR_GENERAL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
BAIDU_OCR_ACCURATE = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"

TENCENT_OCR_ENDPOINT = "ocr.tencentcloudapi.com"
TENCENT_OCR_URL = f"https://{TENCENT_OCR_ENDPOINT}"

ALIYUN_OCR_URL = "https://ocr-api.cn-hangzhou.aliyuncs.com/api/predict/ocr_general"


# ──────────────── Baidu OCR ────────────────


async def get_baidu_access_token(api_key: str, secret_key: str) -> dict:
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(BAIDU_TOKEN_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"百度OCR获取token失败: {data.get('error_description', data)}")
    return {
        "access_token": data["access_token"],
        "expires_in": data.get("expires_in", 2592000),
    }


async def _baidu_ocr(image_data: bytes, config: dict) -> str:
    api_key = config.get("api_key", "")
    secret_key = config.get("secret_key", "")
    ocr_type = config.get("ocr_type", "general_basic")

    cached_token = config.get("access_token")
    expires_str = config.get("token_expires_at")
    token_expires_at = None
    if expires_str:
        try:
            token_expires_at = datetime.fromisoformat(expires_str)
        except (ValueError, TypeError):
            pass

    access_token, _ = await ensure_access_token(api_key, secret_key, cached_token, token_expires_at)

    url = BAIDU_OCR_ACCURATE if ocr_type == "accurate_basic" else BAIDU_OCR_GENERAL
    img_base64 = base64.b64encode(image_data).decode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {"image": img_base64, "language_type": "CHN_ENG"}
    params = {"access_token": access_token}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, data=payload, params=params)
        resp.raise_for_status()
        data = resp.json()

    if "error_code" in data:
        raise RuntimeError(f"百度OCR识别失败({data['error_code']}): {data.get('error_msg', '')}")

    words_result = data.get("words_result", [])
    return "\n".join(item["words"] for item in words_result)


# ──────────────── Tencent OCR (TC3-HMAC-SHA256) ────────────────


def _tc3_sign(secret_key: str, date_str: str, service: str, string_to_sign: str) -> str:
    def _hmac_sha256(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date_str)
    secret_service = _hmac_sha256(secret_date, service)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    return hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()


async def _tencent_ocr(image_data: bytes, config: dict) -> str:
    secret_id = config.get("secret_id", "")
    secret_key = config.get("secret_key", "")
    region = config.get("region", "ap-guangzhou")

    img_base64 = base64.b64encode(image_data).decode("utf-8")
    body_obj = {"ImageBase64": img_base64}
    payload = json.dumps(body_obj)

    service = "ocr"
    action = "GeneralBasicOCR"
    version = "2018-11-19"
    algorithm = "TC3-HMAC-SHA256"
    timestamp = int(time.time())
    date_str = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{TENCENT_OCR_ENDPOINT}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        f"{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n"
        f"{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    )

    credential_scope = f"{date_str}/{service}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

    signature = _tc3_sign(secret_key, date_str, service, string_to_sign)
    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": ct,
        "Host": TENCENT_OCR_ENDPOINT,
        "X-TC-Action": action,
        "X-TC-Version": version,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Region": region,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(TENCENT_OCR_URL, headers=headers, content=payload)
        resp.raise_for_status()
        data = resp.json()

    response_body = data.get("Response", {})
    if "Error" in response_body:
        err = response_body["Error"]
        raise RuntimeError(f"腾讯云OCR失败({err.get('Code','')}): {err.get('Message','')}")

    items = response_body.get("TextDetections", [])
    return "\n".join(item.get("DetectedText", "") for item in items)


# ──────────────── Aliyun OCR (HMAC-SHA1) ────────────────


async def _aliyun_ocr(image_data: bytes, config: dict) -> str:
    access_key_id = config.get("access_key_id", "")
    access_key_secret = config.get("access_key_secret", "")

    img_base64 = base64.b64encode(image_data).decode("utf-8")
    body_obj = {"image": img_base64}
    payload = json.dumps(body_obj)

    nonce = uuid.uuid4().hex
    timestamp_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "x-acs-action": "RecognizeGeneral",
        "x-acs-version": "2021-07-07",
        "x-acs-signature-nonce": nonce,
        "x-acs-date": timestamp_str,
    }

    sorted_headers = sorted(
        [(k.lower(), v) for k, v in headers.items() if k.lower().startswith("x-acs-")],
        key=lambda x: x[0],
    )
    canonical_headers_str = "".join(f"{k}:{v}\n" for k, v in sorted_headers)
    signed_header_keys = ";".join(k for k, _ in sorted_headers)

    hashed_body = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = f"POST\n/\n\n{canonical_headers_str}\n{signed_header_keys}\n{hashed_body}"
    hashed_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"ACS3-HMAC-SHA256\n{hashed_request}"

    signature = hmac.new(
        access_key_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    headers["Authorization"] = (
        f"ACS3-HMAC-SHA256 Credential={access_key_id},"
        f"SignedHeaders={signed_header_keys},Signature={signature}"
    )

    ocr_url = "https://ocr-api.cn-hangzhou.aliyuncs.com"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(ocr_url, headers=headers, content=payload)
        resp.raise_for_status()
        data = resp.json()

    if "Code" in data and data["Code"] != "200":
        raise RuntimeError(f"阿里云OCR失败({data.get('Code','')}): {data.get('Message','')}")

    result_data = data.get("Data", {})
    if isinstance(result_data, str):
        try:
            result_data = json.loads(result_data)
        except json.JSONDecodeError:
            return result_data

    content = result_data.get("content", "")
    if content:
        return content

    prism_data = result_data.get("prism_wordsInfo", [])
    if prism_data:
        return "\n".join(item.get("word", "") for item in prism_data)

    return json.dumps(result_data, ensure_ascii=False) if result_data else ""


# ──────────────── Provider Dispatcher ────────────────


_PROVIDER_MAP = {
    "baidu": _baidu_ocr,
    "tencent": _tencent_ocr,
    "aliyun": _aliyun_ocr,
}


async def ocr_recognize_with_provider(image_data: bytes, provider_name: str, config: dict) -> str:
    handler = _PROVIDER_MAP.get(provider_name)
    if not handler:
        raise RuntimeError(f"不支持的OCR厂商: {provider_name}")
    return await handler(image_data, config)


async def smart_ocr_recognize(
    image_data: bytes,
    db: AsyncSession,
    preferred_provider: str | None = None,
) -> tuple[str, str]:
    """Smart OCR with failover. Returns (text, provider_name)."""
    result = await db.execute(
        select(OcrProviderConfig).where(OcrProviderConfig.is_enabled == True)
    )
    providers = list(result.scalars().all())
    if not providers:
        raise RuntimeError("没有已启用的OCR厂商配置，请先在管理后台配置")

    def _sort_key(p: OcrProviderConfig) -> tuple:
        is_specified = 1 if (preferred_provider and p.provider_name == preferred_provider) else 0
        is_preferred = 1 if p.is_preferred else 0
        return (-is_specified, -is_preferred, p.provider_name)

    providers.sort(key=_sort_key)

    last_error = None
    for provider in providers:
        cfg = provider.config_json or {}
        try:
            text = await ocr_recognize_with_provider(image_data, provider.provider_name, cfg)
            await _update_statistics(db, provider.provider_name, success=True)
            return text, provider.provider_name
        except Exception as e:
            last_error = e
            logger.warning("OCR provider %s failed: %s", provider.provider_name, e)
            await _update_statistics(db, provider.provider_name, success=False)
            continue

    raise RuntimeError(f"所有OCR厂商均识别失败，最后错误: {last_error}")


async def _update_statistics(db: AsyncSession, provider_name: str, success: bool) -> None:
    today = date.today()
    result = await db.execute(
        select(OcrCallStatistics).where(
            OcrCallStatistics.provider_name == provider_name,
            OcrCallStatistics.call_date == today,
        )
    )
    stat = result.scalar_one_or_none()
    if stat:
        stat.total_calls += 1
        if success:
            stat.success_calls += 1
    else:
        db.add(OcrCallStatistics(
            provider_name=provider_name,
            call_date=today,
            total_calls=1,
            success_calls=1 if success else 0,
        ))
    try:
        await db.flush()
    except Exception:
        logger.warning("Failed to update OCR statistics for %s", provider_name, exc_info=True)


# ──────────────── Legacy helpers (kept for backward compat) ────────────────


async def ocr_recognize(image_data: bytes, ocr_type: str, access_token: str) -> str:
    url = BAIDU_OCR_ACCURATE if ocr_type == "accurate_basic" else BAIDU_OCR_GENERAL
    img_base64 = base64.b64encode(image_data).decode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {"image": img_base64, "language_type": "CHN_ENG"}
    params = {"access_token": access_token}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, data=payload, params=params)
        resp.raise_for_status()
        data = resp.json()

    if "error_code" in data:
        raise RuntimeError(f"OCR识别失败({data['error_code']}): {data.get('error_msg', '')}")

    words_result = data.get("words_result", [])
    return "\n".join(item["words"] for item in words_result)


def check_image_quality(image_data: bytes) -> dict:
    size_kb = len(image_data) / 1024
    if size_kb < 10:
        return {"ok": False, "message": "图片文件过小，可能无法识别，请重新拍照"}
    if size_kb > 10 * 1024:
        return {"ok": False, "message": "图片大小超过10MB限制，请压缩后重试"}
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_data))
        width, height = img.size
        if width < 200 or height < 200:
            return {"ok": False, "message": "图片分辨率过低，请上传更清晰的图片"}
    except ImportError:
        pass
    except Exception:
        return {"ok": False, "message": "无法解析图片，请确认文件格式正确"}
    return {"ok": True, "message": "图片质量合格"}


def extract_pdf_text(pdf_data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore[no-redef]
        except ImportError:
            raise RuntimeError("PDF解析库未安装，请联系管理员")
    reader = PdfReader(io.BytesIO(pdf_data))
    texts: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            texts.append(page_text)
    return "\n".join(texts)


async def ensure_access_token(
    api_key: str,
    secret_key: str,
    cached_token: Optional[str],
    token_expires_at: Optional[datetime],
) -> tuple[str, datetime]:
    now = datetime.utcnow()
    if cached_token and token_expires_at and token_expires_at > now:
        return cached_token, token_expires_at
    result = await get_baidu_access_token(api_key, secret_key)
    new_token = result["access_token"]
    new_expires = now + timedelta(seconds=int(result["expires_in"]) - 600)
    return new_token, new_expires
