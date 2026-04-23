"""[2026-04-23] 体检报告多图修复——会话详情接口新增字段的自动化测试。

覆盖 `GET /api/chat/sessions/{id}` 的 4 个兼容字段：
    - type / interpret_session_id / compare_report_ids / auto_start_supported
以及 reports_brief[*].file_urls 的返回 & fallback 行为。
"""
from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from app.models.models import (
    ChatSession,
    CheckupReport,
    SessionType,
)


async def _get_user_id(client: AsyncClient, headers: dict) -> int:
    resp = await client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_report(
    db_session,
    user_id: int,
    **overrides,
) -> CheckupReport:
    defaults = dict(
        user_id=user_id,
        report_date=date(2026, 4, 20),
        file_url="/uploads/r.jpg",
        thumbnail_url="/uploads/r.jpg",
        file_type="image",
        status="completed",
        abnormal_count=0,
    )
    defaults.update(overrides)
    report = CheckupReport(**defaults)
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report


async def _create_session(
    db_session,
    user_id: int,
    *,
    session_type: SessionType = SessionType.report_interpret,
    title: str = "多图测试会话",
    report_id: int | None = None,
    compare_report_ids: str | None = None,
) -> ChatSession:
    sess = ChatSession(
        user_id=user_id,
        session_type=session_type,
        title=title,
        message_count=0,
        report_id=report_id,
        compare_report_ids=compare_report_ids,
    )
    db_session.add(sess)
    await db_session.commit()
    await db_session.refresh(sess)
    return sess


# ─────────────────── 用例 1：type 字段 + interpret_session_id ───────────────────


@pytest.mark.asyncio
async def test_session_detail_returns_type_field(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)
    sess = await _create_session(
        db_session,
        user_id,
        session_type=SessionType.report_interpret,
        report_id=report.id,
    )

    resp = await client.get(f"/api/chat/sessions/{sess.id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["session_type"] == "report_interpret"
    assert data["type"] == data["session_type"]
    assert data["interpret_session_id"] == sess.id
    assert data["auto_start_supported"] is True


# ─────────────────── 用例 2：compare_report_ids ───────────────────


@pytest.mark.asyncio
async def test_session_detail_returns_compare_report_ids(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    r1 = await _create_report(db_session, user_id, file_url="/u/1.jpg", thumbnail_url="/u/1.jpg")
    r2 = await _create_report(db_session, user_id, file_url="/u/2.jpg", thumbnail_url="/u/2.jpg")
    sess = await _create_session(
        db_session,
        user_id,
        session_type=SessionType.report_compare,
        compare_report_ids=f"{r1.id},{r2.id}",
    )

    resp = await client.get(f"/api/chat/sessions/{sess.id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["compare_report_ids"] == [r1.id, r2.id]
    assert data["report_ids"] == [r1.id, r2.id]
    assert data["auto_start_supported"] is True
    assert data["type"] == "report_compare"
    assert data["interpret_session_id"] == sess.id


# ─────────────────── 用例 3：普通会话 auto_start_supported = False ───────────────────


@pytest.mark.asyncio
async def test_session_detail_auto_start_false_for_general(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    sess = await _create_session(
        db_session,
        user_id,
        session_type=SessionType.health_qa,
    )

    resp = await client.get(f"/api/chat/sessions/{sess.id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["type"] == "health_qa"
    assert data["auto_start_supported"] is False
    assert data["interpret_session_id"] is None
    assert data["compare_report_ids"] == []


# ─────────────────── 用例 4：file_urls 列表原样返回 ───────────────────


@pytest.mark.asyncio
async def test_reports_brief_contains_file_urls(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(
        db_session,
        user_id,
        file_url="/u/a.jpg",
        thumbnail_url="/u/a.jpg",
        file_urls=["a.jpg", "b.jpg"],
        thumbnail_urls=["a.jpg", "b.jpg"],
    )
    sess = await _create_session(
        db_session,
        user_id,
        session_type=SessionType.report_interpret,
        report_id=report.id,
    )

    resp = await client.get(f"/api/chat/sessions/{sess.id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert len(data["reports_brief"]) == 1
    brief = data["reports_brief"][0]
    assert brief["id"] == report.id
    assert isinstance(brief["file_urls"], list)
    assert len(brief["file_urls"]) == 2
    assert brief["file_urls"] == ["a.jpg", "b.jpg"]


# ─────────────────── 用例 5：file_urls fallback 到 [file_url] ───────────────────


@pytest.mark.asyncio
async def test_reports_brief_fallback_to_file_url(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(
        db_session,
        user_id,
        file_url="single.jpg",
        thumbnail_url=None,
        file_urls=None,
        thumbnail_urls=None,
    )
    sess = await _create_session(
        db_session,
        user_id,
        session_type=SessionType.report_interpret,
        report_id=report.id,
    )

    resp = await client.get(f"/api/chat/sessions/{sess.id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert len(data["reports_brief"]) == 1
    brief = data["reports_brief"][0]
    assert brief["file_urls"] == ["single.jpg"]
