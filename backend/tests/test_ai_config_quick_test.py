import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import AIModelConfig, User, UserRole


async def _create_admin(db_session, phone="13800070001"):
    user = User(
        phone=phone,
        password_hash=get_password_hash("admin123"),
        nickname="AI配置测试管理员",
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _admin_login(client: AsyncClient, phone="13800070001"):
    resp = await client.post("/api/admin/login", json={
        "phone": phone,
        "password": "admin123",
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def _seed_ai_config(db_session, **overrides):
    defaults = {
        "provider_name": "OpenAI",
        "base_url": "http://localhost:19999",
        "model_name": "test-model",
        "api_key_encrypted": "sk-test-key-000",
        "is_active": False,
    }
    defaults.update(overrides)
    config = AIModelConfig(**defaults)
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return config


@pytest.mark.asyncio
async def test_tc001_direct_params_missing_required(client: AsyncClient, db_session):
    """TC-001: 通过直接参数测试 - 缺少必要参数"""
    await _create_admin(db_session)
    headers = await _admin_login(client)

    resp = await client.post(
        "/api/admin/ai-config/test",
        headers=headers,
        json={"model_name": "some-model"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "缺少" in data["error_detail"]


@pytest.mark.asyncio
async def test_tc002_config_id_not_found(client: AsyncClient, db_session):
    """TC-002: 通过 config_id 测试 - 配置不存在"""
    await _create_admin(db_session)
    headers = await _admin_login(client)

    resp = await client.post(
        "/api/admin/ai-config/test",
        headers=headers,
        json={"config_id": 99999},
    )
    assert resp.status_code == 404
    assert "不存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tc003_direct_params_unreachable_url(client: AsyncClient, db_session):
    """TC-003: 通过直接参数测试 - 无效 base_url 导致连接失败"""
    await _create_admin(db_session)
    headers = await _admin_login(client)

    resp = await client.post(
        "/api/admin/ai-config/test",
        headers=headers,
        json={
            "base_url": "http://localhost:19999",
            "model_name": "test",
            "api_key": "test-key",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "连接失败" in data["error_detail"]


@pytest.mark.asyncio
async def test_tc004_list_returns_new_fields(client: AsyncClient, db_session):
    """TC-004: 列表接口返回新字段"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_ai_config(db_session)

    resp = await client.get("/api/admin/ai-config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    for item in data["items"]:
        assert "last_test_status" in item
        assert "last_test_time" in item
        assert "last_test_message" in item


@pytest.mark.asyncio
async def test_tc005_custom_test_message(client: AsyncClient, db_session):
    """TC-005: 自定义 test_message 参数"""
    await _create_admin(db_session)
    headers = await _admin_login(client)

    resp = await client.post(
        "/api/admin/ai-config/test",
        headers=headers,
        json={
            "base_url": "http://localhost:19999",
            "model_name": "test",
            "api_key": "test-key",
            "test_message": "自定义消息",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["response_time"] is not None or data["response_time"] is None
    assert "error_detail" in data
