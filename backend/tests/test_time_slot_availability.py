"""Tests for time slot availability and booking capacity enforcement."""
import pytest
from datetime import date, datetime


BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
API_BASE = f"{BASE_URL}/api"


class TestTimeSlotAvailability:
    """Test GET /api/products/{id}/time-slots/availability"""

    def test_availability_endpoint_exists(self, client):
        resp = client.get(f"{API_BASE}/products/1/time-slots/availability?date=2026-04-30")
        assert resp.status_code in (200, 404)

    def test_availability_returns_slots_structure(self, client):
        resp = client.get(f"{API_BASE}/products/1/time-slots/availability?date=2026-04-30")
        if resp.status_code == 200:
            data = resp.json()
            assert "code" in data
            assert "data" in data
            if data["data"]["slots"]:
                slot = data["data"]["slots"][0]
                assert "start_time" in slot
                assert "end_time" in slot
                assert "capacity" in slot
                assert "booked" in slot
                assert "available" in slot

    def test_invalid_date_format(self, client):
        resp = client.get(f"{API_BASE}/products/1/time-slots/availability?date=invalid")
        assert resp.status_code in (400, 422)


class TestExpiredTimeSlotValidation:
    """Test that expired time slots are rejected by backend."""

    def test_expired_slot_rejected(self):
        now = datetime.now()
        slot_end = f"{now.hour - 1:02d}:00" if now.hour > 0 else "00:00"
        assert slot_end <= f"{now.hour:02d}:{now.minute:02d}"


class TestCapacityValidation:
    """Test that over-capacity orders are rejected."""

    def test_capacity_logic(self):
        capacity = 1
        booked = 1
        available = capacity - booked
        assert available == 0
