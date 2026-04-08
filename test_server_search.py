"""
Server API Tests for 统一搜索 (Unified Search) Feature
Target: https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857
"""

import time
import uuid

import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"
TEST_USER_PHONE = "13800138999"


def api(path: str) -> str:
    return f"{BASE}{path}"


# ═══════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token via /api/admin/login."""
    r = requests.post(
        api("/api/admin/login"),
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
        verify=False,
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def user_token():
    """Try to get a user token via SMS login; skip if unavailable."""
    r = requests.post(
        api("/api/auth/sms-code"),
        json={"phone": TEST_USER_PHONE, "type": "login"},
        verify=False,
        timeout=15,
    )
    if r.status_code not in (200, 201):
        pytest.skip(f"Cannot send SMS code: {r.status_code} {r.text[:200]}")

    for code in ["1234", "0000", "123456", "666666", "8888"]:
        r2 = requests.post(
            api("/api/auth/sms-login"),
            json={"phone": TEST_USER_PHONE, "code": code},
            verify=False,
            timeout=15,
        )
        if r2.status_code == 200:
            data = r2.json()
            token = data.get("access_token") or data.get("token")
            if token:
                return token

    pytest.skip("Cannot obtain user token (SMS code unknown)")


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# ═══════════════════════════════════════════════
#  1. Hot Search Words (public)
# ═══════════════════════════════════════════════


class TestHotSearch:
    def test_01_hot_keywords_200(self):
        r = requests.get(api("/api/search/hot"), verify=False, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert isinstance(data, list)

    def test_02_hot_keywords_structure(self):
        r = requests.get(api("/api/search/hot"), verify=False, timeout=10)
        data = r.json()
        if len(data) > 0:
            item = data[0]
            assert "keyword" in item
            assert "source" in item


# ═══════════════════════════════════════════════
#  2. Search Suggest (public)
# ═══════════════════════════════════════════════


class TestSearchSuggest:
    def test_03_suggest_200(self):
        r = requests.get(api("/api/search/suggest"), params={"q": "健"}, verify=False, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert isinstance(data, list)

    def test_04_suggest_structure(self):
        r = requests.get(api("/api/search/suggest"), params={"q": "健"}, verify=False, timeout=10)
        data = r.json()
        for item in data:
            assert "keyword" in item
            assert "is_drug_keyword" in item


# ═══════════════════════════════════════════════
#  3. Drug Keywords (public)
# ═══════════════════════════════════════════════


class TestDrugKeywords:
    def test_05_drug_keywords_200(self):
        r = requests.get(api("/api/search/drug-keywords"), verify=False, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert isinstance(data, list)

    def test_06_drug_keywords_structure(self):
        r = requests.get(api("/api/search/drug-keywords"), verify=False, timeout=10)
        data = r.json()
        if len(data) > 0:
            item = data[0]
            assert "id" in item
            assert "keyword" in item
            assert "is_active" in item


# ═══════════════════════════════════════════════
#  4. Unified Search (public)
# ═══════════════════════════════════════════════


class TestUnifiedSearch:
    def test_07_search_all_200(self):
        r = requests.get(
            api("/api/search"), params={"q": "健康", "type": "all"}, verify=False, timeout=10
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "type_counts" in data

    def test_08_search_article_200(self):
        r = requests.get(
            api("/api/search"), params={"q": "健康", "type": "article"}, verify=False, timeout=10
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        for item in data["items"]:
            assert item["type"] == "article"

    def test_09_search_pagination(self):
        r = requests.get(
            api("/api/search"),
            params={"q": "健康", "type": "all", "page": 1, "page_size": 5},
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_10_search_missing_q_422(self):
        r = requests.get(api("/api/search"), params={"type": "all"}, verify=False, timeout=10)
        assert r.status_code == 422


# ═══════════════════════════════════════════════
#  5. Search History (user auth required)
# ═══════════════════════════════════════════════


class TestSearchHistory:
    def test_11_history_no_auth_401(self):
        r = requests.get(api("/api/search/history"), verify=False, timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_12_get_history(self, user_headers):
        r = requests.get(api("/api/search/history"), headers=user_headers, verify=False, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_13_clear_history(self, user_headers):
        r = requests.delete(api("/api/search/history"), headers=user_headers, verify=False, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "message" in data


# ═══════════════════════════════════════════════
#  6. Admin - Recommend Words CRUD
# ═══════════════════════════════════════════════


class TestAdminRecommendWords:
    _created_id = None

    def test_14_list_recommend_words(self, admin_headers):
        r = requests.get(
            api("/api/admin/search/recommend-words"), headers=admin_headers, verify=False, timeout=10
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_15_create_recommend_word(self, admin_headers):
        unique_kw = f"自动测试推荐词_{uuid.uuid4().hex[:6]}"
        r = requests.post(
            api("/api/admin/search/recommend-words"),
            headers=admin_headers,
            json={"keyword": unique_kw, "sort_order": 99, "category_hint": "测试分类"},
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200, f"Create recommend word failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data["keyword"] == unique_kw
        assert "id" in data
        TestAdminRecommendWords._created_id = data["id"]

    def test_16_update_recommend_word(self, admin_headers):
        wid = TestAdminRecommendWords._created_id
        if not wid:
            pytest.skip("No recommend word created in prior test")
        r = requests.put(
            api(f"/api/admin/search/recommend-words/{wid}"),
            headers=admin_headers,
            json={"sort_order": 1},
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["sort_order"] == 1

    def test_17_delete_recommend_word(self, admin_headers):
        wid = TestAdminRecommendWords._created_id
        if not wid:
            pytest.skip("No recommend word created in prior test")
        r = requests.delete(
            api(f"/api/admin/search/recommend-words/{wid}"),
            headers=admin_headers,
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200
        assert "message" in r.json()


# ═══════════════════════════════════════════════
#  7. Admin - Search Statistics
# ═══════════════════════════════════════════════


class TestAdminStatistics:
    def test_18_statistics_200(self, admin_headers):
        r = requests.get(
            api("/api/admin/search/statistics"), headers=admin_headers, verify=False, timeout=10
        )
        assert r.status_code == 200
        data = r.json()
        assert "top_keywords" in data
        assert "trend" in data
        assert "no_result_keywords" in data
        assert "type_distribution" in data


# ═══════════════════════════════════════════════
#  8. Admin - Block Words CRUD
# ═══════════════════════════════════════════════


class TestAdminBlockWords:
    _created_id = None

    def test_19_list_block_words(self, admin_headers):
        r = requests.get(
            api("/api/admin/search/block-words"), headers=admin_headers, verify=False, timeout=10
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_20_create_block_word(self, admin_headers):
        unique_kw = f"屏蔽测试词_{uuid.uuid4().hex[:6]}"
        r = requests.post(
            api("/api/admin/search/block-words"),
            headers=admin_headers,
            json={"keyword": unique_kw, "block_mode": "full", "is_active": True},
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200, f"Create block word failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data["keyword"] == unique_kw
        TestAdminBlockWords._created_id = data["id"]

    def test_21_batch_import_block_words(self, admin_headers):
        kws = [f"批量屏蔽_{uuid.uuid4().hex[:6]}" for _ in range(3)]
        r = requests.post(
            api("/api/admin/search/block-words/batch"),
            headers=admin_headers,
            json={"keywords": kws, "block_mode": "full"},
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "added" in data
        assert data["added"] == 3

    def test_22_delete_block_word(self, admin_headers):
        wid = TestAdminBlockWords._created_id
        if not wid:
            pytest.skip("No block word created in prior test")
        r = requests.delete(
            api(f"/api/admin/search/block-words/{wid}"),
            headers=admin_headers,
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200
        assert "message" in r.json()


# ═══════════════════════════════════════════════
#  9. Admin - ASR Config
# ═══════════════════════════════════════════════


class TestAdminAsrConfig:
    def test_23_get_asr_config(self, admin_headers):
        r = requests.get(
            api("/api/admin/search/asr-config"), headers=admin_headers, verify=False, timeout=10
        )
        assert r.status_code == 200
        data = r.json()
        assert "provider" in data
        assert "is_enabled" in data

    def test_24_update_asr_config(self, admin_headers):
        r = requests.put(
            api("/api/admin/search/asr-config"),
            headers=admin_headers,
            json={"supported_dialects": "普通话,粤语,四川话"},
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "普通话" in (data.get("supported_dialects") or "")


# ═══════════════════════════════════════════════
#  10. Admin Auth Guard
# ═══════════════════════════════════════════════


class TestAdminAuthGuard:
    def test_25_no_token_returns_401_recommend(self):
        r = requests.get(api("/api/admin/search/recommend-words"), verify=False, timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_26_no_token_returns_401_block(self):
        r = requests.get(api("/api/admin/search/block-words"), verify=False, timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_27_no_token_returns_401_statistics(self):
        r = requests.get(api("/api/admin/search/statistics"), verify=False, timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_28_no_token_returns_401_asr(self):
        r = requests.get(api("/api/admin/search/asr-config"), verify=False, timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_29_user_token_returns_403_for_admin(self, user_token):
        """Non-admin user should be rejected by admin endpoints."""
        headers = {"Authorization": f"Bearer {user_token}"}
        r = requests.get(
            api("/api/admin/search/recommend-words"), headers=headers, verify=False, timeout=10
        )
        assert r.status_code in (401, 403), f"Expected 401/403 for non-admin, got {r.status_code}"


# ═══════════════════════════════════════════════
#  11. Block Word Effect (business logic)
# ═══════════════════════════════════════════════


class TestBlockWordEffect:
    _block_word_id = None
    _block_keyword = f"违禁测试词_{uuid.uuid4().hex[:6]}"

    def test_30_add_block_word(self, admin_headers):
        r = requests.post(
            api("/api/admin/search/block-words"),
            headers=admin_headers,
            json={
                "keyword": self._block_keyword,
                "block_mode": "full",
                "is_active": True,
            },
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200, f"Failed to add block word: {r.status_code} {r.text[:300]}"
        TestBlockWordEffect._block_word_id = r.json()["id"]

    def test_31_search_blocked_word_returns_empty(self, admin_headers):
        if not TestBlockWordEffect._block_word_id:
            pytest.skip("Block word not created")
        time.sleep(0.5)
        r = requests.get(
            api("/api/search"),
            params={"q": self._block_keyword, "type": "all"},
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0, f"Expected 0 results for blocked word, got {data['total']}"
        assert len(data["items"]) == 0

    def test_32_cleanup_block_word(self, admin_headers):
        wid = TestBlockWordEffect._block_word_id
        if wid:
            requests.delete(
                api(f"/api/admin/search/block-words/{wid}"),
                headers=admin_headers,
                verify=False,
                timeout=10,
            )


# ═══════════════════════════════════════════════
#  12. Search Log (public)
# ═══════════════════════════════════════════════


class TestSearchLog:
    def test_33_record_search_click(self):
        r = requests.post(
            api("/api/search/log"),
            json={"keyword": "测试搜索日志", "clicked_type": "article", "clicked_item_id": 1},
            verify=False,
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "message" in data
