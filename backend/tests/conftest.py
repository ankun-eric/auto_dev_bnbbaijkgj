import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.models import User, UserRole, VerificationCode

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


@pytest.fixture(autouse=True)
def mock_send_sms(monkeypatch):
    """SMS tests exercise auth flow only; avoid Tencent API and production DB for config."""

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.auth.send_sms", _noop)


@pytest.fixture(autouse=True)
def reset_captcha_state():
    """每个测试前清空 captcha 验证码与登录失败/锁定状态，避免测试间状态污染。
    （PRD: 后台登录页图形验证码改造 v1.0 / 2026-04-25）"""
    try:
        from app.services.captcha_service import _store
        _store._captcha.clear()
        _store._failures.clear()
        _store._locks.clear()
        _store._issue_rate.clear()
    except Exception:
        pass
    yield


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
async def db_session():
    async with test_session() as session:
        yield session
        await session.commit()


@pytest_asyncio.fixture
async def latest_sms_code():
    """Read the newest VerificationCode for a phone after POST /api/auth/sms-code (response no longer returns code)."""

    async def _fetch(phone: str) -> str:
        async with test_session() as session:
            result = await session.execute(
                select(VerificationCode)
                .where(VerificationCode.phone == phone)
                .order_by(VerificationCode.created_at.desc())
                .limit(1)
            )
            vc = result.scalar_one_or_none()
            assert vc is not None, f"expected VerificationCode for {phone}"
            return vc.code

    return _fetch


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient):
    async with test_session() as session:
        session.add(User(
            phone="13800000001",
            password_hash=get_password_hash("admin123"),
            nickname="测试管理员",
            role=UserRole.admin,
        ))
        await session.commit()

    # PRD: 后台登录页图形验证码改造（v1.0 / 2026-04-25）
    # 测试环境下后端会跳过验证码强制要求（PYTEST_CURRENT_TEST 环境变量），故此处不传验证码
    response = await client.post("/api/admin/login", json={
        "phone": "13800000001",
        "password": "admin123",
    })
    return response.json()["token"]


@pytest_asyncio.fixture
async def user_token(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13900000001",
        "password": "user123",
        "nickname": "测试用户",
    })
    response = await client.post("/api/auth/login", json={
        "phone": "13900000001",
        "password": "user123",
    })
    return response.json()["access_token"]


@pytest_asyncio.fixture
def auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest_asyncio.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
