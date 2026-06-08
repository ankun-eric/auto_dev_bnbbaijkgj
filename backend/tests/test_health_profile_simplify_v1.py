"""Tests for health profile simplify v1
Covers:
1. _compute_missing_fields_v2 simplified logic
2. guide-status endpoints removed (404)
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.health_profile_self import _compute_missing_fields_v2, _is_name_empty, PLACEHOLDER_NAMES


class FakeProfile:
    """Mock HealthProfile for testing _compute_missing_fields_v2"""
    def __init__(self, name=None, gender=None, birthday=None):
        self.name = name
        self.gender = gender
        self.birthday = birthday


@pytest.mark.asyncio
class TestComputeMissingFieldsV2:
    """Test simplified _compute_missing_fields_v2 - only checks health_profiles"""

    async def test_profile_none_returns_all_missing(self):
        """When profile is None, all 3 fields missing"""
        db = AsyncMock()
        result = await _compute_missing_fields_v2(db, 1, None)
        assert result == ["name", "gender", "birthday"]

    async def test_all_fields_present_returns_empty(self):
        """When all 3 fields are present, returns empty list"""
        db = AsyncMock()
        profile = FakeProfile(name="张三", gender="男", birthday=date(1990, 1, 1))
        result = await _compute_missing_fields_v2(db, 1, profile)
        assert result == []

    async def test_name_placeholder_returns_name_missing(self):
        """When name is placeholder value '本人', returns ['name']"""
        db = AsyncMock()
        profile = FakeProfile(name="本人", gender="男", birthday=date(1990, 1, 1))
        result = await _compute_missing_fields_v2(db, 1, profile)
        assert "name" in result
        assert "gender" not in result
        assert "birthday" not in result

    async def test_name_empty_string_returns_name_missing(self):
        """When name is empty string, returns ['name']"""
        db = AsyncMock()
        profile = FakeProfile(name="", gender="男", birthday=date(1990, 1, 1))
        result = await _compute_missing_fields_v2(db, 1, profile)
        assert "name" in result

    async def test_gender_none_returns_gender_missing(self):
        """When gender is None, returns ['gender']"""
        db = AsyncMock()
        profile = FakeProfile(name="张三", gender=None, birthday=date(1990, 1, 1))
        result = await _compute_missing_fields_v2(db, 1, profile)
        assert "gender" in result
        assert "name" not in result
        assert "birthday" not in result

    async def test_gender_empty_string_returns_gender_missing(self):
        """When gender is empty string, returns ['gender']"""
        db = AsyncMock()
        profile = FakeProfile(name="张三", gender="", birthday=date(1990, 1, 1))
        result = await _compute_missing_fields_v2(db, 1, profile)
        assert "gender" in result

    async def test_gender_whitespace_returns_gender_missing(self):
        """When gender is whitespace only, returns ['gender']"""
        db = AsyncMock()
        profile = FakeProfile(name="张三", gender="   ", birthday=date(1990, 1, 1))
        result = await _compute_missing_fields_v2(db, 1, profile)
        assert "gender" in result

    async def test_birthday_none_returns_birthday_missing(self):
        """When birthday is None, returns ['birthday']"""
        db = AsyncMock()
        profile = FakeProfile(name="张三", gender="男", birthday=None)
        result = await _compute_missing_fields_v2(db, 1, profile)
        assert "birthday" in result
        assert "name" not in result
        assert "gender" not in result

    async def test_multiple_missing_fields(self):
        """When multiple fields missing, all are returned"""
        db = AsyncMock()
        profile = FakeProfile(name="本人", gender=None, birthday=None)
        result = await _compute_missing_fields_v2(db, 1, profile)
        assert sorted(result) == sorted(["name", "gender", "birthday"])

    async def test_does_not_query_users_table(self):
        """Verify function does NOT query users table (no 'real_name' lookup)"""
        db = AsyncMock()
        db.execute = AsyncMock()
        profile = FakeProfile(name="本人", gender="男", birthday=date(1990, 1, 1))
        result = await _compute_missing_fields_v2(db, 1, profile)
        # Should only return ['name'] without executing any additional DB queries
        assert result == ["name"]
        # db.execute should NOT have been called - simplified version doesn't query
        db.execute.assert_not_called()

    async def test_does_not_query_family_members(self):
        """Verify function does NOT query family_members table"""
        db = AsyncMock()
        db.execute = AsyncMock()
        profile = FakeProfile(name=None, gender=None, birthday=None)
        result = await _compute_missing_fields_v2(db, 1, profile)
        # profile is None so it returns directly without querying
        assert sorted(result) == sorted(["name", "gender", "birthday"])
        db.execute.assert_not_called()


class TestIsNameEmpty:
    """Test _is_name_empty helper"""

    def test_none_is_empty(self):
        assert _is_name_empty(None) is True

    def test_empty_string_is_empty(self):
        assert _is_name_empty("") is True

    def test_whitespace_is_empty(self):
        assert _is_name_empty("   ") is True

    def test_placeholder_self_is_empty(self):
        assert _is_name_empty("本人") is True
        assert _is_name_empty("我") is True
        assert _is_name_empty("self") is True
        assert _is_name_empty("Self") is True

    def test_real_name_not_empty(self):
        assert _is_name_empty("张三") is False
        assert _is_name_empty("李四") is False


class TestGuideStatusEndpointsRemoved:
    """Test that guide-status endpoints return 404 after removal"""

    @pytest.mark.anyio
    async def test_get_guide_status_404(self):
        """GET /api/health/guide-status should return 404"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health/guide-status")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_post_guide_status_404(self):
        """POST /api/health/guide-status should return 404"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/health/guide-status", json={"action": "skip"})
            assert resp.status_code == 404
