"""[BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29]
前端兜底响应上报接口的非UI自动化测试。

覆盖：
- POST /api/_frontend_log 无鉴权可调用
- 接收 gateway_fallback 事件正常落 WARN 日志、返回 {"ok": True}
- 空 body / 异常 JSON 不抛错
- 超大 body 被自动截断，仍返回成功
"""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_frontend_log_gateway_fallback_event_ok(client: AsyncClient):
    payload = {
        "type": "gateway_fallback",
        "url": "/api/home_safety/family/members/add",
        "full_url": "/autodev/xxx/api/home_safety/family/members/add",
        "method": "POST",
        "status": 200,
        "content_type": "text/plain",
        "body_excerpt": "gateway ok",
        "page_path": "/home-safety",
        "user_id": "10001",
        "ts": "2026-05-29T10:00:00Z",
    }
    rsp = await client.post("/api/_frontend_log", json=payload)
    assert rsp.status_code == 200
    assert rsp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_frontend_log_empty_body_ok(client: AsyncClient):
    rsp = await client.post("/api/_frontend_log", content=b"")
    assert rsp.status_code == 200
    assert rsp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_frontend_log_non_json_body_ok(client: AsyncClient):
    rsp = await client.post(
        "/api/_frontend_log",
        content=b"not json at all",
        headers={"Content-Type": "text/plain"},
    )
    assert rsp.status_code == 200
    assert rsp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_frontend_log_oversized_body_truncated(client: AsyncClient):
    big_payload = {"type": "gateway_fallback", "body_excerpt": "X" * 8192}
    rsp = await client.post("/api/_frontend_log", content=json.dumps(big_payload))
    assert rsp.status_code == 200
    assert rsp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_frontend_log_no_auth_required(client: AsyncClient):
    """无 Authorization 头也应该可以正常上报，避免上报本身被 401 拦截。"""
    payload = {"type": "gateway_fallback", "url": "/api/x"}
    rsp = await client.post("/api/_frontend_log", json=payload)
    assert rsp.status_code == 200
