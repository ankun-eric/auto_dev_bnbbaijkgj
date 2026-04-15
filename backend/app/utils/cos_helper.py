import hashlib
import hmac
import os
import time
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_cos_config_cached(db: AsyncSession):
    """Fetch the active COS config row (latest by id)."""
    from app.models.models import CosConfig

    result = await db.execute(select(CosConfig).order_by(CosConfig.id.desc()).limit(1))
    return result.scalar_one_or_none()


def _build_cos_authorization(secret_id: str, secret_key: str, host: str, file_key: str, method: str = "put") -> str:
    now = int(time.time())
    key_time = f"{now};{now + 3600}"
    sign_key = hmac.new(secret_key.encode(), key_time.encode(), hashlib.sha1).hexdigest()

    http_string = f"{method}\n/{file_key}\n\nhost={host}\n"
    sha1_http = hashlib.sha1(http_string.encode()).hexdigest()
    string_to_sign = f"sha1\n{key_time}\n{sha1_http}\n"
    signature = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()

    return (
        f"q-sign-algorithm=sha1&q-ak={secret_id}&q-sign-time={key_time}"
        f"&q-key-time={key_time}&q-header-list=host&q-url-param-list=&q-signature={signature}"
    )


def _build_file_url(cfg, file_key: str) -> str:
    """Build the public URL for a COS file, using CDN domain if configured."""
    if cfg.cdn_domain:
        protocol = cfg.cdn_protocol or "https"
        return f"{protocol}://{cfg.cdn_domain}/{file_key}"
    region = cfg.region or "ap-guangzhou"
    return f"https://{cfg.bucket}.cos.{region}.myqcloud.com/{file_key}"


async def try_cos_upload(
    db: AsyncSession,
    file_content: bytes,
    filename: str,
    content_type: str,
    prefix: str = "",
) -> Optional[str]:
    """Try uploading to COS. Returns full URL on success, None on failure (fallback to local).

    Determines storage prefix by MIME type: image/ -> image_prefix, video/ -> video_prefix, else -> file_prefix.
    The `prefix` param is used as fallback only when no matching category prefix is configured.
    """
    try:
        cfg = await get_cos_config_cached(db)
        if not cfg or not cfg.is_active or not cfg.secret_id or not cfg.secret_key_encrypted or not cfg.bucket:
            return None

        ext = os.path.splitext(filename)[1] if filename else ""
        if content_type and content_type.startswith("image/"):
            effective_prefix = cfg.image_prefix or "images/"
        elif content_type and content_type.startswith("video/"):
            effective_prefix = cfg.video_prefix or "videos/"
        else:
            effective_prefix = cfg.file_prefix or "files/"
        file_key = f"{effective_prefix}{uuid.uuid4().hex}{ext}"

        region = cfg.region or "ap-guangzhou"
        host = f"{cfg.bucket}.cos.{region}.myqcloud.com"
        upload_url = f"https://{host}/{file_key}"

        authorization = _build_cos_authorization(
            cfg.secret_id, cfg.secret_key_encrypted, host, file_key, "put"
        )

        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                upload_url,
                content=file_content,
                headers={
                    "Host": host,
                    "Authorization": authorization,
                    "Content-Type": content_type or "application/octet-stream",
                },
            )
            if resp.status_code in (200, 204):
                return _build_file_url(cfg, file_key)
    except Exception:
        pass
    return None


async def delete_cos_file(db: AsyncSession, file_key: str) -> bool:
    """Delete a file from COS by its key. Returns True on success."""
    try:
        cfg = await get_cos_config_cached(db)
        if not cfg or not cfg.is_active or not cfg.secret_id or not cfg.secret_key_encrypted or not cfg.bucket:
            return False

        region = cfg.region or "ap-guangzhou"
        host = f"{cfg.bucket}.cos.{region}.myqcloud.com"
        delete_url = f"https://{host}/{file_key}"

        authorization = _build_cos_authorization(
            cfg.secret_id, cfg.secret_key_encrypted, host, file_key, "delete"
        )

        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                delete_url,
                headers={
                    "Host": host,
                    "Authorization": authorization,
                },
            )
            return resp.status_code in (200, 204, 404)
    except Exception:
        return False
