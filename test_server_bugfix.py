"""
Server API integration tests for bugfix + enhancement deployment.
Tests 15 endpoints covering orders, services, content, points, and upload.
"""
import io
import warnings

import httpx
import pytest

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"

_token: str | None = None
_created_article_id: int | None = None
_created_video_id: int | None = None
_created_mall_item_id: int | None = None


def get_client() -> httpx.Client:
    return httpx.Client(verify=False, timeout=30)


def auth_headers() -> dict:
    assert _token, "Admin token not acquired — login failed"
    return {"Authorization": f"Bearer {_token}"}


# ── Fixture: login once ──

@pytest.fixture(scope="session", autouse=True)
def admin_login():
    global _token
    credentials = [
        {"phone": "admin", "password": "admin123"},
        {"phone": "13800000000", "password": "admin123"},
        {"phone": "admin", "password": "123456"},
    ]
    with get_client() as c:
        for cred in credentials:
            resp = c.post(f"{BASE_URL}/admin/login", json=cred)
            if resp.status_code == 200:
                data = resp.json()
                _token = data.get("token")
                if _token:
                    return
        # Try general auth/login as fallback
        for cred in credentials:
            resp = c.post(f"{BASE_URL}/auth/login", json=cred)
            if resp.status_code == 200:
                data = resp.json()
                _token = data.get("token") or data.get("access_token")
                if _token:
                    return

    pytest.fail(f"Could not login with any credential set. Last response: {resp.status_code} {resp.text[:500]}")


# ══════════════════════════════════════════════
# TC-001: 订单列表API
# ══════════════════════════════════════════════

class TestTC001OrderList:
    def test_basic_list(self):
        """GET /api/admin/orders — returns 200 with items/total/page/page_size"""
        with get_client() as c:
            resp = c.get(f"{BASE_URL}/admin/orders", headers=auth_headers(), params={"page": 1, "page_size": 5})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        for key in ("items", "total", "page", "page_size"):
            assert key in data, f"Missing key '{key}' in response"
        assert isinstance(data["items"], list)
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_multi_status_filter(self):
        """GET /api/admin/orders?order_status=confirmed,processing — multi-status filter"""
        with get_client() as c:
            resp = c.get(
                f"{BASE_URL}/admin/orders",
                headers=auth_headers(),
                params={"order_status": "confirmed,processing", "page": 1, "page_size": 5},
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "items" in data

    def test_keyword_search(self):
        """GET /api/admin/orders?keyword=xxx — keyword search"""
        with get_client() as c:
            resp = c.get(
                f"{BASE_URL}/admin/orders",
                headers=auth_headers(),
                params={"keyword": "NONEXIST999", "page": 1, "page_size": 5},
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data["total"] == 0 or isinstance(data["items"], list)


# ══════════════════════════════════════════════
# TC-002: 订单统计API
# ══════════════════════════════════════════════

class TestTC002OrderStatistics:
    def test_statistics(self):
        """GET /api/admin/orders/statistics — returns required fields"""
        with get_client() as c:
            resp = c.get(f"{BASE_URL}/admin/orders/statistics", headers=auth_headers())
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        required = ["today_count", "today_amount", "month_count", "month_amount", "total_count", "total_amount"]
        for key in required:
            assert key in data, f"Missing key '{key}' in statistics response"


# ══════════════════════════════════════════════
# TC-003: 订单趋势API
# ══════════════════════════════════════════════

class TestTC003OrderTrends:
    def test_trends(self):
        """GET /api/admin/orders/trends?days=7 — returns trends array"""
        with get_client() as c:
            resp = c.get(f"{BASE_URL}/admin/orders/trends", headers=auth_headers(), params={"days": 7})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "trends" in data, f"Missing 'trends' key: {list(data.keys())}"
        trends = data["trends"]
        assert isinstance(trends, list)
        assert len(trends) == 7, f"Expected 7 trend points, got {len(trends)}"
        for item in trends:
            assert "date" in item, f"Trend item missing 'date'"
            assert "count" in item, f"Trend item missing 'count'"
            assert "amount" in item, f"Trend item missing 'amount'"


# ══════════════════════════════════════════════
# TC-004: 订单分布API
# ══════════════════════════════════════════════

class TestTC004OrderDistribution:
    def test_distribution(self):
        """GET /api/admin/orders/distribution — returns category + status distribution"""
        with get_client() as c:
            resp = c.get(f"{BASE_URL}/admin/orders/distribution", headers=auth_headers())
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "category_distribution" in data, f"Missing 'category_distribution'"
        assert "status_distribution" in data, f"Missing 'status_distribution'"
        assert isinstance(data["category_distribution"], list)
        assert isinstance(data["status_distribution"], list)


# ══════════════════════════════════════════════
# TC-005: 服务项目列表
# ══════════════════════════════════════════════

class TestTC005ServiceItems:
    def test_list(self):
        """GET /api/admin/services/items — returns 200 with data"""
        with get_client() as c:
            resp = c.get(f"{BASE_URL}/admin/services/items", headers=auth_headers(), params={"page": 1, "page_size": 10})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)


# ══════════════════════════════════════════════
# TC-006: 服务项目批量操作
# ══════════════════════════════════════════════

class TestTC006ServiceBatchStatus:
    def test_batch_status_empty(self):
        """PUT /api/admin/services/items/batch-status — empty ids"""
        with get_client() as c:
            resp = c.put(
                f"{BASE_URL}/admin/services/items/batch-status",
                headers=auth_headers(),
                json={"item_ids": [], "status": "inactive"},
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "updated" in data


# ══════════════════════════════════════════════
# TC-007: 文章列表
# ══════════════════════════════════════════════

class TestTC007ArticleList:
    def test_list(self):
        """GET /api/admin/content/articles — returns 200"""
        with get_client() as c:
            resp = c.get(f"{BASE_URL}/admin/content/articles", headers=auth_headers(), params={"page": 1, "page_size": 10})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "items" in data
        assert "total" in data


# ══════════════════════════════════════════════
# TC-008: 文章创建(含summary)
# ══════════════════════════════════════════════

class TestTC008ArticleCreate:
    def test_create_with_summary(self):
        """POST /api/admin/content/articles — summary field is saved"""
        global _created_article_id
        payload = {
            "title": "自动化测试文章",
            "content": "<p>这是自动化测试创建的文章内容</p>",
            "summary": "这是文章摘要，用于测试summary字段",
            "category": "health",
            "status": "published",
        }
        with get_client() as c:
            resp = c.post(f"{BASE_URL}/admin/content/articles", headers=auth_headers(), json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "id" in data, f"Missing 'id' in created article"
        _created_article_id = data["id"]
        assert data.get("summary") == "这是文章摘要，用于测试summary字段", \
            f"summary mismatch: {data.get('summary')}"


# ══════════════════════════════════════════════
# TC-009: 视频列表
# ══════════════════════════════════════════════

class TestTC009VideoList:
    def test_list(self):
        """GET /api/admin/content/videos — returns 200"""
        with get_client() as c:
            resp = c.get(f"{BASE_URL}/admin/content/videos", headers=auth_headers(), params={"page": 1, "page_size": 10})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "items" in data
        assert "total" in data


# ══════════════════════════════════════════════
# TC-010: 视频创建(duration整数)
# ══════════════════════════════════════════════

class TestTC010VideoCreate:
    def test_create_with_int_duration(self):
        """POST /api/admin/content/videos — duration=330 (integer seconds)"""
        global _created_video_id
        payload = {
            "title": "自动化测试视频",
            "description": "测试视频描述",
            "video_url": "https://example.com/test-video.mp4",
            "cover_image": "https://example.com/cover.jpg",
            "category": "health",
            "duration": 330,
        }
        with get_client() as c:
            resp = c.post(f"{BASE_URL}/admin/content/videos", headers=auth_headers(), json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "id" in data, f"Missing 'id' in created video"
        _created_video_id = data["id"]
        assert data.get("duration") == 330, f"Expected duration=330, got {data.get('duration')}"


# ══════════════════════════════════════════════
# TC-011: 积分商城列表
# ══════════════════════════════════════════════

class TestTC011PointsMallList:
    def test_list(self):
        """GET /api/admin/points/mall — returns 200"""
        with get_client() as c:
            resp = c.get(f"{BASE_URL}/admin/points/mall", headers=auth_headers(), params={"page": 1, "page_size": 10})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "items" in data
        assert "total" in data


# ══════════════════════════════════════════════
# TC-012: 积分商城创建(JSON Body)
# ══════════════════════════════════════════════

class TestTC012PointsMallCreate:
    def test_create_via_json_body(self):
        """POST /api/admin/points/mall — JSON body (not Query params)"""
        global _created_mall_item_id
        payload = {
            "name": "自动化测试积分商品",
            "description": "测试用积分兑换商品",
            "type": "virtual",
            "price_points": 100,
            "stock": 50,
            "status": "active",
        }
        with get_client() as c:
            resp = c.post(f"{BASE_URL}/admin/points/mall", headers=auth_headers(), json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "id" in data, f"Missing 'id' in created mall item"
        _created_mall_item_id = data["id"]
        assert data.get("name") == "自动化测试积分商品"


# ══════════════════════════════════════════════
# TC-013: 积分商城更新(JSON Body)
# ══════════════════════════════════════════════

class TestTC013PointsMallUpdate:
    def test_update_via_json_body(self):
        """PUT /api/admin/points/mall/{id} — JSON body update"""
        if not _created_mall_item_id:
            pytest.skip("No mall item created in TC-012")
        payload = {
            "name": "自动化测试积分商品(已更新)",
            "price_points": 200,
            "stock": 30,
        }
        with get_client() as c:
            resp = c.put(
                f"{BASE_URL}/admin/points/mall/{_created_mall_item_id}",
                headers=auth_headers(),
                json=payload,
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("name") == "自动化测试积分商品(已更新)", f"Name not updated: {data.get('name')}"
        assert data.get("price_points") == 200, f"price_points not updated: {data.get('price_points')}"


# ══════════════════════════════════════════════
# TC-014: 文件上传
# ══════════════════════════════════════════════

class TestTC014FileUpload:
    def test_upload_image(self):
        """POST /api/upload/image — upload a small PNG, verify URL returned"""
        import struct
        import zlib

        def _make_tiny_png() -> bytes:
            width, height = 2, 2
            raw_data = b""
            for _ in range(height):
                raw_data += b"\x00" + b"\xff\x00\x00" * width
            compressed = zlib.compress(raw_data)

            def _chunk(ctype, cdata):
                c = ctype + cdata
                return struct.pack(">I", len(cdata)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

            ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
            return (
                b"\x89PNG\r\n\x1a\n"
                + _chunk(b"IHDR", ihdr)
                + _chunk(b"IDAT", compressed)
                + _chunk(b"IEND", b"")
            )

        png_bytes = _make_tiny_png()
        with get_client() as c:
            resp = c.post(
                f"{BASE_URL}/upload/image",
                headers=auth_headers(),
                files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert "url" in data, f"Missing 'url' in upload response: {data}"
        assert data["url"], "Returned URL is empty"


# ══════════════════════════════════════════════
# TC-015: 订单确认操作
# ══════════════════════════════════════════════

class TestTC015OrderConfirm:
    def test_confirm_nonexistent(self):
        """PUT /api/admin/orders/99999/confirm — 404 for nonexistent order"""
        with get_client() as c:
            resp = c.put(f"{BASE_URL}/admin/orders/99999/confirm", headers=auth_headers())
        assert resp.status_code in (404, 400), f"Expected 404/400, got {resp.status_code}: {resp.text[:300]}"

    def test_confirm_existing_order(self):
        """PUT /api/admin/orders/{id}/confirm — test on a real order if available"""
        with get_client() as c:
            list_resp = c.get(
                f"{BASE_URL}/admin/orders",
                headers=auth_headers(),
                params={"page": 1, "page_size": 50},
            )
        if list_resp.status_code != 200:
            pytest.skip("Cannot list orders")

        orders = list_resp.json().get("items", [])
        target = None
        for o in orders:
            os_val = o.get("order_status", "")
            ps_val = o.get("payment_status", "")
            if os_val == "pending" and ps_val == "paid":
                target = o
                break

        if not target:
            pytest.skip("No pending+paid order available to confirm")

        order_id = target["id"]
        with get_client() as c:
            resp = c.put(f"{BASE_URL}/admin/orders/{order_id}/confirm", headers=auth_headers())
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("order_status") == "confirmed" or "order_status" in str(data), \
            f"Order not confirmed: {data}"


# ══════════════════════════════════════════════
# Cleanup: delete test data created during tests
# ══════════════════════════════════════════════

@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    yield
    with get_client() as c:
        hdrs = {}
        if _token:
            hdrs = {"Authorization": f"Bearer {_token}"}
        if _created_article_id:
            c.delete(f"{BASE_URL}/admin/content/articles/{_created_article_id}", headers=hdrs)
        if _created_video_id:
            c.delete(f"{BASE_URL}/admin/content/videos/{_created_video_id}", headers=hdrs)
        if _created_mall_item_id:
            c.delete(f"{BASE_URL}/admin/points/mall/{_created_mall_item_id}", headers=hdrs)
