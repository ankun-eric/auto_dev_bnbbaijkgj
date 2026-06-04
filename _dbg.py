import asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.database import Base, get_db
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

engine = create_async_engine('sqlite+aiosqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
session = async_sessionmaker(engine)


async def odb():
    async with session() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise


app.dependency_overrides[get_db] = odb


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as c:
        r = await c.post('/api/auth/register', json={'phone': '13900000099', 'password': 'x123456', 'nickname': 't'})
        print('register', r.status_code)
        r = await c.post('/api/auth/login', json={'phone': '13900000099', 'password': 'x123456'})
        tok = r.json()['access_token']
        h = {'Authorization': 'Bearer ' + tok, 'Client-Type': 'h5-user'}
        rb = await c.post('/api/home_safety/devices/bind', json={'device_type': 7, 'gateway_sn': 'GWCOMPAT00001', 'device_sn': 'COMPAT01'}, headers=h)
        print('bind', rb.status_code, rb.text)
        rc = await c.post('/api/home_safety/callback/alarm', json={'device_sn': 'COMPAT01', 'type': 7, 'alarm_time': '2026-05-27T18:30:00'})
        print('callback', rc.status_code, rc.text)


asyncio.run(main())
