import httpx
import pytest

BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"


def test_h5_home():
    r = httpx.get(f"{BASE}/", follow_redirects=True, verify=False, timeout=30)
    assert r.status_code == 200


def test_search_page():
    r = httpx.get(f"{BASE}/search", follow_redirects=True, verify=False, timeout=30)
    assert r.status_code == 200


def test_hot_search():
    r = httpx.get(f"{BASE}/api/search/hot", verify=False, timeout=30)
    assert r.status_code == 200


def test_asr_token():
    r = httpx.post(f"{BASE}/api/search/asr/token", verify=False, timeout=30)
    # 即使未配置 ASR，也应返回 200（success: false 或带 provider）
    assert r.status_code == 200


def test_search_suggest():
    r = httpx.get(
        f"{BASE}/api/search/suggest", params={"q": "感冒"}, verify=False, timeout=30
    )
    assert r.status_code == 200
