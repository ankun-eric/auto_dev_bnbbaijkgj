import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_member(client: AsyncClient, auth_headers):
    response = await client.post("/api/family/members", json={
        "relationship_type": "spouse",
        "nickname": "我的配偶",
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
        "nickname": "父亲",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["member_user_id"] == family_user_id


@pytest.mark.asyncio
async def test_add_member_invalid_user_id(client: AsyncClient, auth_headers):
    response = await client.post("/api/family/members", json={
        "member_user_id": 99999,
        "relationship_type": "child",
        "nickname": "孩子",
    }, headers=auth_headers)
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient, auth_headers):
    await client.post("/api/family/members", json={
        "relationship_type": "spouse",
        "nickname": "配偶",
    }, headers=auth_headers)
    await client.post("/api/family/members", json={
        "relationship_type": "child",
        "nickname": "孩子",
    }, headers=auth_headers)

    response = await client.get("/api/family/members", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_members_empty(client: AsyncClient, auth_headers):
    response = await client.get("/api/family/members", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_member(client: AsyncClient, auth_headers):
    create_resp = await client.post("/api/family/members", json={
        "relationship_type": "parent",
        "nickname": "父亲",
    }, headers=auth_headers)
    member_id = create_resp.json()["id"]

    response = await client.delete(f"/api/family/members/{member_id}", headers=auth_headers)
    assert response.status_code == 200
    assert "移除" in response.json()["message"]

    list_resp = await client.get("/api/family/members", headers=auth_headers)
    assert list_resp.json()["total"] == 0


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
        "nickname": "配偶",
    })
    assert response.status_code == 401
