import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "phone": "13800001111",
        "password": "test1234",
        "nickname": "新用户",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["phone"] == "13800001111"
    assert data["user"]["nickname"] == "新用户"
    assert data["user"]["role"] == "user"
    assert data["user"]["status"] == "active"


@pytest.mark.asyncio
async def test_register_duplicate_phone(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13800002222",
        "password": "test1234",
        "nickname": "用户A",
    })
    response = await client.post("/api/auth/register", json={
        "phone": "13800002222",
        "password": "test5678",
        "nickname": "用户B",
    })
    assert response.status_code == 400
    assert "已注册" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_default_nickname(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "phone": "13800003333",
        "password": "test1234",
    })
    assert response.status_code == 200
    assert response.json()["user"]["nickname"] == "用户3333"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13800004444",
        "password": "mypassword",
    })
    response = await client.post("/api/auth/login", json={
        "phone": "13800004444",
        "password": "mypassword",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["phone"] == "13800004444"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13800005555",
        "password": "correct",
    })
    response = await client.post("/api/auth/login", json={
        "phone": "13800005555",
        "password": "wrong",
    })
    assert response.status_code == 400
    assert "密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_phone(client: AsyncClient):
    response = await client.post("/api/auth/login", json={
        "phone": "19999999999",
        "password": "whatever",
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers):
    response = await client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "13900000001"
    assert data["nickname"] == "测试用户"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, auth_headers):
    response = await client.put("/api/auth/me", json={
        "nickname": "新昵称",
        "avatar": "https://example.com/avatar.png",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["nickname"] == "新昵称"
    assert data["avatar"] == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_update_profile_partial(client: AsyncClient, auth_headers):
    response = await client.put("/api/auth/me", json={
        "nickname": "只改昵称",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["nickname"] == "只改昵称"
