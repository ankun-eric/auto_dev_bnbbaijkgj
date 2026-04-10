"""
Server-side integration tests for bini-health family/profile bug fixes.
Validates archive management related bug fixes on the deployed server.
"""

import random

import httpx
import pytest

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"


def random_phone() -> str:
    return f"199{random.randint(10000000, 99999999)}"


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_new_user(client: httpx.Client) -> dict:
    phone = random_phone()
    resp = client.post("/auth/register", json={
        "phone": phone,
        "password": "Test123456",
        "nickname": f"测试用户_{phone[-4:]}",
    })
    assert resp.status_code == 200, f"Registration failed ({resp.status_code}): {resp.text}"
    data = resp.json()
    return {
        "token": data["access_token"],
        "user": data["user"],
        "phone": phone,
    }


@pytest.fixture()
def client():
    with httpx.Client(base_url=API_URL, verify=False, timeout=30) as c:
        yield c


@pytest.fixture()
def user(client):
    return register_new_user(client)


# ─── Test 1: Registration creates a self member ───

def test_register_creates_self_member(client, user):
    resp = client.get("/family/members", headers=auth_headers(user["token"]))
    assert resp.status_code == 200, f"GET /family/members failed: {resp.text}"
    items = resp.json().get("items", [])
    self_members = [m for m in items if m.get("is_self")]
    assert len(self_members) >= 1, (
        f"No is_self=true member found after registration. items={items}"
    )


# ─── Test 2: Self member has relation_type ───

def test_self_member_has_relation_type(client, user):
    resp = client.get("/family/members", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    self_members = [m for m in items if m.get("is_self")]
    assert len(self_members) >= 1, "No self member found"
    self_member = self_members[0]
    assert self_member.get("relation_type_id") is not None, (
        f"Self member missing relation_type_id: {self_member}"
    )
    assert self_member.get("relation_type_name") == "本人", (
        f"Expected relation_type_name='本人', got '{self_member.get('relation_type_name')}'"
    )


# ─── Test 3: Self member health profile exists ───

def test_self_member_health_profile_exists(client, user):
    resp = client.get("/family/members", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    self_members = [m for m in items if m.get("is_self")]
    assert len(self_members) >= 1, "No self member found"
    member_id = self_members[0]["id"]

    hp_resp = client.get(
        f"/health/profile/member/{member_id}",
        headers=auth_headers(user["token"]),
    )
    assert hp_resp.status_code == 200, f"Health profile fetch failed: {hp_resp.text}"
    hp_data = hp_resp.json()
    assert hp_data.get("family_member_id") == member_id, (
        f"Expected family_member_id={member_id}, got {hp_data.get('family_member_id')}"
    )


# ─── Test 4: Guide Step1 save ───

def test_guide_step1_save(client, user):
    resp = client.get("/family/members", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    self_members = [m for m in items if m.get("is_self")]
    assert len(self_members) >= 1
    member_id = self_members[0]["id"]

    put_resp = client.put(
        f"/health/profile/member/{member_id}",
        headers=auth_headers(user["token"]),
        json={
            "name": "张三测试",
            "gender": "男",
            "birthday": "1990-05-15",
        },
    )
    assert put_resp.status_code == 200, f"Step1 save failed: {put_resp.text}"
    result = put_resp.json()
    assert result.get("name") == "张三测试"
    assert result.get("gender") == "男"
    assert result.get("birthday") == "1990-05-15"


# ─── Test 5: Guide Step1 syncs family member ───

def test_guide_step1_syncs_family_member(client, user):
    resp = client.get("/family/members", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    self_members = [m for m in items if m.get("is_self")]
    assert len(self_members) >= 1
    member_id = self_members[0]["id"]

    client.put(
        f"/health/profile/member/{member_id}",
        headers=auth_headers(user["token"]),
        json={
            "name": "李四同步",
            "gender": "女",
            "birthday": "1995-08-20",
        },
    )

    members_resp = client.get("/family/members", headers=auth_headers(user["token"]))
    assert members_resp.status_code == 200
    updated_items = members_resp.json().get("items", [])
    updated_self = [m for m in updated_items if m.get("is_self")]
    assert len(updated_self) >= 1
    member = updated_self[0]
    assert member.get("nickname") == "李四同步", (
        f"Expected nickname '李四同步', got '{member.get('nickname')}'"
    )
    assert member.get("gender") == "女", (
        f"Expected gender '女', got '{member.get('gender')}'"
    )
    assert member.get("birthday") == "1995-08-20", (
        f"Expected birthday '1995-08-20', got '{member.get('birthday')}'"
    )


# ─── Test 6: No duplicate self member ───

def test_no_duplicate_self_member(client, user):
    headers = auth_headers(user["token"])
    for _ in range(5):
        resp = client.get("/family/members", headers=headers)
        assert resp.status_code == 200

    resp = client.get("/family/members", headers=headers)
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    self_members = [m for m in items if m.get("is_self")]
    assert len(self_members) == 1, (
        f"Expected exactly 1 self member, found {len(self_members)}"
    )


# ─── Test 7: Add member validation ───

def test_add_member_validation(client, user):
    headers = auth_headers(user["token"])

    resp = client.post("/family/members", headers=headers, json={
        "relationship_type": "儿子",
        "gender": "男",
        "birthday": "2020-01-01",
    })
    assert resp.status_code == 400, (
        f"Expected 400 for missing name, got {resp.status_code}: {resp.text}"
    )

    resp = client.post("/family/members", headers=headers, json={
        "relationship_type": "儿子",
        "name": "小明",
        "birthday": "2020-01-01",
    })
    assert resp.status_code == 400, (
        f"Expected 400 for missing gender, got {resp.status_code}: {resp.text}"
    )

    resp = client.post("/family/members", headers=headers, json={
        "relationship_type": "儿子",
        "name": "小明",
        "gender": "男",
    })
    assert resp.status_code == 400, (
        f"Expected 400 for missing birthday, got {resp.status_code}: {resp.text}"
    )


# ─── Test 8: Add member success ───

def test_add_member_success(client, user):
    resp = client.post("/family/members", headers=auth_headers(user["token"]), json={
        "relationship_type": "儿子",
        "name": "小明测试",
        "gender": "男",
        "birthday": "2020-06-15",
    })
    assert resp.status_code == 200, (
        f"Add member failed: {resp.status_code} {resp.text}"
    )
    data = resp.json()
    assert data.get("nickname") == "小明测试"
    assert data.get("gender") == "男"
    assert data.get("is_self") is False


# ─── Test 9: Relation types ───

def test_relation_types(client):
    resp = client.get("/relation-types")
    assert resp.status_code == 200, f"Relation types failed: {resp.text}"
    data = resp.json()
    items = data.get("items", [])
    assert len(items) > 0, "No relation types returned"
    names = [item.get("name") for item in items]
    assert "本人" in names, f"'本人' not found in relation types: {names}"
    for item in items:
        assert "id" in item
        assert "name" in item


# ─── Test 10: Family members list ───

def test_family_members_list(client, user):
    resp = client.get("/family/members", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data, f"Response missing 'items': {data}"
    assert "total" in data, f"Response missing 'total': {data}"
    assert data["total"] >= 1, f"Expected total >= 1, got {data['total']}"
    assert len(data["items"]) >= 1
