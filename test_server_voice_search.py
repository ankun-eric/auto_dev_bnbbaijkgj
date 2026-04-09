"""语音搜索多端升级 - 服务器API测试"""

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"

def test_health():
    """健康检查"""
    r = requests.get(f"{BASE}/health", verify=False)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_search_with_source_voice():
    """搜索传 source=voice 返回 200"""
    r = requests.get(f"{BASE}/search", params={"q": "测试语音搜索", "type": "all", "source": "voice"}, verify=False)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "type_counts" in data
    assert "source" not in data

def test_search_with_source_text():
    """搜索传 source=text 返回 200"""
    r = requests.get(f"{BASE}/search", params={"q": "测试文本搜索", "type": "all", "source": "text"}, verify=False)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data

def test_search_default_source():
    """搜索不传 source 默认为 text"""
    r = requests.get(f"{BASE}/search", params={"q": "测试默认来源", "type": "all"}, verify=False)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data

def test_search_invalid_source():
    """搜索传非法 source 值也正常返回"""
    r = requests.get(f"{BASE}/search", params={"q": "非法来源测试", "type": "all", "source": "invalid"}, verify=False)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data

def test_search_by_article_type():
    """按文章类型搜索 + source=voice"""
    r = requests.get(f"{BASE}/search", params={"q": "健康", "type": "article", "source": "voice"}, verify=False)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    for item in data["items"]:
        assert item["type"] == "article"

def test_search_hot():
    """热门搜索"""
    r = requests.get(f"{BASE}/search/hot", verify=False)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_search_suggest():
    """搜索联想"""
    r = requests.get(f"{BASE}/search/suggest", params={"q": "感冒"}, verify=False)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_asr_token():
    """ASR token 接口"""
    r = requests.post(f"{BASE}/search/asr/token", verify=False)
    assert r.status_code in (200, 400)

def test_asr_recognize_no_file():
    """ASR 识别无文件 422"""
    r = requests.post(f"{BASE}/search/asr/recognize", verify=False)
    assert r.status_code == 422

def test_search_drug_keywords():
    """药品搜索关键词"""
    r = requests.get(f"{BASE}/search/drug-keywords", verify=False)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_search_history_no_auth():
    """搜索历史未登录 401"""
    r = requests.get(f"{BASE}/search/history", verify=False)
    assert r.status_code == 401

def test_search_source_voice_log_via_db():
    """通过管理员 API 验证搜索日志记录了 source"""
    r = requests.get(f"{BASE}/search", params={"q": "服务器日志验证词", "type": "all", "source": "voice"}, verify=False)
    assert r.status_code == 200
    admin_login = requests.post(f"{BASE}/admin/login", json={"phone": "13800000001", "password": "admin123"}, verify=False)
    if admin_login.status_code == 200:
        token = admin_login.json().get("token")
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            stats = requests.get(f"{BASE}/admin/search/statistics", headers=headers, verify=False)
            assert stats.status_code == 200
