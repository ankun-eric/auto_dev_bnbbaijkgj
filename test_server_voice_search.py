import pytest
import httpx
import io
import asyncio

BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.get(f"{BASE}/api/health")
        assert r.status_code == 200

@pytest.mark.asyncio
async def test_asr_token():
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.post(f"{BASE}/api/search/asr/token")
        assert r.status_code in (200, 400)

@pytest.mark.asyncio
async def test_asr_recognize_no_file():
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.post(f"{BASE}/api/search/asr/recognize")
        assert r.status_code == 422

@pytest.mark.asyncio
async def test_asr_recognize_empty_audio():
    async with httpx.AsyncClient(verify=False) as c:
        files = {"audio_file": ("test.wav", io.BytesIO(b""), "audio/wav")}
        data = {"format": "wav", "sample_rate": "16000"}
        r = await c.post(f"{BASE}/api/search/asr/recognize", files=files, data=data)
        result = r.json()
        assert r.status_code == 200
        assert result.get("success") == False
        assert result.get("error_code") in ("ASR_DISABLED", "AUDIO_EMPTY")

@pytest.mark.asyncio
async def test_asr_recognize_with_audio():
    async with httpx.AsyncClient(verify=False) as c:
        fake_audio = b"\x00" * 1000
        files = {"audio_file": ("test.webm", io.BytesIO(fake_audio), "audio/webm")}
        data = {"format": "webm", "sample_rate": "16000"}
        r = await c.post(f"{BASE}/api/search/asr/recognize", files=files, data=data)
        result = r.json()
        assert r.status_code == 200
        assert "success" in result

@pytest.mark.asyncio
async def test_search_hot():
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.get(f"{BASE}/api/search/hot")
        assert r.status_code == 200

@pytest.mark.asyncio
async def test_search_suggest():
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.get(f"{BASE}/api/search/suggest", params={"q": "感冒"})
        assert r.status_code == 200

@pytest.mark.asyncio
async def test_search_query():
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.get(f"{BASE}/api/search", params={"q": "健康", "type": "all", "page": 1, "page_size": 10})
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

@pytest.mark.asyncio
async def test_search_drug_keywords():
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.get(f"{BASE}/api/search/drug-keywords")
        assert r.status_code == 200

@pytest.mark.asyncio
async def test_search_history_no_auth():
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.get(f"{BASE}/api/search/history")
        assert r.status_code == 401

@pytest.mark.asyncio
async def test_admin_login_and_search_history():
    async with httpx.AsyncClient(verify=False) as c:
        login = await c.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
        if login.status_code == 200:
            token = login.json().get("access_token") or login.json().get("token")
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                r = await c.get(f"{BASE}/api/search/history", headers=headers)
                assert r.status_code == 200

@pytest.mark.asyncio
async def test_h5_search_page():
    async with httpx.AsyncClient(verify=False, follow_redirects=True) as c:
        r = await c.get(f"{BASE}/search")
        assert r.status_code == 200
