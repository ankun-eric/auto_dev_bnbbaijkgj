"""
Server-level integration tests for the consultation target linkage feature.
Tests run against the live deployed server using HTTP requests.
"""
import random
import string
import time

import pytest
import requests

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
TIMEOUT = 15


def _random_phone():
    return "139" + "".join(random.choices(string.digits, k=8))


def _register_and_login(phone=None, password="test1234"):
    phone = phone or _random_phone()
    nickname = f"test_{phone[-4:]}"

    resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={"phone": phone, "password": password, "nickname": nickname},
        timeout=TIMEOUT,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data["access_token"], data["user"]["id"], phone

    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"phone": phone, "password": password},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    return data["access_token"], data["user"]["id"], phone


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ────────────────── Test Cases ──────────────────


class TestHealthEndpoint:
    def test_api_health(self):
        """TC-0: GET /api/health returns 200"""
        resp = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        assert resp.status_code == 200, f"Health endpoint returned {resp.status_code}: {resp.text}"


class TestSessionDetailNewFields:
    """TC-1: Session detail API returns family_member_id/relation/nickname fields."""

    def test_symptom_check_session_has_family_fields(self):
        token, user_id, phone = _register_and_login()
        headers = _auth_headers(token)

        create_resp = requests.post(
            f"{BASE_URL}/chat/sessions",
            json={"session_type": "symptom_check", "title": "TC1 symptom session"},
            headers=headers,
            timeout=TIMEOUT,
        )
        assert create_resp.status_code == 200, f"Create session failed: {create_resp.status_code} {create_resp.text}"
        session_id = create_resp.json()["id"]

        detail_resp = requests.get(
            f"{BASE_URL}/chat-sessions/{session_id}",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert detail_resp.status_code == 200, f"Get detail failed: {detail_resp.status_code} {detail_resp.text}"
        data = detail_resp.json()

        assert "family_member_id" in data, f"Response missing 'family_member_id'. Keys: {list(data.keys())}"
        assert "family_member_relation" in data, f"Response missing 'family_member_relation'. Keys: {list(data.keys())}"
        assert "family_member_nickname" in data, f"Response missing 'family_member_nickname'. Keys: {list(data.keys())}"
        assert data["family_member_id"] is None
        assert data["family_member_relation"] is None
        assert data["family_member_nickname"] is None
        assert data["session_type"] == "symptom_check"


class TestSessionWithFamilyMember:
    """TC-2: Session with family member returns relation info."""

    def test_family_member_relation_propagated(self):
        token, user_id, phone = _register_and_login()
        headers = _auth_headers(token)

        member_resp = requests.post(
            f"{BASE_URL}/family/members",
            json={"relationship_type": "母亲", "nickname": "张三"},
            headers=headers,
            timeout=TIMEOUT,
        )
        assert member_resp.status_code == 200, f"Create member failed: {member_resp.status_code} {member_resp.text}"
        member_id = member_resp.json()["id"]

        create_resp = requests.post(
            f"{BASE_URL}/chat/sessions",
            json={
                "session_type": "symptom_check",
                "title": "TC2 family session",
                "family_member_id": member_id,
            },
            headers=headers,
            timeout=TIMEOUT,
        )
        assert create_resp.status_code == 200, f"Create session failed: {create_resp.status_code} {create_resp.text}"
        session_id = create_resp.json()["id"]

        detail_resp = requests.get(
            f"{BASE_URL}/chat-sessions/{session_id}",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert detail_resp.status_code == 200, f"Get detail failed: {detail_resp.status_code} {detail_resp.text}"
        data = detail_resp.json()

        assert data["family_member_id"] == member_id, (
            f"Expected family_member_id={member_id}, got {data['family_member_id']}"
        )
        assert data["family_member_relation"] == "母亲", (
            f"Expected relation '母亲', got '{data['family_member_relation']}'"
        )
        assert data["family_member_nickname"] == "张三", (
            f"Expected nickname '张三', got '{data['family_member_nickname']}'"
        )


class TestRegularSession:
    """TC-3: Regular (non-symptom) session works normally."""

    def test_health_qa_session_null_family_fields(self):
        token, user_id, phone = _register_and_login()
        headers = _auth_headers(token)

        create_resp = requests.post(
            f"{BASE_URL}/chat/sessions",
            json={"session_type": "health_qa", "title": "TC3 health_qa session"},
            headers=headers,
            timeout=TIMEOUT,
        )
        assert create_resp.status_code == 200, f"Create session failed: {create_resp.status_code} {create_resp.text}"
        session_id = create_resp.json()["id"]

        detail_resp = requests.get(
            f"{BASE_URL}/chat-sessions/{session_id}",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert detail_resp.status_code == 200, f"Get detail failed: {detail_resp.status_code} {detail_resp.text}"
        data = detail_resp.json()

        assert data["session_type"] == "health_qa"
        assert data["family_member_id"] is None
        assert data["family_member_relation"] is None
        assert data["family_member_nickname"] is None
