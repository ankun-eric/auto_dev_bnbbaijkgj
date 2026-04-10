import pytest
import httpx

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, verify=False, timeout=30.0, follow_redirects=True) as c:
        yield c


def test_h5_homepage_accessible(client):
    """H5 首页可访问"""
    resp = client.get("/")
    assert resp.status_code == 200


def test_chat_page_accessible(client):
    """聊天页面可访问"""
    resp = client.get("/chat/1")
    assert resp.status_code == 200


def test_asr_token_endpoint(client):
    """ASR 令牌接口可用"""
    resp = client.post("/api/search/asr/token")
    assert resp.status_code in (200, 201, 422), f"Unexpected status {resp.status_code}: {resp.text}"


def test_asr_recognize_endpoint(client):
    """ASR 识别接口可用（空请求应返回 422 而非 500）"""
    resp = client.post("/api/search/asr/recognize")
    assert resp.status_code != 500, f"Server error 500: {resp.text}"
    assert resp.status_code in (200, 400, 422), f"Unexpected status {resp.status_code}: {resp.text}"


def test_backend_health_check(client):
    """后端健康检查"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
