"""Unified file reading helper — supports both local paths and remote URLs (e.g. COS)."""

import os
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def read_file_content(file_url: str) -> Optional[bytes]:
    """Read file content from a local path or remote URL.

    - URLs starting with http:// or https:// are fetched via HTTP GET.
    - Paths starting with /uploads/ are resolved relative to UPLOAD_DIR.
    - Returns None if the file cannot be read.
    """
    if not file_url:
        return None

    if file_url.startswith(("http://", "https://")):
        return await _read_remote(file_url)

    return _read_local(file_url)


async def _read_remote(url: str) -> Optional[bytes]:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.content
            logger.warning("Remote file download failed: %s -> HTTP %s", url, resp.status_code)
    except Exception as e:
        logger.warning("Remote file download error: %s -> %s", url, e)
    return None


def _read_local(file_url: str) -> Optional[bytes]:
    filename = os.path.basename(file_url)
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.warning("Local file read error: %s -> %s", file_path, e)
    return None
