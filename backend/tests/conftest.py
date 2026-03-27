import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
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


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13800000001",
        "password": "admin123",
        "nickname": "测试管理员",
    })
    response = await client.post("/api/auth/login", json={
        "phone": "13800000001",
        "password": "admin123",
    })
    return response.json()["access_token"]


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
