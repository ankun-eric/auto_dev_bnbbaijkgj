"""
Server-side integration tests for the symptom page bugfix:
"为谁咨询" popup should auto-load the default-selected member's health profile fields.

Since this is a frontend logic fix, these tests verify the backend API contract:
- GET /api/family/members returns complete profile fields for each member
- Member data structure is correct for frontend parsing
- Profile fields can be updated via PUT and reflected in subsequent GET calls
"""
import random
import string

import httpx
import pytest

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"

_PHONE_SUFFIX = "".join(random.choices(string.digits, k=8))
TEST_PHONE = f"139{_PHONE_SUFFIX}"
TEST_PASSWORD = "TestPass1234"

PROFILE_FIELDS = ["birthday", "gender", "height", "weight", "medical_histories", "allergies"]


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=API_URL, verify=False, timeout=30) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client: httpx.Client):
    resp = client.post("/auth/register", json={
        "phone": TEST_PHONE,
        "password": TEST_PASSWORD,
        "nickname": f"症状测试{_PHONE_SUFFIX}",
    })
    if resp.status_code == 400 and "已注册" in resp.text:
        resp = client.post("/auth/login", json={
            "phone": TEST_PHONE,
            "password": TEST_PASSWORD,
        })
    assert resp.status_code == 200, f"Auth failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token: str):
    return {"Authorization": f"Bearer {auth_token}"}


# ── 1. Basic API health checks ──────────────────────────────────────────


class TestBasicAPIs:
    def test_health_check(self, client: httpx.Client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_family_members_requires_auth(self, client: httpx.Client):
        resp = client.get("/family/members")
        assert resp.status_code == 401

    def test_relation_types_accessible(self, client: httpx.Client):
        resp = client.get("/relation-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) > 0
        names = [item["name"] for item in data["items"]]
        assert "本人" in names


# ── 2. Family members API returns profile fields ─────────────────────────


class TestFamilyMemberProfileFields:
    """Core tests: verify GET /api/family/members returns all profile fields
    needed by the frontend symptom page to populate the health form."""

    def test_get_members_returns_items(self, client: httpx.Client, auth_headers: dict):
        resp = client.get("/family/members", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_self_member_exists_with_profile_fields(self, client: httpx.Client, auth_headers: dict):
        """The auto-created '本人' member must include all 6 profile fields in its response,
        even if they are null. The frontend relies on these fields to populate the form."""
        resp = client.get("/family/members", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]

        self_member = next((m for m in items if m.get("is_self") is True), None)
        assert self_member is not None, "No is_self=True member found"
        assert self_member["nickname"] == "本人"

        for field in PROFILE_FIELDS:
            assert field in self_member, (
                f"Field '{field}' missing from self member response. "
                f"Frontend needs this field to auto-fill health profile."
            )

    def test_self_member_is_first_in_list(self, client: httpx.Client, auth_headers: dict):
        resp = client.get("/family/members", headers=auth_headers)
        items = resp.json()["items"]
        assert items[0].get("is_self") is True, "本人 should be first in members list"

    def test_member_response_structure(self, client: httpx.Client, auth_headers: dict):
        """Verify the complete response structure matches what the frontend expects."""
        resp = client.get("/family/members", headers=auth_headers)
        items = resp.json()["items"]
        assert len(items) >= 1

        expected_keys = {
            "id", "user_id", "nickname", "relationship_type", "is_self",
            "birthday", "gender", "height", "weight",
            "medical_histories", "allergies",
            "status", "created_at",
        }
        member = items[0]
        for key in expected_keys:
            assert key in member, f"Expected key '{key}' not found in member response"


# ── 3. Profile update and retrieval round-trip ───────────────────────────


class TestProfileUpdateRoundTrip:
    """After updating a member's profile, GET /api/family/members should reflect
    the new values. This ensures the frontend can correctly load profile data."""

    def test_update_self_member_profile(self, client: httpx.Client, auth_headers: dict):
        """Update the '本人' member with health profile data and verify it persists."""
        list_resp = client.get("/family/members", headers=auth_headers)
        items = list_resp.json()["items"]
        self_member = next(m for m in items if m.get("is_self") is True)
        member_id = self_member["id"]

        update_data = {
            "birthday": "1990-06-15",
            "gender": "male",
            "height": 175.0,
            "weight": 70.5,
            "medical_histories": ["高血压", "糖尿病"],
            "allergies": ["青霉素", "花粉"],
        }
        put_resp = client.put(f"/family/members/{member_id}", json=update_data, headers=auth_headers)
        assert put_resp.status_code == 200, f"PUT failed: {put_resp.status_code} {put_resp.text}"
        put_data = put_resp.json()
        assert put_data["birthday"] == "1990-06-15"
        assert put_data["gender"] == "male"
        assert put_data["height"] == 175.0
        assert put_data["weight"] == 70.5
        assert put_data["medical_histories"] == ["高血压", "糖尿病"]
        assert put_data["allergies"] == ["青霉素", "花粉"]

    def test_updated_profile_reflected_in_list(self, client: httpx.Client, auth_headers: dict):
        """After updating, GET /api/family/members should return the updated profile data.
        This is the exact data source the frontend uses to populate the symptom form."""
        resp = client.get("/family/members", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        self_member = next(m for m in items if m.get("is_self") is True)

        assert self_member["birthday"] == "1990-06-15"
        assert self_member["gender"] == "male"
        assert self_member["height"] == 175.0
        assert self_member["weight"] == 70.5
        assert self_member["medical_histories"] == ["高血压", "糖尿病"]
        assert self_member["allergies"] == ["青霉素", "花粉"]


# ── 4. Add family member with profile and verify fields ──────────────────


class TestAddMemberWithProfile:
    """Adding a family member with profile fields should persist them,
    and they should appear in the members list for the frontend to use."""

    def test_add_member_with_full_profile(self, client: httpx.Client, auth_headers: dict):
        create_resp = client.post("/family/members", json={
            "relationship_type": "child",
            "nickname": "测试孩子",
            "name": "测试孩子",
            "gender": "female",
            "birthday": "2018-03-20",
            "height": 120.0,
            "weight": 25.0,
            "medical_histories": ["哮喘"],
            "allergies": ["牛奶"],
        }, headers=auth_headers)
        assert create_resp.status_code == 200, f"POST failed: {create_resp.status_code} {create_resp.text}"
        child = create_resp.json()
        assert child["gender"] == "female"
        assert child["birthday"] == "2018-03-20"
        assert child["height"] == 120.0
        assert child["weight"] == 25.0

    def test_new_member_profile_in_list(self, client: httpx.Client, auth_headers: dict):
        """The newly added member's profile fields must appear in the list response."""
        resp = client.get("/family/members", headers=auth_headers)
        items = resp.json()["items"]
        child = next((m for m in items if m.get("nickname") == "测试孩子"), None)
        assert child is not None, "Newly added '测试孩子' member not found in list"

        for field in PROFILE_FIELDS:
            assert field in child, f"Field '{field}' missing from new member"

        assert child["gender"] == "female"
        assert child["birthday"] == "2018-03-20"

    def test_all_members_have_profile_fields(self, client: httpx.Client, auth_headers: dict):
        """Every member in the list must include all profile fields.
        The frontend iterates all members and expects these fields to exist."""
        resp = client.get("/family/members", headers=auth_headers)
        items = resp.json()["items"]
        for member in items:
            for field in PROFILE_FIELDS:
                assert field in member, (
                    f"Member '{member.get('nickname')}' missing field '{field}'"
                )


# ── 5. Chat session creation (smoke test) ────────────────────────────────


class TestChatSessionSmoke:
    def test_create_chat_session(self, client: httpx.Client, auth_headers: dict):
        resp = client.post("/chat/sessions", json={
            "title": "症状自查测试",
            "session_type": "health_qa",
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Create session failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "id" in data
