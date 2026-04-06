from __future__ import annotations

import base64
import io
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_OCR_GENERAL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
BAIDU_OCR_ACCURATE = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"


async def get_baidu_access_token(api_key: str, secret_key: str) -> dict:
    """Fetch a Baidu Cloud access_token. Returns {"access_token": ..., "expires_in": ...}."""
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


async def ocr_recognize(image_data: bytes, ocr_type: str, access_token: str) -> str:
    """Call Baidu OCR and return concatenated text."""
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
    lines = [item["words"] for item in words_result]
    return "\n".join(lines)


def check_image_quality(image_data: bytes) -> dict:
    """Basic image quality check: size and simple heuristics.

    Returns {"ok": bool, "message": str}.
    """
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
    """Extract text from a PDF file using PyPDF2 / pypdf."""
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
    """Return a valid access_token, refreshing if expired."""
    now = datetime.utcnow()
    if cached_token and token_expires_at and token_expires_at > now:
        return cached_token, token_expires_at

    result = await get_baidu_access_token(api_key, secret_key)
    new_token = result["access_token"]
    new_expires = now + timedelta(seconds=int(result["expires_in"]) - 600)
    return new_token, new_expires
