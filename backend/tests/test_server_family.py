"""
Server-side integration tests for the family member "本人" auto-creation bug fix.
Runs against the live deployed environment.
"""
import random
import string
import httpx
import pytest

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"

# Generate a unique phone number per test run to avoid conflicts
_PHONE_SUFFIX = "".join(random.choices(string.digits, k=8))
TEST_PHONE = f"139{_PHONE_SUFFIX}"
TEST_PASSWORD = "TestPass1234"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=API_URL, verify=False, timeout=30) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client: httpx.Client):
    """Register a new test user and return the access token."""
    resp = client.post("/auth/register", json={
        "phone": TEST_PHONE,
        "password": TEST_PASSWORD,
        "nickname": f"测试用户{_PHONE_SUFFIX}",
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


class TestHealthCheck:
    def test_health_check(self, client: httpx.Client):
        """GET /api/health returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200


class TestNewUserFamilyMembers:
    def test_sms_login_new_user_and_family_members(self, client: httpx.Client, auth_headers: dict):
        """
        After registration, GET /api/family/members should auto-create a '本人' member
        with is_self=True at position 0.
        """
        resp = client.get("/family/members", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        assert len(items) >= 1, "Family members list should have at least 1 item (本人)"

        self_members = [m for m in items if m.get("is_self") is True]
        assert len(self_members) == 1, f"Expected exactly 1 is_self=True member, got {len(self_members)}"

        self_member = self_members[0]
        assert self_member["nickname"] == "本人"
        assert self_member["relationship_type"] == "本人"

        assert items[0]["is_self"] is True, "本人 should be the first item in the list"


class TestSelfMemberDeletion:
    def test_self_member_cannot_be_deleted(self, client: httpx.Client, auth_headers: dict):
        """DELETE /api/family/members/{self_id} should return 400."""
        list_resp = client.get("/family/members", headers=auth_headers)
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]

        self_member = None
        for m in items:
            if m.get("is_self") is True:
                self_member = m
                break
        assert self_member is not None, "No is_self=True member found"

        del_resp = client.delete(f"/family/members/{self_member['id']}", headers=auth_headers)
        assert del_resp.status_code == 400, f"Expected 400, got {del_resp.status_code}: {del_resp.text}"
        assert "不可删除" in del_resp.json().get("detail", "")


class TestNoDuplicateSelf:
    def test_no_duplicate_self_member(self, client: httpx.Client, auth_headers: dict):
        """Multiple calls to GET /api/family/members should not create duplicate self members."""
        for _ in range(3):
            resp = client.get("/family/members", headers=auth_headers)
            assert resp.status_code == 200

        data = resp.json()
        self_members = [m for m in data["items"] if m.get("is_self") is True]
        assert len(self_members) == 1, f"Expected 1 self member after 3 calls, got {len(self_members)}"


class TestRelationTypes:
    def test_relation_types_available(self, client: httpx.Client):
        """GET /api/relation-types should include '本人'."""
        resp = client.get("/relation-types")
        assert resp.status_code == 200
        items = resp.json()["items"]
        names = [item["name"] for item in items]
        assert "本人" in names, f"'本人' not found in relation types: {names}"
