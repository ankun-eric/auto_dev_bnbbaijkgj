"""Tests for AppKey-based Tencent Cloud SMS sending and SMS config/template seeding."""
import hashlib
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.models import (
    SmsConfig,
    SmsLog,
    SmsTemplate,
    User,
    UserRole,
    VerificationCode,
)
from app.services.sms_service import (
    _resolve_sms_config,
    _send_via_tencent_appkey,
    encrypt_secret_key,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with test_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def setup_database(prepare_database):
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(delete(table))
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db():
    async with test_session() as session:
        yield session
        await session.commit()


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, db: AsyncSession):
    db.add(User(
        phone="13800000001",
        password_hash=get_password_hash("admin123"),
        nickname="测试管理员",
        role=UserRole.admin,
    ))
    await db.commit()
    response = await client.post("/api/admin/login", json={
        "phone": "13800000001",
        "password": "admin123",
    })
    return {"Authorization": f"Bearer {response.json()['token']}"}


# ──── _resolve_sms_config tests ────


@pytest.mark.asyncio
async def test_resolve_config_prefers_cam_over_appkey(db: AsyncSession):
    """When DB config has both CAM credentials and AppKey, auth_mode should be 'cam'."""
    db.add(SmsConfig(
        provider="tencent",
        secret_id="test_secret_id",
        secret_key_encrypted=encrypt_secret_key("test_secret_key"),
        sdk_app_id="1400920269",
        app_key="test_app_key",
        sign_name="测试签名",
        template_id="2201340",
        is_active=True,
    ))
    await db.commit()

    cfg = await _resolve_sms_config(db, provider="tencent")
    assert cfg["auth_mode"] == "cam"
    assert cfg["secret_id"] == "test_secret_id"


@pytest.mark.asyncio
async def test_resolve_config_appkey_only(db: AsyncSession):
    """When DB config has only AppKey (no CAM), auth_mode should be 'appkey'."""
    db.add(SmsConfig(
        provider="tencent",
        sdk_app_id="1400920269",
        app_key="7e3c8242bf0799cca367fa18fa47a7ea",
        sign_name="呃唉帮帮网络",
        template_id="2201340",
        is_active=True,
    ))
    await db.commit()

    cfg = await _resolve_sms_config(db, provider="tencent")
    assert cfg["auth_mode"] == "appkey"
    assert cfg["app_key"] == "7e3c8242bf0799cca367fa18fa47a7ea"
    assert cfg["sdk_app_id"] == "1400920269"
    assert cfg["sign_name"] == "呃唉帮帮网络"
    assert cfg["template_id"] == "2201340"


@pytest.mark.asyncio
async def test_resolve_config_env_appkey_fallback():
    """When no DB config exists, fall back to env vars AppKey if CAM not set."""
    with patch("app.services.sms_service.settings") as mock_settings, \
         patch("app.services.sms_service._get_db_sms_config", return_value=None):
        mock_settings.TENCENT_SMS_SECRET_ID = ""
        mock_settings.TENCENT_SMS_SECRET_KEY = ""
        mock_settings.TENCENT_SMS_APP_KEY = "test_appkey"
        mock_settings.TENCENT_SMS_SDK_APP_ID = "1400000000"
        mock_settings.TENCENT_SMS_SIGN_NAME = "测试"
        mock_settings.TENCENT_SMS_TEMPLATE_ID = "123456"

        cfg = await _resolve_sms_config()
        assert cfg["auth_mode"] == "appkey"
        assert cfg["app_key"] == "test_appkey"


@pytest.mark.asyncio
async def test_resolve_config_raises_when_no_credentials():
    """When no credentials are available at all, should raise RuntimeError."""
    with patch("app.services.sms_service.settings") as mock_settings, \
         patch("app.services.sms_service._get_db_sms_config", return_value=None):
        mock_settings.TENCENT_SMS_SECRET_ID = ""
        mock_settings.TENCENT_SMS_SECRET_KEY = ""
        mock_settings.TENCENT_SMS_APP_KEY = ""
        mock_settings.TENCENT_SMS_SDK_APP_ID = ""

        with pytest.raises(RuntimeError, match="短信服务未配置"):
            await _resolve_sms_config()


# ──── _send_via_tencent_appkey tests ────


@pytest.mark.asyncio
async def test_appkey_signature_calculation():
    """Verify the HMAC-SHA256 signature is correctly computed."""
    cfg = {
        "app_key": "testkey123",
        "sdk_app_id": "1400920269",
        "sign_name": "测试",
        "template_id": "2201340",
    }

    with patch("app.services.sms_service.random.randint", return_value=123456), \
         patch("time.time", return_value=1700000000):
        import httpx

        mock_response = MagicMock()
        mock_response.json.return_value = {"result": 0, "errmsg": "OK"}

        async def mock_post(url, json=None):
            sig_raw = f"appkey=testkey123&random=123456&time=1700000000&mobile=13800138000"
            expected_sig = hashlib.sha256(sig_raw.encode("utf-8")).hexdigest()
            assert json["sig"] == expected_sig
            assert json["tpl_id"] == 2201340
            assert json["params"] == ["654321", "5"]
            assert json["sign"] == "测试"
            assert json["tel"]["mobile"] == "13800138000"
            assert "sdkappid=1400920269" in url
            return mock_response

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await _send_via_tencent_appkey("13800138000", "654321", cfg)


@pytest.mark.asyncio
async def test_appkey_send_with_custom_template_params():
    """Custom template_params should be passed through to the API."""
    cfg = {
        "app_key": "testkey",
        "sdk_app_id": "1400920269",
        "sign_name": "测试",
        "template_id": "2201340",
    }

    mock_response = MagicMock()
    mock_response.json.return_value = {"result": 0, "errmsg": "OK"}

    captured_body = {}

    async def mock_post(url, json=None):
        captured_body.update(json)
        return mock_response

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        await _send_via_tencent_appkey(
            "13800138000", "123456", cfg,
            template_params=["ABCDEF", "10"],
        )

    assert captured_body["params"] == ["ABCDEF", "10"]


@pytest.mark.asyncio
async def test_appkey_send_raises_on_api_error():
    """Should raise RuntimeError when API returns non-zero result."""
    cfg = {
        "app_key": "testkey",
        "sdk_app_id": "1400920269",
        "sign_name": "测试",
        "template_id": "2201340",
    }

    mock_response = MagicMock()
    mock_response.json.return_value = {"result": 1014, "errmsg": "签名未审批"}

    async def mock_post(url, json=None):
        return mock_response

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="签名未审批"):
            await _send_via_tencent_appkey("13800138000", "123456", cfg)


# ──── End-to-end SMS login flow with AppKey config ────


@pytest.mark.asyncio
async def test_sms_login_flow_with_appkey_config(client: AsyncClient, db: AsyncSession):
    """Full SMS login flow should work when only AppKey config is available."""
    db.add(SmsConfig(
        provider="tencent",
        sdk_app_id="1400920269",
        app_key="7e3c8242bf0799cca367fa18fa47a7ea",
        sign_name="呃唉帮帮网络",
        template_id="2201340",
        is_active=True,
    ))
    await db.commit()

    with patch("app.api.auth.send_sms", new_callable=AsyncMock) as mock_send:
        resp = await client.post("/api/auth/sms-code", json={
            "phone": "13800099100",
            "type": "login",
        })
        assert resp.status_code == 200
        assert resp.json()["message"] == "验证码已发送"
        mock_send.assert_called_once()

    async with test_session() as session:
        result = await session.execute(
            select(VerificationCode)
            .where(VerificationCode.phone == "13800099100")
            .order_by(VerificationCode.created_at.desc())
            .limit(1)
        )
        vc = result.scalar_one_or_none()
        assert vc is not None
        code = vc.code

    login_resp = await client.post("/api/auth/sms-login", json={
        "phone": "13800099100",
        "code": code,
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert data["is_new_user"] is True


# ──── Admin SMS test endpoint with AppKey config ────


@pytest.mark.asyncio
async def test_admin_sms_test_with_appkey_config(
    client: AsyncClient, db: AsyncSession, admin_headers: dict,
):
    """Admin SMS test send should work with AppKey-only config."""
    db.add(SmsConfig(
        provider="tencent",
        sdk_app_id="1400920269",
        app_key="7e3c8242bf0799cca367fa18fa47a7ea",
        sign_name="呃唉帮帮网络",
        template_id="2201340",
        is_active=True,
    ))
    db.add(SmsTemplate(
        name="登录验证",
        provider="tencent",
        template_id="2201340",
        content="{1}为您的登录验证码，请于{2}分钟内填写，如非本人操作，请忽略本短信。",
        sign_name="呃唉帮帮网络",
        scene="login",
        status=True,
    ))
    await db.commit()

    with patch("app.services.sms_service._send_via_tencent_appkey", new_callable=AsyncMock) as mock_send:
        resp = await client.post(
            "/api/admin/sms/test",
            json={
                "phone": "13800099200",
                "template_id": "2201340",
                "provider": "tencent",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["preview_content"] is not None


# ──── SMS config GET returns AppKey-only config ────


@pytest.mark.asyncio
async def test_get_sms_config_shows_appkey_config(
    client: AsyncClient, db: AsyncSession, admin_headers: dict,
):
    """GET /api/admin/sms/config should show config even when only AppKey is set."""
    db.add(SmsConfig(
        provider="tencent",
        sdk_app_id="1400920269",
        app_key="7e3c8242bf0799cca367fa18fa47a7ea",
        sign_name="呃唉帮帮网络",
        template_id="2201340",
        is_active=True,
    ))
    await db.commit()

    resp = await client.get("/api/admin/sms/config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tencent"]["sdk_app_id"] == "1400920269"
    assert data["tencent"]["app_key"] == "7e3c8242bf0799cca367fa18fa47a7ea"
    assert data["tencent"]["sign_name"] == "呃唉帮帮网络"
    assert data["tencent"]["is_active"] is True
