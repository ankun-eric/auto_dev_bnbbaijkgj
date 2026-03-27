import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_health_profile(client: AsyncClient, auth_headers):
    response = await client.post("/api/health/profile", json={
        "height": 175.5,
        "weight": 70.0,
        "blood_type": "A",
        "gender": "male",
        "birthday": "1990-01-15",
        "smoking": "never",
        "drinking": "occasionally",
        "exercise_habit": "3 times/week",
        "sleep_habit": "7-8 hours",
        "diet_habit": "balanced",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["height"] == 175.5
    assert data["weight"] == 70.0
    assert data["blood_type"] == "A"
    assert data["gender"] == "male"
    assert data["birthday"] == "1990-01-15"


@pytest.mark.asyncio
async def test_create_health_profile_duplicate(client: AsyncClient, auth_headers):
    await client.post("/api/health/profile", json={
        "height": 170.0,
    }, headers=auth_headers)
    response = await client.post("/api/health/profile", json={
        "height": 180.0,
    }, headers=auth_headers)
    assert response.status_code == 400
    assert "已存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_health_profile(client: AsyncClient, auth_headers):
    await client.post("/api/health/profile", json={
        "height": 170.0,
        "weight": 65.0,
    }, headers=auth_headers)
    response = await client.get("/api/health/profile", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["height"] == 170.0
    assert data["weight"] == 65.0


@pytest.mark.asyncio
async def test_get_health_profile_not_found(client: AsyncClient, auth_headers):
    response = await client.get("/api/health/profile", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_health_profile(client: AsyncClient, auth_headers):
    await client.post("/api/health/profile", json={
        "height": 170.0,
        "weight": 65.0,
    }, headers=auth_headers)
    response = await client.put("/api/health/profile", json={
        "weight": 68.0,
        "exercise_habit": "daily",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["weight"] == 68.0
    assert data["exercise_habit"] == "daily"
    assert data["height"] == 170.0


@pytest.mark.asyncio
async def test_update_health_profile_creates_if_missing(client: AsyncClient, auth_headers):
    response = await client.put("/api/health/profile", json={
        "height": 180.0,
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["height"] == 180.0


@pytest.mark.asyncio
async def test_create_allergy(client: AsyncClient, auth_headers):
    response = await client.post("/api/health/allergies", json={
        "allergy_type": "food",
        "allergy_name": "花生",
        "severity": "severe",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["allergy_type"] == "food"
    assert data["allergy_name"] == "花生"
    assert data["severity"] == "severe"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_allergies(client: AsyncClient, auth_headers):
    await client.post("/api/health/allergies", json={
        "allergy_type": "food",
        "allergy_name": "花生",
    }, headers=auth_headers)
    await client.post("/api/health/allergies", json={
        "allergy_type": "drug",
        "allergy_name": "青霉素",
    }, headers=auth_headers)
    response = await client.get("/api/health/allergies", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_delete_allergy(client: AsyncClient, auth_headers):
    create_resp = await client.post("/api/health/allergies", json={
        "allergy_type": "food",
        "allergy_name": "虾",
    }, headers=auth_headers)
    allergy_id = create_resp.json()["id"]
    response = await client.delete(f"/api/health/allergies/{allergy_id}", headers=auth_headers)
    assert response.status_code == 200

    list_resp = await client.get("/api/health/allergies", headers=auth_headers)
    assert list_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_create_medical_history(client: AsyncClient, auth_headers):
    response = await client.post("/api/health/medical-history", json={
        "disease_name": "高血压",
        "diagnosis_date": "2020-06-01",
        "status": "active",
        "notes": "需要长期服药",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["disease_name"] == "高血压"
    assert data["diagnosis_date"] == "2020-06-01"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_list_medical_history(client: AsyncClient, auth_headers):
    await client.post("/api/health/medical-history", json={
        "disease_name": "高血压",
    }, headers=auth_headers)
    await client.post("/api/health/medical-history", json={
        "disease_name": "糖尿病",
    }, headers=auth_headers)
    response = await client.get("/api/health/medical-history", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    response = await client.get("/api/health/profile")
    assert response.status_code == 401

    response = await client.post("/api/health/profile", json={"height": 170.0})
    assert response.status_code == 401

    response = await client.get("/api/health/allergies")
    assert response.status_code == 401

    response = await client.post("/api/health/allergies", json={
        "allergy_type": "food",
        "allergy_name": "花生",
    })
    assert response.status_code == 401
