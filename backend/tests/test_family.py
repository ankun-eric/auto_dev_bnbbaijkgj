import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_member(client: AsyncClient, auth_headers):
    response = await client.post("/api/family/members", json={
        "relationship_type": "spouse",
        "name": "我的配偶",
        "nickname": "我的配偶",
        "gender": "female",
        "birthday": "1990-05-20",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["relationship_type"] == "spouse"
    assert data["nickname"] == "我的配偶"
    assert data["status"] == "active"
    assert "id" in data


@pytest.mark.asyncio
async def test_add_member_with_user_id(client: AsyncClient, auth_headers, admin_token):
    reg_resp = await client.post("/api/auth/register", json={
        "phone": "13700001111",
        "password": "test1234",
        "nickname": "家人",
    })
    family_user_id = reg_resp.json()["user"]["id"]

    response = await client.post("/api/family/members", json={
        "member_user_id": family_user_id,
        "relationship_type": "parent",
        "name": "父亲",
        "nickname": "父亲",
        "gender": "male",
        "birthday": "1960-03-15",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["member_user_id"] == family_user_id


@pytest.mark.asyncio
async def test_add_member_invalid_user_id(client: AsyncClient, auth_headers):
    response = await client.post("/api/family/members", json={
        "member_user_id": 99999,
        "relationship_type": "child",
        "name": "孩子",
        "nickname": "孩子",
        "gender": "male",
        "birthday": "2020-01-01",
    }, headers=auth_headers)
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient, auth_headers):
    await client.post("/api/family/members", json={
        "relationship_type": "spouse",
        "name": "配偶",
        "nickname": "配偶",
        "gender": "female",
        "birthday": "1992-06-10",
    }, headers=auth_headers)
    await client.post("/api/family/members", json={
        "relationship_type": "child",
        "name": "孩子",
        "nickname": "孩子",
        "gender": "male",
        "birthday": "2018-09-01",
    }, headers=auth_headers)

    response = await client.get("/api/family/members", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3  # 1 auto-created self + 2 added


@pytest.mark.asyncio
async def test_list_members_empty(client: AsyncClient, auth_headers):
    response = await client.get("/api/family/members", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1  # auto-created "本人"
    assert data["items"][0]["is_self"] is True


@pytest.mark.asyncio
async def test_delete_member(client: AsyncClient, auth_headers):
    create_resp = await client.post("/api/family/members", json={
        "relationship_type": "parent",
        "name": "父亲",
        "nickname": "父亲",
        "gender": "male",
        "birthday": "1965-04-12",
    }, headers=auth_headers)
    assert create_resp.status_code == 200
    member_id = create_resp.json()["id"]

    response = await client.delete(f"/api/family/members/{member_id}", headers=auth_headers)
    assert response.status_code == 200
    assert "移除" in response.json()["message"]

    list_resp = await client.get("/api/family/members", headers=auth_headers)
    assert list_resp.json()["total"] == 1  # only self remains


@pytest.mark.asyncio
async def test_delete_member_not_found(client: AsyncClient, auth_headers):
    response = await client.delete("/api/family/members/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_family_unauthorized(client: AsyncClient):
    response = await client.get("/api/family/members")
    assert response.status_code == 401

    response = await client.post("/api/family/members", json={
        "relationship_type": "spouse",
        "name": "配偶",
        "nickname": "配偶",
        "gender": "female",
        "birthday": "1990-01-01",
    })
    assert response.status_code == 401


# --- New tests for the "本人" auto-creation bug fix ---


@pytest.mark.asyncio
async def test_auto_create_self_member(client: AsyncClient, auth_headers):
    """New user calling GET /api/family/members should auto-create an is_self=True member."""
    response = await client.get("/api/family/members", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    self_members = [m for m in data["items"] if m["is_self"] is True]
    assert len(self_members) == 1
    assert self_members[0]["nickname"] == "本人"
    assert self_members[0]["relationship_type"] == "本人"


@pytest.mark.asyncio
async def test_self_member_is_first(client: AsyncClient, auth_headers):
    """Self member should always be sorted first in the list."""
    await client.post("/api/family/members", json={
        "relationship_type": "spouse",
        "name": "配偶",
        "nickname": "配偶",
        "gender": "female",
        "birthday": "1993-08-22",
    }, headers=auth_headers)
    await client.post("/api/family/members", json={
        "relationship_type": "child",
        "name": "孩子",
        "nickname": "孩子",
        "gender": "male",
        "birthday": "2020-03-15",
    }, headers=auth_headers)

    response = await client.get("/api/family/members", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 2
    assert items[0]["is_self"] is True


@pytest.mark.asyncio
async def test_self_member_cannot_be_deleted(client: AsyncClient, auth_headers):
    """DELETE /api/family/members/{self_member_id} should return 400."""
    list_resp = await client.get("/api/family/members", headers=auth_headers)
    items = list_resp.json()["items"]
    self_member = next(m for m in items if m["is_self"] is True)

    response = await client.delete(
        f"/api/family/members/{self_member['id']}", headers=auth_headers
    )
    assert response.status_code == 400
    assert "不可删除" in response.json()["detail"]


@pytest.mark.asyncio
async def test_no_duplicate_self_member(client: AsyncClient, auth_headers):
    """Multiple calls to GET /api/family/members should not create duplicate self members."""
    for _ in range(3):
        response = await client.get("/api/family/members", headers=auth_headers)
        assert response.status_code == 200

    data = response.json()
    self_members = [m for m in data["items"] if m["is_self"] is True]
    assert len(self_members) == 1
