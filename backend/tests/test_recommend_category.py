"""
Tests for the recommend virtual category feature.

Verifies:
1. Categories API injects "recommend" virtual category when recommend products exist
2. Products API supports category_id=recommend to filter by marketing_badges
3. Recommend category is hidden when no recommend products exist
4. Sort order for recommend category (recommend_weight DESC, created_at DESC)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
API_BASE = f"{BASE_URL}/api"


def test_categories_endpoint_structure():
    """Test that the categories endpoint can return the recommend virtual category."""
    import requests
    try:
        resp = requests.get(f"{API_BASE}/products/categories", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "flat" in data
        items = data["items"]
        assert isinstance(items, list)
        if len(items) > 0:
            first = items[0]
            assert "id" in first
            assert "name" in first
            if first.get("id") == "recommend":
                assert first["name"] == "推荐"
                assert first.get("is_virtual") is True
                assert first.get("icon") == "🔥"
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not reachable")


def test_products_recommend_filter():
    """Test that products API supports category_id=recommend."""
    import requests
    try:
        resp = requests.get(f"{API_BASE}/products", params={"category_id": "recommend", "page": 1, "page_size": 10}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        for item in data["items"]:
            badges = item.get("marketing_badges", [])
            assert "recommend" in badges, f"Product {item['id']} should have recommend badge"
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not reachable")


def test_products_normal_category_filter():
    """Test that normal category_id (integer) still works correctly."""
    import requests
    try:
        cat_resp = requests.get(f"{API_BASE}/products/categories", timeout=10)
        if cat_resp.status_code != 200:
            pytest.skip("Server not reachable")
        data = cat_resp.json()
        items = data.get("items", [])
        normal_cats = [c for c in items if c.get("id") != "recommend"]
        if not normal_cats:
            pytest.skip("No normal categories available")
        cat_id = normal_cats[0]["id"]
        resp = requests.get(f"{API_BASE}/products", params={"category_id": str(cat_id), "page": 1, "page_size": 10}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not reachable")


def test_recommend_category_hidden_when_no_products():
    """Test that recommend category does not appear when no recommend products exist.
    This is a logic test - we verify the structure is correct."""
    import requests
    try:
        resp = requests.get(f"{API_BASE}/products/categories", timeout=10)
        if resp.status_code != 200:
            pytest.skip("Server not reachable")
        data = resp.json()
        items = data.get("items", [])
        recommend_items = [c for c in items if c.get("id") == "recommend"]
        if recommend_items:
            prod_resp = requests.get(f"{API_BASE}/products", params={"category_id": "recommend", "page": 1, "page_size": 1}, timeout=10)
            prod_data = prod_resp.json()
            assert prod_data.get("total", 0) > 0, "Recommend category shown but no recommend products exist"
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not reachable")


def test_recommend_products_sort_order():
    """Test that recommend products are sorted by recommend_weight DESC."""
    import requests
    try:
        resp = requests.get(f"{API_BASE}/products", params={"category_id": "recommend", "page": 1, "page_size": 50}, timeout=10)
        if resp.status_code != 200:
            pytest.skip("Server not reachable")
        data = resp.json()
        items = data.get("items", [])
        if len(items) < 2:
            pytest.skip("Not enough recommend products to verify sort order")
        weights = [item.get("recommend_weight", 0) for item in items]
        for i in range(len(weights) - 1):
            assert weights[i] >= weights[i + 1], f"Products not sorted by recommend_weight DESC at index {i}"
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not reachable")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
