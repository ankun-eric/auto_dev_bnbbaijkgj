"""[BUG-FIX-INVITE-NULL-MEMBER 2026-05-25]
邀请页"选择关系"导致预创建被守护人档案的 Bug 修复回归测试。

核心点：
- 情况 2（不传 member_id）创建邀请，应当不预创建 Tab
- 情况 1（传 member_id）保持原有行为
- 接受邀请时才补建 Tab
- 守护配额计算包含 pending 邀请
- 情况 2 邀请允许并存多条 pending
- 邀请详情接口对 member_id=NULL 健壮

运行：pytest backend/tests/test_invite_no_phantom_tab_20260525.py -v
"""

import random
import string

import httpx
import pytest

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api"

MAX_MANAGED_COUNT = 10


def _random_phone() -> str:
    return "138" + "".join(random.choices(string.digits, k=8))


def register_and_login(client: httpx.Client, phone: str | None = None) -> str:
    if not phone:
        phone = _random_phone()
    nickname = f"test_{phone[-4:]}"
    client.post(f"{BASE_URL}/auth/register", json={
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


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _list_members(client: httpx.Client, token: str) -> list[dict]:
    resp = client.get(f"{BASE_URL}/family/members", headers=_headers(token))
    assert resp.status_code == 200, f"List members failed: {resp.text}"
    return resp.json().get("items", [])


@pytest.fixture(scope="module")
def client():
    with httpx.Client(verify=False, timeout=60) as c:
        yield c


# ---------------------------------------------------------------------------
# T1: 情况 2 不预创建 Tab
# ---------------------------------------------------------------------------
def test_t1_case2_no_phantom_tab(client: httpx.Client):
    token_a = register_and_login(client)

    before = _list_members(client, token_a)
    before_len = len(before)

    resp = client.post(
        f"{BASE_URL}/family/invitation",
        headers=_headers(token_a),
        json={"relation_type": "妈妈"},
    )
    assert resp.status_code == 200, f"Create invitation failed: {resp.text}"
    body = resp.json()
    assert "invite_code" in body and body["invite_code"]

    after = _list_members(client, token_a)
    non_self_after = [m for m in after if not m.get("is_self")]
    non_self_before = [m for m in before if not m.get("is_self")]
    assert len(non_self_after) == len(non_self_before), (
        f"Phantom tab created! before non_self={len(non_self_before)}, "
        f"after non_self={len(non_self_after)}: {non_self_after}"
    )
    assert len(after) == before_len


# ---------------------------------------------------------------------------
# T2: 情况 1 正常 Tab 邀请
# ---------------------------------------------------------------------------
def test_t2_case1_with_member_id(client: httpx.Client):
    token_a = register_and_login(client)

    resp = client.post(
        f"{BASE_URL}/family/members",
        headers=_headers(token_a),
        json={
            "nickname": f"测试家人_{random.randint(1000, 9999)}",
            "relationship_type": "父亲",
            "gender": "male",
        },
    )
    assert resp.status_code == 200, f"Create member failed: {resp.text}"
    member_id = resp.json()["id"]

    resp = client.post(
        f"{BASE_URL}/family/invitation",
        headers=_headers(token_a),
        json={"member_id": member_id},
    )
    assert resp.status_code == 200, f"Case1 invitation failed: {resp.text}"
    assert resp.json().get("invite_code")


# ---------------------------------------------------------------------------
# T3: 情况 2 接受后才建 Tab
# ---------------------------------------------------------------------------
def test_t3_case2_tab_created_on_accept(client: httpx.Client):
    token_a = register_and_login(client)
    token_b = register_and_login(client)

    before = _list_members(client, token_a)
    before_non_self_ids = {m["id"] for m in before if not m.get("is_self")}

    resp = client.post(
        f"{BASE_URL}/family/invitation",
        headers=_headers(token_a),
        json={"relation_type": "妈妈"},
    )
    assert resp.status_code == 200
    code = resp.json()["invite_code"]

    mid_list = _list_members(client, token_a)
    mid_non_self_ids = {m["id"] for m in mid_list if not m.get("is_self")}
    assert mid_non_self_ids == before_non_self_ids, "情况 2 邀请阶段不应建 Tab"

    resp = client.post(
        f"{BASE_URL}/family/invitation/{code}/accept",
        headers=_headers(token_b),
    )
    assert resp.status_code == 200, f"Accept failed: {resp.text}"

    after = _list_members(client, token_a)
    after_non_self = [m for m in after if not m.get("is_self")]
    new_tabs = [m for m in after_non_self if m["id"] not in before_non_self_ids]
    assert len(new_tabs) == 1, f"接受后应恰好新增 1 个 Tab，得到 {len(new_tabs)}: {new_tabs}"
    new_tab = new_tabs[0]
    assert new_tab.get("nickname") == "" or new_tab.get("nickname") is None, (
        f"接受后 nickname 应为空，得到 {new_tab.get('nickname')!r}"
    )
    assert new_tab.get("relationship_type") == "妈妈", (
        f"接受后 relationship_type 应为'妈妈'，得到 {new_tab.get('relationship_type')!r}"
    )


# ---------------------------------------------------------------------------
# T4: 守护配额含 pending
# ---------------------------------------------------------------------------
def test_t4_quota_includes_pending(client: httpx.Client):
    token_a = register_and_login(client)

    success = 0
    last_resp = None
    for i in range(MAX_MANAGED_COUNT + 2):
        resp = client.post(
            f"{BASE_URL}/family/invitation",
            headers=_headers(token_a),
            json={"relation_type": f"朋友{i}"},
        )
        last_resp = resp
        if resp.status_code == 200:
            success += 1
        else:
            break

    assert success <= MAX_MANAGED_COUNT, (
        f"成功发起 {success} 次邀请超出上限 {MAX_MANAGED_COUNT}"
    )
    assert last_resp is not None
    assert last_resp.status_code == 400, (
        f"达到上限后应返回 400，实际 {last_resp.status_code}: {last_resp.text}"
    )
    assert "管理人数已达上限" in last_resp.text, (
        f"错误文案应包含'管理人数已达上限'，实际: {last_resp.text}"
    )


# ---------------------------------------------------------------------------
# T5: 情况 2 允许并存多条 pending
# ---------------------------------------------------------------------------
def test_t5_case2_multiple_pending_coexist(client: httpx.Client):
    token_a = register_and_login(client)

    codes = []
    for _ in range(3):
        resp = client.post(
            f"{BASE_URL}/family/invitation",
            headers=_headers(token_a),
            json={"relation_type": "妈妈"},
        )
        assert resp.status_code == 200, f"Create case2 invitation failed: {resp.text}"
        codes.append(resp.json()["invite_code"])

    assert len(set(codes)) == 3

    for code in codes:
        resp = client.get(
            f"{BASE_URL}/family/invitation/{code}",
            headers=_headers(token_a),
        )
        assert resp.status_code == 200, f"Get invitation {code} failed: {resp.text}"
        body = resp.json()
        assert body["status"] == "pending", (
            f"邀请 {code} 应为 pending，实际 {body['status']}（情况 2 不应互相取消）"
        )


# ---------------------------------------------------------------------------
# T6: member_id=NULL 的邀请详情接口健壮
# ---------------------------------------------------------------------------
def test_t6_invitation_detail_with_null_member(client: httpx.Client):
    token_a = register_and_login(client)

    resp = client.post(
        f"{BASE_URL}/family/invitation",
        headers=_headers(token_a),
        json={"relation_type": "爸爸"},
    )
    assert resp.status_code == 200
    code = resp.json()["invite_code"]

    resp = client.get(
        f"{BASE_URL}/family/invitation/{code}",
        headers=_headers(token_a),
    )
    assert resp.status_code == 200, f"Get invitation detail failed: {resp.text}"
    body = resp.json()
    assert body.get("member_id") is None
    assert body.get("relation_type") == "爸爸"
