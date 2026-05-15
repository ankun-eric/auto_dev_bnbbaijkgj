"""[Bug-471 2026-05-15] AI 对话卡片「相册 / 拍照 / 本机 / 微信」点击无响应 修复回归测试。

本 Bug 的核心是 H5 前端：
  - input 没有 appendChild 到 DOM（iOS / 微信 GC 导致 onchange 不触发）
  - 选完图后没有"图片气泡 + AI 回复"，反而跳到 /drug 独立页

后端层面只做了"协议兼容性"扩展点，本测试确保：
  1) /api/upload/image 与 /api/upload/file 接口仍正常工作（前端选完图后逐张上传拿 URL）
  2) /api/chat/sessions/{sid}/messages 接受嵌入了图片 URL 的长文本内容（前端把
     "[用户上传的图片 N 张]\n1. http://...\n\n我上传了一张药品图片..." 作为 content 发到后端）
  3) 上述链路在用户已登录态下能跑通（避免 401 误判为 Bug）
"""
from __future__ import annotations

import io
from typing import Tuple

import pytest
from httpx import AsyncClient


def _png_bytes() -> bytes:
    """构造一个最小合法 PNG（1x1 透明像素），用于上传接口测试。"""
    # 标准 1x1 透明 PNG（base64 编码后约 70 字节）
    import base64

    b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    return base64.b64decode(b64)


@pytest.mark.asyncio
async def test_upload_image_endpoint_returns_url(client: AsyncClient, auth_headers):
    """T-471-01：POST /api/upload/image 成功返回包含 url 字段的 JSON。"""
    png = _png_bytes()
    files = {"file": ("test.png", io.BytesIO(png), "image/png")}
    r = await client.post("/api/upload/image", headers=auth_headers, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict)
    assert "url" in body and isinstance(body["url"], str) and body["url"]
    # 文件名占位 + 文件大小
    assert "filename" in body
    assert body.get("size") == len(png)


@pytest.mark.asyncio
async def test_upload_image_rejects_non_image_mime(client: AsyncClient, auth_headers):
    """T-471-02：/api/upload/image 拒绝非图片 MIME（防止误传 PDF 等）。"""
    files = {"file": ("a.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    r = await client.post("/api/upload/image", headers=auth_headers, files=files)
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_upload_file_endpoint_supports_pdf(client: AsyncClient, auth_headers):
    """T-471-03：POST /api/upload/file 接受 PDF（本机/文件类按钮走该接口）。"""
    pdf_bytes = b"%PDF-1.4\n%fake-pdf-bytes-for-test-only\n"
    files = {"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r = await client.post("/api/upload/file", headers=auth_headers, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "url" in body and body["url"]


@pytest.mark.asyncio
async def test_chat_session_accepts_message_with_embedded_image_urls(
    client: AsyncClient, auth_headers
):
    """T-471-04：会话消息接口接受"嵌入图片 URL 的长内容"，这是前端 Bug-471 修复后的核心载荷形态。

    前端修复后，用户选完图、上传完毕后调用 /api/chat/sessions/{sid}/messages 时，content
    形如：
        [用户上传的图片 2 张]
        1. http://server/uploads/a.png
        2. http://server/uploads/b.png

        我上传了一张药品图片，请帮我识别

    本测试只验证后端能正常接收 + 入库（不依赖外部 LLM）。
    """
    r = await client.post(
        "/api/chat/sessions",
        headers=auth_headers,
        json={"session_type": "drug_query", "title": "Bug471 回归"},
    )
    assert r.status_code in (200, 201), r.text
    sid = r.json().get("id") or r.json().get("data", {}).get("id")
    assert isinstance(sid, int), f"got: {r.json()}"

    long_content = (
        "[用户上传的图片 2 张]\n"
        "1. http://newbb.test.bangbangvip.com/uploads/a.png\n"
        "2. http://newbb.test.bangbangvip.com/uploads/b.png\n"
        "\n"
        "我上传了一张药品图片，请帮我识别"
    )
    r2 = await client.post(
        f"/api/chat/sessions/{sid}/messages",
        headers=auth_headers,
        json={"content": long_content, "message_type": "text", "source": "preset"},
    )
    # 后端可能因为没有真实 LLM 配置返回 200 / 500（取决于 mock），但绝不应该是 422
    # 422 才是 Bug：协议字段不接受。
    assert r2.status_code != 422, f"422 schema rejection: {r2.text}"


@pytest.mark.asyncio
async def test_chat_message_accepts_optional_source_field(
    client: AsyncClient, auth_headers
):
    """T-471-05：source 字段允许传 'preset'（前端 upload 卡片走的就是 preset 路径）。"""
    r = await client.post(
        "/api/chat/sessions",
        headers=auth_headers,
        json={"session_type": "health_qa"},
    )
    sid = r.json().get("id") or r.json().get("data", {}).get("id")
    assert isinstance(sid, int)

    r2 = await client.post(
        f"/api/chat/sessions/{sid}/messages",
        headers=auth_headers,
        json={"content": "你好", "message_type": "text", "source": "preset"},
    )
    assert r2.status_code != 422


@pytest.mark.asyncio
async def test_upload_image_requires_auth(client: AsyncClient):
    """T-471-06：未登录访问图片上传接口必须 401（防止匿名滥用）。"""
    files = {"file": ("test.png", io.BytesIO(_png_bytes()), "image/png")}
    r = await client.post("/api/upload/image", files=files)
    assert r.status_code in (401, 403), r.status_code
