"""
非 UI 自动化测试：部署后语音搜索相关页面与 API 可用性。
使用 requests（同步）。
"""
import pytest
import requests

BASE = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API = f"{BASE}/api"
TIMEOUT = 30


@pytest.fixture
def session():
    s = requests.Session()
    s.headers.update({"User-Agent": "pytest-server-voice-search/1.0"})
    yield s


def test_tc001_h5_search_page_ok(session):
    """TC-001: H5 搜索页面可访问"""
    r = session.get(f"{BASE}/search/", timeout=TIMEOUT)
    assert r.status_code == 200, f"expected 200, got {r.status_code}"


def test_tc002_asr_token_ok(session):
    """TC-002: ASR Token 端点可用"""
    r = session.post(
        f"{API}/search/asr/token",
        json={},
        headers={"Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:500]}"
    data = r.json()
    assert "provider" in data, f"response missing 'provider': {data}"


def test_tc003_search_hot_ok(session):
    """TC-003: 搜索热门端点可用"""
    r = session.get(f"{API}/search/hot", timeout=TIMEOUT)
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:500]}"
    data = r.json()
    assert isinstance(data, list), f"expected array, got {type(data)}: {data!r}"


def test_tc004_search_suggest_ok(session):
    """TC-004: 搜索建议端点可用"""
    r = session.get(
        f"{API}/search/suggest",
        params={"q": "测试"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:500]}"
    data = r.json()
    assert isinstance(data, list), f"expected array, got {type(data)}: {data!r}"


def test_tc005_h5_home_ok(session):
    """TC-005: H5 首页可访问"""
    r = session.get(f"{BASE}/", timeout=TIMEOUT)
    assert r.status_code == 200, f"expected 200, got {r.status_code}"


def test_tc006_api_health_ok(session):
    """TC-006: 后端 API 健康检查"""
    r = session.get(f"{API}/health", timeout=TIMEOUT)
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:500]}"
