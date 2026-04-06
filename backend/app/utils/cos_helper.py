import os
import uuid
import hashlib
import hmac
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def try_cos_upload(
    db: AsyncSession,
    file_content: bytes,
    filename: str,
    content_type: str,
    prefix: str = "images/",
) -> Optional[str]:
    """Try uploading to COS. Returns full URL on success, None on failure (fallback to local)."""
    try:
        from app.models.models import CosConfig
        result = await db.execute(select(CosConfig).limit(1))
        cfg = result.scalar_one_or_none()
        if not cfg or not cfg.is_active or not cfg.secret_id or not cfg.secret_key_encrypted or not cfg.bucket:
            return None

        ext = os.path.splitext(filename)[1] if filename else ""
        file_key = f"{prefix}{uuid.uuid4().hex}{ext}"

        region = cfg.region or "ap-guangzhou"
        bucket = cfg.bucket
        host = f"{bucket}.cos.{region}.myqcloud.com"
        url = f"https://{host}/{file_key}"

        now = int(time.time())
        key_time = f"{now};{now + 3600}"
        sign_key = hmac.new(cfg.secret_key_encrypted.encode(), key_time.encode(), hashlib.sha1).hexdigest()

        http_string = f"put\n/{file_key}\n\nhost={host}\n"
        sha1_http = hashlib.sha1(http_string.encode()).hexdigest()
        string_to_sign = f"sha1\n{key_time}\n{sha1_http}\n"
        signature = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()

        authorization = (
            f"q-sign-algorithm=sha1&q-ak={cfg.secret_id}&q-sign-time={key_time}"
            f"&q-key-time={key_time}&q-header-list=host&q-url-param-list=&q-signature={signature}"
        )

        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                url,
                content=file_content,
                headers={
                    "Host": host,
                    "Authorization": authorization,
                    "Content-Type": content_type or "application/octet-stream",
                },
            )
            if resp.status_code in (200, 204):
                return url
    except Exception:
        pass
    return None
