"""
Bini Health - Server Bug-Fix Verification Tests (v2)

Covers Bug 4/5/7/8/9 (API-testable) plus general health checks.
Bugs 1/2/3/6 are front-end-only and not tested here.
"""

import random
import string
import time

import pytest
import requests

BASE_URL = (
    "https://newbb.bangbangvip.com"
    "/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
)
API_URL = f"{BASE_URL}/api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_phone() -> str:
    return "139" + "".join(random.choices(string.digits, k=8))


def _register_user(phone: str = None, password: str = "TestPass123") -> dict:
    phone = phone or _random_phone()
    resp = requests.post(
        f"{API_URL}/auth/register",
        json={"phone": phone, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "phone": phone,
        "password": password,
        "token": data["access_token"],
        "user": data["user"],
    }


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def auth_user():
    """Register a fresh test user and return credentials + token."""
    return _register_user()


@pytest.fixture(scope="module")
def auth_headers(auth_user):
    return _auth_headers(auth_user["token"])


# ---------------------------------------------------------------------------
# 1. General health checks
# ---------------------------------------------------------------------------

class TestHealthChecks:
    def test_api_health_returns_200(self):
        resp = requests.get(f"{API_URL}/health", timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "ok"

    def test_frontend_returns_200(self):
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 2. Bug 4 + 9: GET /api/relation-types
# ---------------------------------------------------------------------------

class TestRelationTypes:
    """Bug 4: '本人' should NOT appear in add-member picker (front-end filters).
    Bug 9: /api/relation-types must return a valid non-empty list."""

    def test_relation_types_returns_non_empty_list(self):
        resp = requests.get(f"{API_URL}/relation-types", timeout=10)
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        assert len(items) > 0, "relation-types returned empty list"

    def test_relation_types_contains_common_relations(self):
        resp = requests.get(f"{API_URL}/relation-types", timeout=10)
        assert resp.status_code == 200
        names = [item["name"] for item in resp.json()["items"]]
        for expected in ["爸爸", "妈妈"]:
            assert expected in names, f"Missing expected relation type: {expected}"

    def test_relation_types_contains_self(self):
        """Backend should return '本人'; front-end is responsible for filtering."""
        resp = requests.get(f"{API_URL}/relation-types", timeout=10)
        assert resp.status_code == 200
        names = [item["name"] for item in resp.json()["items"]]
        assert "本人" in names, "Backend should include '本人' in relation-types"

    def test_relation_types_have_id_and_name(self):
        resp = requests.get(f"{API_URL}/relation-types", timeout=10)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert "id" in item, "Each relation type must have an id"
            assert "name" in item, "Each relation type must have a name"


# ---------------------------------------------------------------------------
# 3. Bug 5 + 7: POST /api/family/members
# ---------------------------------------------------------------------------

class TestAddFamilyMember:
    """Bug 5: Adding a member used to fail.
    Bug 7: name/gender/birthday should no longer be required."""

    def test_add_member_with_nickname_only(self, auth_headers):
        """Bug 5+7: only nickname + relationship_type, no name/gender/birthday."""
        resp = requests.get(f"{API_URL}/relation-types", timeout=10)
        rt_items = resp.json()["items"]
        daddy_rt = next((r for r in rt_items if r["name"] == "爸爸"), None)
        assert daddy_rt is not None, "Cannot find '爸爸' relation type"

        payload = {
            "nickname": f"测试爸爸_{int(time.time())}",
            "relationship_type": "爸爸",
            "relation_type_id": daddy_rt["id"],
        }
        resp = requests.post(
            f"{API_URL}/family/members",
            json=payload,
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200, (
            f"Adding member with nickname-only failed: {resp.status_code} {resp.text}"
        )
        body = resp.json()
        assert body.get("id"), "Response should contain member id"
        assert body.get("nickname") == payload["nickname"]

    def test_add_member_without_gender_birthday(self, auth_headers):
        """Bug 7: gender and birthday are no longer mandatory."""
        resp = requests.get(f"{API_URL}/relation-types", timeout=10)
        rt_items = resp.json()["items"]
        mama_rt = next((r for r in rt_items if r["name"] == "妈妈"), None)
        assert mama_rt is not None

        payload = {
            "nickname": f"测试妈妈_{int(time.time())}",
            "relationship_type": "妈妈",
            "relation_type_id": mama_rt["id"],
        }
        resp = requests.post(
            f"{API_URL}/family/members",
            json=payload,
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200, (
            f"Adding member without gender/birthday failed: {resp.status_code} {resp.text}"
        )

    def test_add_member_with_full_info(self, auth_headers):
        """Adding a member with all optional fields should also work."""
        resp = requests.get(f"{API_URL}/relation-types", timeout=10)
        rt_items = resp.json()["items"]
        son_rt = next((r for r in rt_items if r["name"] == "儿子"), None)
        assert son_rt is not None

        payload = {
            "nickname": f"测试儿子_{int(time.time())}",
            "relationship_type": "儿子",
            "relation_type_id": son_rt["id"],
            "gender": "male",
            "birthday": "2020-01-15",
            "height": 120.0,
            "weight": 25.0,
        }
        resp = requests.post(
            f"{API_URL}/family/members",
            json=payload,
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200, (
            f"Adding member with full info failed: {resp.status_code} {resp.text}"
        )

    def test_add_member_without_relationship_fails(self, auth_headers):
        """relationship_type is required — omitting it should return 400."""
        payload = {"nickname": f"无关系_{int(time.time())}"}
        resp = requests.post(
            f"{API_URL}/family/members",
            json=payload,
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code in (400, 422), (
            f"Expected 400/422 when relationship_type is missing, got {resp.status_code}"
        )

    def test_add_member_requires_auth(self):
        """POST /api/family/members without token should be rejected."""
        payload = {
            "nickname": "ghost",
            "relationship_type": "爸爸",
        }
        resp = requests.post(
            f"{API_URL}/family/members",
            json=payload,
            timeout=10,
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without auth, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 4. Bug 8: GET /api/family/members  — self member auto-created
# ---------------------------------------------------------------------------

class TestFamilyMembersList:
    """Bug 8: Every user should have a '本人' (is_self=true) record."""

    def test_list_contains_self_member(self, auth_headers):
        resp = requests.get(
            f"{API_URL}/family/members",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        self_members = [m for m in items if m.get("is_self")]
        assert len(self_members) >= 1, (
            "Family member list must contain at least one is_self=true record"
        )

    def test_self_member_has_correct_relation(self, auth_headers):
        resp = requests.get(
            f"{API_URL}/family/members",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        self_members = [m for m in items if m.get("is_self")]
        assert len(self_members) >= 1
        self_m = self_members[0]
        assert self_m.get("relationship_type") == "本人" or self_m.get("relation_type_name") == "本人", (
            "Self member should have relationship_type or relation_type_name = '本人'"
        )

    def test_multiple_queries_return_same_count(self, auth_headers):
        """Querying family members should not create duplicates."""
        resp1 = requests.get(
            f"{API_URL}/family/members",
            headers=auth_headers,
            timeout=10,
        )
        assert resp1.status_code == 200
        count1 = resp1.json().get("total", len(resp1.json().get("items", [])))

        resp2 = requests.get(
            f"{API_URL}/family/members",
            headers=auth_headers,
            timeout=10,
        )
        assert resp2.status_code == 200
        count2 = resp2.json().get("total", len(resp2.json().get("items", [])))

        assert count1 == count2, (
            f"Querying family members should not create new records "
            f"(first call: {count1}, second call: {count2})"
        )

    def test_new_user_auto_gets_self_member(self):
        """A freshly registered user should immediately have a '本人' record."""
        user = _register_user()
        headers = _auth_headers(user["token"])
        resp = requests.get(
            f"{API_URL}/family/members",
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        self_members = [m for m in items if m.get("is_self")]
        assert len(self_members) == 1, (
            f"New user should have exactly 1 self member, found {len(self_members)}"
        )

    def test_list_members_requires_auth(self):
        resp = requests.get(f"{API_URL}/family/members", timeout=10)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without auth, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 5. Cleanup: remove test members created during tests
# ---------------------------------------------------------------------------

class TestCleanup:
    """Delete non-self family members created by tests."""

    def test_cleanup_test_members(self, auth_headers):
        resp = requests.get(
            f"{API_URL}/family/members",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        deleted = 0
        for m in items:
            if not m.get("is_self") and "测试" in (m.get("nickname") or ""):
                del_resp = requests.delete(
                    f"{API_URL}/family/members/{m['id']}",
                    headers=auth_headers,
                    timeout=10,
                )
                if del_resp.status_code == 200:
                    deleted += 1
        # This is a cleanup step, always passes
        assert True, f"Cleaned up {deleted} test members"
