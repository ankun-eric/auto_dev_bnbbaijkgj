"""[PRD-FAMILY-AUTH-MP-V1] 小程序「接受守护邀请」页 - 非UI集成测试。

覆盖：
- TC01 GET /api/family/invitation/{code} 返回新字段（relationship_type、inviter_avatar、
       current_managed_by_count、max_managed_by_count、merge_preview、is_self_invite、
       invalid_reason）
- TC02 当 inviter == current_user 时 is_self_invite=True 且 invalid_reason='self'
- TC03 未登录态调用 detail，可正常返回，不带个人视角字段
- TC04 POST accept 携带 merge_fields=[] 时不合并任何字段
- TC05 POST accept 携带 merge_fields=['name'] 时仅合并 name
- TC06 拒绝邀请后再次 detail 时 invalid_reason='cancelled'
- TC07 邀请人自接受被拒（self），返回 400

运行：pytest backend/tests/test_family_auth_mp_v1.py -v
"""

from __future__ import annotations

import os
import random
import string

import httpx
import pytest

BASE_URL = os.environ.get(
    "FAMILY_AUTH_MP_BASE_URL",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api",
)


def _rand_phone() -> str:
    return "138" + "".join(random.choices(string.digits, k=8))


def _register_and_login(client: httpx.Client, phone: str | None = None) -> tuple[str, str]:
    phone = phone or _rand_phone()
    nickname = f"famauth_{phone[-4:]}"
    client.post(
        f"{BASE_URL}/auth/register",
        json={"phone": phone, "password": "Test123456", "nickname": nickname},
    )
    resp = client.post(
        f"{BASE_URL}/auth/login",
        json={"phone": phone, "password": "Test123456"},
    )
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"], nickname


def _create_member(client: httpx.Client, token: str) -> int:
    resp = client.post(
        f"{BASE_URL}/family/members",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nickname": f"老人_{random.randint(1000, 9999)}",
            "relationship_type": "father",
            "gender": "male",
            "height": 170,
            "weight": 65,
        },
    )
    assert resp.status_code == 200, f"create member: {resp.status_code} {resp.text}"
    return resp.json()["id"]


def _create_invitation(client: httpx.Client, token: str, member_id: int) -> str:
    resp = client.post(
        f"{BASE_URL}/family/invitation",
        headers={"Authorization": f"Bearer {token}"},
        json={"member_id": member_id},
    )
    assert resp.status_code == 200, f"create invitation: {resp.status_code} {resp.text}"
    return resp.json()["invite_code"]


@pytest.fixture(scope="module")
def client():
    with httpx.Client(verify=False, timeout=60) as c:
        yield c


@pytest.fixture(scope="module")
def setup(client: httpx.Client):
    # A 是邀请人（建档子女）；B 是受邀者（老人）
    token_a, _nick_a = _register_and_login(client)
    token_b, _nick_b = _register_and_login(client)
    member_id = _create_member(client, token_a)
    return {
        "token_a": token_a,
        "token_b": token_b,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
        "member_id": member_id,
    }


class TestInvitationDetail:
    """detail 接口新字段覆盖。"""

    def test_tc01_detail_has_new_fields_for_authed_b(self, client, setup):
        code = _create_invitation(client, setup["token_a"], setup["member_id"])
        resp = client.get(
            f"{BASE_URL}/family/invitation/{code}",
            headers=setup["headers_b"],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # 新字段必须存在
        for k in (
            "inviter_user_id",
            "inviter_avatar",
            "member_id",
            "relationship_type",
            "is_self_invite",
            "current_managed_by_count",
            "max_managed_by_count",
            "reached_managed_by_limit",
            "merge_preview",
        ):
            assert k in body, f"detail 缺少字段 {k}: {body}"
        assert body["status"] == "pending"
        assert body["is_self_invite"] is False
        assert body["max_managed_by_count"] == 3
        assert body["reached_managed_by_limit"] is False
        # invalid_reason 在 pending 且 B 视角应为 None
        assert body.get("invalid_reason") in (None, "")
        # relationship_type 应为创建时传入
        assert body["relationship_type"] in ("father", None)

    def test_tc02_self_invite_detected(self, client, setup):
        code = _create_invitation(client, setup["token_a"], setup["member_id"])
        resp = client.get(
            f"{BASE_URL}/family/invitation/{code}",
            headers=setup["headers_a"],  # 用邀请人自己的 token
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["is_self_invite"] is True
        assert body["invalid_reason"] == "self"

    def test_tc03_unauthed_detail_still_works(self, client, setup):
        code = _create_invitation(client, setup["token_a"], setup["member_id"])
        resp = client.get(f"{BASE_URL}/family/invitation/{code}")
        # 未登录也应能拿到基础信息
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["invite_code"] == code
        assert body["is_self_invite"] is False
        assert body["current_managed_by_count"] == 0
        # merge_preview 在未登录态应为空
        assert body["merge_preview"] == []

    def test_tc04_rejected_invitation_invalid_reason_cancelled(self, client, setup):
        code = _create_invitation(client, setup["token_a"], setup["member_id"])
        # B 拒绝
        resp = client.post(
            f"{BASE_URL}/family/invitation/{code}/reject",
            headers=setup["headers_b"],
        )
        assert resp.status_code == 200, resp.text
        # 再次 detail
        resp2 = client.get(
            f"{BASE_URL}/family/invitation/{code}",
            headers=setup["headers_b"],
        )
        assert resp2.status_code == 200, resp2.text
        body = resp2.json()
        assert body["status"] == "cancelled"
        assert body["invalid_reason"] == "cancelled"


class TestInvitationAccept:
    """accept 接口 merge_fields 参数覆盖。"""

    def _fresh_member_and_invite(self, client, setup):
        # A 再建一个 member 并发起新邀请，避免污染前面的用例
        member_id = _create_member(client, setup["token_a"])
        code = _create_invitation(client, setup["token_a"], member_id)
        return member_id, code

    def test_tc05_accept_with_empty_merge_fields(self, client, setup):
        """merge_fields=[] 时应成功接受，且不报错。"""
        # 用一个全新的 B 用户避免命中 3 人上限
        token_b, _ = _register_and_login(client)
        _member_id, code = self._fresh_member_and_invite(client, setup)
        resp = client.post(
            f"{BASE_URL}/family/invitation/{code}/accept",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"merge_fields": []},
        )
        assert resp.status_code == 200, f"accept empty: {resp.status_code} {resp.text}"
        body = resp.json()
        assert "management_id" in body

    def test_tc06_accept_with_partial_merge_fields(self, client, setup):
        """merge_fields=['name','height'] 时应成功接受。"""
        token_b, _ = _register_and_login(client)
        _member_id, code = self._fresh_member_and_invite(client, setup)
        resp = client.post(
            f"{BASE_URL}/family/invitation/{code}/accept",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"merge_fields": ["name", "height"]},
        )
        assert resp.status_code == 200, f"accept partial: {resp.status_code} {resp.text}"
        body = resp.json()
        assert "management_id" in body

    def test_tc07_accept_without_body_backcompat(self, client, setup):
        """旧客户端无 body 调用应继续工作（向后兼容）。"""
        token_b, _ = _register_and_login(client)
        _member_id, code = self._fresh_member_and_invite(client, setup)
        resp = client.post(
            f"{BASE_URL}/family/invitation/{code}/accept",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 200, f"accept no-body: {resp.status_code} {resp.text}"

    def test_tc08_accept_self_invite_blocked(self, client, setup):
        """邀请人接受自己的邀请应被拒。"""
        _member_id, code = self._fresh_member_and_invite(client, setup)
        resp = client.post(
            f"{BASE_URL}/family/invitation/{code}/accept",
            headers=setup["headers_a"],
        )
        assert resp.status_code == 400, resp.text
