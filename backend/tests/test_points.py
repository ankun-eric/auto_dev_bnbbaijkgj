import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_balance(client: AsyncClient, auth_headers):
    response = await client.get("/api/points/balance", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "points" in data
    assert "member_level" in data
    assert data["points"] == 0
    assert data["member_level"] == 0


@pytest.mark.asyncio
async def test_get_balance_unauthorized(client: AsyncClient):
    response = await client.get("/api/points/balance")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_signin(client: AsyncClient, auth_headers):
    response = await client.post("/api/points/signin", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["consecutive_days"] == 1
    assert data["points_earned"] == 5
    assert "sign_date" in data

    balance_resp = await client.get("/api/points/balance", headers=auth_headers)
    assert balance_resp.json()["points"] == 5


@pytest.mark.asyncio
async def test_signin_duplicate(client: AsyncClient, auth_headers):
    await client.post("/api/points/signin", headers=auth_headers)
    response = await client.post("/api/points/signin", headers=auth_headers)
    assert response.status_code == 400
    assert "已签到" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_records(client: AsyncClient, auth_headers):
    await client.post("/api/points/signin", headers=auth_headers)

    response = await client.get("/api/points/records", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["items"][0]["type"] == "signin"
    assert data["items"][0]["points"] == 5


@pytest.mark.asyncio
async def test_list_records_empty(client: AsyncClient, auth_headers):
    response = await client.get("/api/points/records", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_records_filter_type(client: AsyncClient, auth_headers):
    await client.post("/api/points/signin", headers=auth_headers)

    response = await client.get(
        "/api/points/records", params={"points_type": "signin"}, headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1

    response = await client.get(
        "/api/points/records", params={"points_type": "purchase"}, headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0
