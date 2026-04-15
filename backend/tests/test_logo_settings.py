"""Tests for LOGO Settings — 品牌LOGO上传、获取、删除.

Covers public GET endpoint and admin POST/DELETE endpoints
for brand logo management.
"""

import io
import struct
import zlib

import pytest
from httpx import AsyncClient


def _make_minimal_png() -> bytes:
    """Generate a valid 1x1 red PNG image in memory."""
    width, height = 1, 1
    raw_row = b"\x00\xff\x00\x00"  # filter byte + RGB
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat_data = zlib.compress(raw_row)

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        out = struct.pack(">I", len(data)) + chunk_type + data
        return out + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr_data)
    png += _chunk(b"IDAT", idat_data)
    png += _chunk(b"IEND", b"")
    return png


# ══════════════════════════════════════════════
#  TC-001: GET 无LOGO时返回 logo_url 为 null
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc001_get_logo_no_logo(client: AsyncClient):
    """GET /api/settings/logo returns logo_url=null when no logo is set."""
    resp = await client.get("/api/settings/logo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["logo_url"] is None


# ══════════════════════════════════════════════
#  TC-002: POST 上传LOGO成功（管理员角色）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc002_upload_logo_admin(client: AsyncClient, admin_headers):
    """POST /api/admin/settings/logo uploads a PNG logo successfully."""
    png_bytes = _make_minimal_png()
    resp = await client.post(
        "/api/admin/settings/logo",
        headers=admin_headers,
        files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "logo_url" in data["data"]
    assert data["data"]["logo_url"].endswith(".png")


# ══════════════════════════════════════════════
#  TC-003: GET 上传后返回有效 logo_url
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc003_get_logo_after_upload(client: AsyncClient, admin_headers):
    """GET /api/settings/logo returns a non-null logo_url after upload."""
    png_bytes = _make_minimal_png()
    await client.post(
        "/api/admin/settings/logo",
        headers=admin_headers,
        files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
    )

    resp = await client.get("/api/settings/logo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["logo_url"] is not None
    assert "/uploads/logo/" in data["data"]["logo_url"]


# ══════════════════════════════════════════════
#  TC-004: DELETE 删除LOGO成功（管理员角色）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc004_delete_logo_admin(client: AsyncClient, admin_headers):
    """DELETE /api/admin/settings/logo deletes the logo successfully."""
    png_bytes = _make_minimal_png()
    await client.post(
        "/api/admin/settings/logo",
        headers=admin_headers,
        files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
    )

    resp = await client.delete("/api/admin/settings/logo", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0


# ══════════════════════════════════════════════
#  TC-005: GET 删除后 logo_url 恢复为 null
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc005_get_logo_after_delete(client: AsyncClient, admin_headers):
    """GET /api/settings/logo returns null after logo deletion."""
    png_bytes = _make_minimal_png()
    await client.post(
        "/api/admin/settings/logo",
        headers=admin_headers,
        files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
    )

    await client.delete("/api/admin/settings/logo", headers=admin_headers)

    resp = await client.get("/api/settings/logo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["logo_url"] is None


# ══════════════════════════════════════════════
#  TC-006: POST 非管理员上传被拒（应返回 401/403）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc006_upload_logo_non_admin(client: AsyncClient, auth_headers):
    """POST /api/admin/settings/logo with regular user token is rejected."""
    png_bytes = _make_minimal_png()
    resp = await client.post(
        "/api/admin/settings/logo",
        headers=auth_headers,
        files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  TC-007: DELETE 非管理员删除被拒（应返回 401/403）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc007_delete_logo_non_admin(client: AsyncClient, auth_headers):
    """DELETE /api/admin/settings/logo with regular user token is rejected."""
    resp = await client.delete("/api/admin/settings/logo", headers=auth_headers)
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  TC-008: POST 上传无效文件格式被拒（如上传 .txt 文件）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc008_upload_invalid_format(client: AsyncClient, admin_headers):
    """POST /api/admin/settings/logo rejects non-image file types."""
    txt_content = b"this is not an image"
    resp = await client.post(
        "/api/admin/settings/logo",
        headers=admin_headers,
        files={"file": ("test.txt", io.BytesIO(txt_content), "text/plain")},
    )
    assert resp.status_code == 400
    assert "格式" in resp.json()["detail"]
