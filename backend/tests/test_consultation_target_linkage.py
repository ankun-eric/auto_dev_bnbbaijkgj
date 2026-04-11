import pytest
from httpx import AsyncClient

from app.models.models import (
    ChatSession,
    FamilyMember,
    SessionType,
)

from .conftest import test_session


async def _create_user(client: AsyncClient, phone="13900200001", password="user123", nickname="联动测试用户"):
    resp = await client.post("/api/auth/register", json={
        "phone": phone, "password": password, "nickname": nickname,
    })
    assert resp.status_code == 200
    return resp.json()


async def _user_headers(client: AsyncClient, phone="13900200001", password="user123"):
    resp = await client.post("/api/auth/login", json={"phone": phone, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_family_member(db_session, user_id: int, relationship_type="母亲", nickname="张三") -> FamilyMember:
    member = FamilyMember(
        user_id=user_id,
        relationship_type=relationship_type,
        nickname=nickname,
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)
    return member


async def _seed_session(
    db_session,
    user_id: int,
    title="联动测试对话",
    session_type=SessionType.health_qa,
    family_member_id=None,
) -> ChatSession:
    session = ChatSession(
        user_id=user_id,
        session_type=session_type,
        title=title,
        family_member_id=family_member_id,
        message_count=0,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest.mark.asyncio
async def test_tc001_session_detail_returns_family_member_id(client: AsyncClient, db_session):
    """TC-001: Session detail returns family_member_id when set"""
    reg = await _create_user(client, phone="13900200010")
    headers = await _user_headers(client, phone="13900200010")
    user_id = reg["user"]["id"]

    member = await _seed_family_member(db_session, user_id)
    session = await _seed_session(db_session, user_id, family_member_id=member.id)

    resp = await client.get(f"/api/chat-sessions/{session.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["family_member_id"] == member.id


@pytest.mark.asyncio
async def test_tc002_session_detail_null_family_member_fields(client: AsyncClient, db_session):
    """TC-002: Session detail returns null family_member fields when no member set"""
    reg = await _create_user(client, phone="13900200020")
    headers = await _user_headers(client, phone="13900200020")
    user_id = reg["user"]["id"]

    session = await _seed_session(db_session, user_id)

    resp = await client.get(f"/api/chat-sessions/{session.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["family_member_id"] is None
    assert data["family_member_relation"] is None
    assert data["family_member_nickname"] is None


@pytest.mark.asyncio
async def test_tc003_session_detail_correct_family_member_relation(client: AsyncClient, db_session):
    """TC-003: Session detail returns correct family_member_relation and nickname"""
    reg = await _create_user(client, phone="13900200030")
    headers = await _user_headers(client, phone="13900200030")
    user_id = reg["user"]["id"]

    member = await _seed_family_member(db_session, user_id, relationship_type="母亲", nickname="张三")
    session = await _seed_session(db_session, user_id, family_member_id=member.id)

    resp = await client.get(f"/api/chat-sessions/{session.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["family_member_relation"] == "母亲"
    assert data["family_member_nickname"] == "张三"


@pytest.mark.asyncio
async def test_tc004_symptom_check_session_preserves_type(client: AsyncClient, db_session):
    """TC-004: Symptom check session preserves session_type"""
    reg = await _create_user(client, phone="13900200040")
    headers = await _user_headers(client, phone="13900200040")
    user_id = reg["user"]["id"]

    session = await _seed_session(db_session, user_id, session_type=SessionType.symptom_check)

    resp = await client.get(f"/api/chat-sessions/{session.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_type"] == "symptom_check"
