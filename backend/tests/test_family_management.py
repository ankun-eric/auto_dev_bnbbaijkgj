"""
Non-UI integration tests for 家庭健康档案共管 (Family Health Record Co-management).
Runs against the live deployed server using synchronous httpx client.

Run with: pytest tests/test_family_management.py -v
"""

import random
import string

import httpx
import pytest

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"

_state: dict = {}


def _random_phone() -> str:
    return "138" + "".join(random.choices(string.digits, k=8))


def register_and_login(client: httpx.Client, phone: str | None = None) -> str:
    if not phone:
        phone = _random_phone()
    nickname = f"test_{phone[-4:]}"

    resp = client.post(f"{BASE_URL}/auth/register", json={
        "phone": phone,
        "password": "Test123456",
        "nickname": nickname,
    })

    resp = client.post(f"{BASE_URL}/auth/login", json={
        "phone": phone,
        "password": "Test123456",
    })
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


def create_family_member(client: httpx.Client, token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(f"{BASE_URL}/family/members", headers=headers, json={
        "nickname": f"测试家人_{random.randint(1000, 9999)}",
        "relationship_type": "父亲",
        "gender": "male",
    })
    assert resp.status_code == 200, f"Create member failed: {resp.status_code} {resp.text}"
    return resp.json()["id"]


@pytest.fixture(scope="module")
def client():
    with httpx.Client(verify=False, timeout=60) as c:
        yield c


@pytest.fixture(scope="module")
def setup_users(client: httpx.Client):
    phone_a = _random_phone()
    phone_b = _random_phone()

    token_a = register_and_login(client, phone_a)
    token_b = register_and_login(client, phone_b)
    member_id = create_family_member(client, token_a)

    _state["token_a"] = token_a
    _state["token_b"] = token_b
    _state["member_id"] = member_id
    _state["headers_a"] = {"Authorization": f"Bearer {token_a}"}
    _state["headers_b"] = {"Authorization": f"Bearer {token_b}"}
    return _state


class TestInvitationCRUD:

    def test_tc001_create_invitation_success(self, client: httpx.Client, setup_users):
        resp = client.post(
            f"{BASE_URL}/family/invitation",
            headers=_state["headers_a"],
            json={"member_id": _state["member_id"]},
        )
        assert resp.status_code == 200, f"Unexpected {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "invite_code" in body
        assert "expires_at" in body
        _state["invite_code"] = body["invite_code"]

    def test_tc002_create_invitation_member_not_found(self, client: httpx.Client, setup_users):
        resp = client.post(
            f"{BASE_URL}/family/invitation",
            headers=_state["headers_a"],
            json={"member_id": 99999},
        )
        assert resp.status_code == 404

    def test_tc003_get_invitation_detail(self, client: httpx.Client, setup_users):
        code = _state.get("invite_code")
        assert code, "invite_code not set — TC-001 must run first"
        resp = client.get(f"{BASE_URL}/family/invitation/{code}", headers=_state["headers_a"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["invite_code"] == code
        assert body["status"] == "pending"

    def test_tc004_get_invitation_not_found(self, client: httpx.Client, setup_users):
        resp = client.get(
            f"{BASE_URL}/family/invitation/invalid-code-xyz",
            headers=_state["headers_a"],
        )
        assert resp.status_code == 404


class TestInvitationAcceptReject:

    def test_tc006_reject_invitation(self, client: httpx.Client, setup_users):
        resp = client.post(
            f"{BASE_URL}/family/invitation",
            headers=_state["headers_a"],
            json={"member_id": _state["member_id"]},
        )
        assert resp.status_code == 200
        reject_code = resp.json()["invite_code"]

        resp = client.post(
            f"{BASE_URL}/family/invitation/{reject_code}/reject",
            headers=_state["headers_b"],
        )
        assert resp.status_code == 200

    def test_tc005_accept_invitation(self, client: httpx.Client, setup_users):
        resp = client.post(
            f"{BASE_URL}/family/invitation",
            headers=_state["headers_a"],
            json={"member_id": _state["member_id"]},
        )
        assert resp.status_code == 200
        accept_code = resp.json()["invite_code"]

        resp = client.post(
            f"{BASE_URL}/family/invitation/{accept_code}/accept",
            headers=_state["headers_b"],
        )
        assert resp.status_code == 200, f"Accept failed: {resp.status_code} {resp.text}"
        body = resp.json()
        assert "management_id" in body
        _state["management_id"] = body["management_id"]

    def test_tc007_accept_expired_invitation(self, client: httpx.Client, setup_users):
        pytest.skip("Invitation expiry is 24h; cannot realistically test in automated run")


class TestManagementRelationship:

    def test_tc008_list_managed_members(self, client: httpx.Client, setup_users):
        assert _state.get("management_id"), "management_id not set — TC-005 must run first"
        resp = client.get(
            f"{BASE_URL}/family/management",
            headers=_state["headers_a"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

    def test_tc009_list_managed_by(self, client: httpx.Client, setup_users):
        resp = client.get(
            f"{BASE_URL}/family/managed-by",
            headers=_state["headers_b"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

    def test_tc010_cancel_management(self, client: httpx.Client, setup_users):
        mgmt_id = _state.get("management_id")
        assert mgmt_id, "management_id not set"
        resp = client.delete(
            f"{BASE_URL}/family/management/{mgmt_id}",
            headers=_state["headers_a"],
        )
        assert resp.status_code == 200

    def test_tc011_cancel_management_not_found(self, client: httpx.Client, setup_users):
        resp = client.delete(
            f"{BASE_URL}/family/management/99999",
            headers=_state["headers_a"],
        )
        assert resp.status_code == 404


class TestAuthGuard:

    def test_tc012_unauthenticated_request(self, client: httpx.Client, setup_users):
        resp = client.post(
            f"{BASE_URL}/family/invitation",
            json={"member_id": 1},
        )
        assert resp.status_code == 401
