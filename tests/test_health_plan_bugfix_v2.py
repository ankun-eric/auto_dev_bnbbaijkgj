"""
Health Plan Bugfix V2 — Regression Tests
Covers four bugs fixed in this iteration:
  1. today-todos removes sub_groups nesting
  2. user-plans list filters deleted records
  3. New checkin-item detail endpoint
  4. New medication-reminder detail endpoint
"""
import os
import uuid
import warnings

import pytest
import requests

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = os.environ.get(
    "TEST_BASE_URL",
    "https://newbb.test.bangbangvip.com"
    "/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857",
)
TIMEOUT = 15
TEST_PHONE = "13800138000"
TEST_CODE = "123456"


def _uid():
    return uuid.uuid4().hex[:6]


# ──────────────── Fixtures ────────────────


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.verify = False
    return s


@pytest.fixture(scope="module")
def user_token(session):
    """Obtain user token via SMS login."""
    r = session.post(
        f"{BASE_URL}/api/auth/sms-code",
        json={"phone": TEST_PHONE, "type": "login"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"Send SMS code failed: {r.status_code} {r.text}"
    r = session.post(
        f"{BASE_URL}/api/auth/sms-login",
        json={"phone": TEST_PHONE, "code": TEST_CODE},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"SMS login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# ══════════════════════════════════════════
#  Bug 1: today-todos 移除 sub_groups 层级
# ══════════════════════════════════════════


class TestTodayTodosNoSubGroups:
    """Verify that today-todos groups no longer contain sub_groups;
    the '健康计划' group items should be a flat list."""

    def test_groups_have_no_sub_groups(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/today-todos",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "groups" in data
        for group in data["groups"]:
            sub = group.get("sub_groups")
            assert sub is None or sub == [], (
                f"Group '{group['group_name']}' still contains sub_groups: {sub}"
            )

    def test_health_plan_group_items_flat(self, session, user_headers):
        """Create a user plan so the '健康计划' group is non-empty,
        then verify its items are a flat list of todo items."""
        tag = _uid()
        cr = session.post(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=user_headers,
            json={
                "plan_name": f"FlatTest_{tag}",
                "description": "regression test",
                "duration_days": 7,
                "tasks": [{"task_name": "任务A", "sort_order": 0}],
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200, cr.text
        plan_id = cr.json()["id"]

        r = session.get(
            f"{BASE_URL}/api/health-plan/today-todos",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        groups = r.json()["groups"]
        custom_group = next(
            (g for g in groups if g.get("group_type") == "custom"),
            None,
        )
        assert custom_group is not None, "Missing '健康计划' (custom) group"

        assert isinstance(custom_group["items"], list)
        for item in custom_group["items"]:
            assert "id" in item
            assert "name" in item
            assert "type" in item
            assert not isinstance(item, list), "Item should be a dict, not a nested list"

        sub = custom_group.get("sub_groups")
        assert sub is None or sub == [], "custom group should have no sub_groups"

        # Cleanup
        session.delete(
            f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )


# ══════════════════════════════════════════
#  Bug 2: 用户计划列表过滤已删除记录
# ══════════════════════════════════════════


class TestUserPlansFilterDeleted:
    """After deleting a user plan, it must not appear in the list endpoint."""

    def test_deleted_plan_not_in_list(self, session, user_headers):
        tag = _uid()

        # Step 1: create a custom plan
        cr = session.post(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=user_headers,
            json={
                "plan_name": f"DelTest_{tag}",
                "description": "will be deleted",
                "duration_days": 7,
                "tasks": [{"task_name": "占位任务", "sort_order": 0}],
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200, cr.text
        plan_id = cr.json()["id"]

        # Step 2: delete the plan
        dr = session.delete(
            f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert dr.status_code == 200, dr.text

        # Step 3: list user plans and ensure the deleted one is absent
        lr = session.get(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert lr.status_code == 200
        items = lr.json().get("items", [])
        returned_ids = [p["id"] for p in items]
        assert plan_id not in returned_ids, (
            f"Deleted plan {plan_id} still present in user-plans list"
        )

    def test_deleted_plan_not_in_paginated_list(self, session, user_headers):
        """Walk through all pages to confirm the deleted plan is gone."""
        tag = _uid()

        cr = session.post(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=user_headers,
            json={
                "plan_name": f"PageDel_{tag}",
                "description": "pagination check",
                "duration_days": 3,
                "tasks": [{"task_name": "t1", "sort_order": 0}],
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200
        plan_id = cr.json()["id"]

        session.delete(
            f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )

        all_ids: list[int] = []
        page = 1
        while True:
            lr = session.get(
                f"{BASE_URL}/api/health-plan/user-plans",
                headers=user_headers,
                params={"page": page, "page_size": 50},
                timeout=TIMEOUT,
            )
            assert lr.status_code == 200
            items = lr.json().get("items", [])
            if not items:
                break
            all_ids.extend(p["id"] for p in items)
            page += 1
            if page > 20:
                break

        assert plan_id not in all_ids


# ══════════════════════════════════════════
#  Bug 3: 打卡详情接口
# ══════════════════════════════════════════


class TestCheckInItemDetail:
    """GET /api/health-plan/checkin-items/{item_id} returns item detail."""

    def test_checkin_item_detail(self, session, user_headers):
        tag = _uid()

        # Create a checkin item
        cr = session.post(
            f"{BASE_URL}/api/health-plan/checkin-items",
            headers=user_headers,
            json={
                "name": f"DetailCI_{tag}",
                "remind_times": ["08:00", "20:00"],
                "repeat_frequency": "daily",
                "target_value": 8000,
                "target_unit": "步",
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200, cr.text
        item_id = cr.json()["id"]

        # Get detail
        r = session.get(
            f"{BASE_URL}/api/health-plan/checkin-items/{item_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()

        assert data["id"] == item_id
        assert data["name"] == f"DetailCI_{tag}"
        assert "remind_times" in data
        assert "repeat_frequency" in data
        assert data["repeat_frequency"] == "daily"
        assert "status" in data
        assert "today_completed" in data

        # Cleanup
        session.delete(
            f"{BASE_URL}/api/health-plan/checkin-items/{item_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )

    def test_checkin_item_detail_fields(self, session, user_headers):
        """Ensure all expected fields are present in the response."""
        tag = _uid()
        cr = session.post(
            f"{BASE_URL}/api/health-plan/checkin-items",
            headers=user_headers,
            json={
                "name": f"FieldCI_{tag}",
                "repeat_frequency": "weekly",
                "target_value": 5,
                "target_unit": "杯",
                "remind_times": ["09:00"],
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200
        item_id = cr.json()["id"]

        r = session.get(
            f"{BASE_URL}/api/health-plan/checkin-items/{item_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()

        expected_fields = [
            "id", "user_id", "name", "target_value", "target_unit",
            "remind_times", "repeat_frequency", "status", "created_at",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        assert data["target_value"] == 5
        assert data["target_unit"] == "杯"

        # Cleanup
        session.delete(
            f"{BASE_URL}/api/health-plan/checkin-items/{item_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )

    def test_checkin_item_detail_not_found(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/checkin-items/999999",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_checkin_item_detail_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/health-plan/checkin-items/1",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401


# ══════════════════════════════════════════
#  Bug 4: 用药提醒详情接口
# ══════════════════════════════════════════


class TestMedicationDetail:
    """GET /api/health-plan/medications/{reminder_id} returns medication detail."""

    def test_medication_detail(self, session, user_headers):
        tag = _uid()

        # Create a medication reminder
        cr = session.post(
            f"{BASE_URL}/api/health-plan/medications",
            headers=user_headers,
            json={
                "medicine_name": f"DetailMed_{tag}",
                "dosage": "2片",
                "time_period": "早上",
                "remind_time": "07:30",
                "notes": "regression test",
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200, cr.text
        med_id = cr.json()["id"]

        # Get detail
        r = session.get(
            f"{BASE_URL}/api/health-plan/medications/{med_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()

        assert data["id"] == med_id
        assert data["medicine_name"] == f"DetailMed_{tag}"
        assert data["dosage"] == "2片"
        assert data["time_period"] == "早上"
        assert "today_checked" in data

        # Cleanup
        session.delete(
            f"{BASE_URL}/api/health-plan/medications/{med_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )

    def test_medication_detail_fields(self, session, user_headers):
        """Ensure all expected fields are present in the response."""
        tag = _uid()
        cr = session.post(
            f"{BASE_URL}/api/health-plan/medications",
            headers=user_headers,
            json={
                "medicine_name": f"FieldMed_{tag}",
                "dosage": "1粒",
                "time_period": "晚上",
                "remind_time": "21:00",
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200
        med_id = cr.json()["id"]

        r = session.get(
            f"{BASE_URL}/api/health-plan/medications/{med_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()

        expected_fields = [
            "id", "user_id", "medicine_name", "dosage", "time_period",
            "remind_time", "is_paused", "status", "created_at", "today_checked",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        assert data["is_paused"] is False
        assert data["status"] == "active"

        # Cleanup
        session.delete(
            f"{BASE_URL}/api/health-plan/medications/{med_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )

    def test_medication_detail_not_found(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/medications/999999",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_medication_detail_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/health-plan/medications/1",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401
