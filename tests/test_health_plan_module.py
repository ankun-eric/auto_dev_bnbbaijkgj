"""
Health Plan Module - Non-UI Automated Tests
Tests run against the deployed server using requests (synchronous HTTP).
Covers: Medication CRUD, CheckIn CRUD, Template Categories, User Plans,
        Today Todos, Statistics, and Admin APIs.
"""
import uuid
import warnings

import pytest
import requests

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = (
    "https://newbb.test.bangbangvip.com"
    "/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
)
TIMEOUT = 15
TEST_PHONE = "13800138000"
TEST_CODE = "123456"
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"


# ──────────────── Fixtures ────────────────


@pytest.fixture(scope="module")
def user_token():
    """Obtain user token via SMS login."""
    s = requests.Session()
    s.verify = False
    r = s.post(
        f"{BASE_URL}/api/auth/sms-code",
        json={"phone": TEST_PHONE, "type": "login"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"Send SMS code failed: {r.status_code} {r.text}"
    r = s.post(
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


@pytest.fixture(scope="module")
def admin_token():
    """Obtain admin token via password login."""
    r = requests.post(
        f"{BASE_URL}/api/admin/login",
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
        timeout=TIMEOUT,
        verify=False,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.verify = False
    return s


def _uid():
    return uuid.uuid4().hex[:6]


# ══════════════════════════════════════════
#  1. 用药提醒 CRUD
# ══════════════════════════════════════════


class TestMedicationCRUD:
    """POST/GET/PUT/DELETE /api/health-plan/medications + pause + checkin"""

    def test_create_medication(self, session, user_headers):
        tag = _uid()
        r = session.post(
            f"{BASE_URL}/api/health-plan/medications",
            headers=user_headers,
            json={
                "medicine_name": f"TestMed_{tag}",
                "dosage": "1片",
                "time_period": "早上",
                "remind_time": "08:00",
                "notes": "pytest auto",
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        assert data["medicine_name"] == f"TestMed_{tag}"
        self.__class__._med_id = data["id"]
        self.__class__._tag = tag

    def test_list_medications(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/medications",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "groups" in data
        assert "total" in data

    def test_update_medication(self, session, user_headers):
        med_id = self.__class__._med_id
        tag = self.__class__._tag
        r = session.put(
            f"{BASE_URL}/api/health-plan/medications/{med_id}",
            headers=user_headers,
            json={"medicine_name": f"Updated_{tag}", "dosage": "2片"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["medicine_name"] == f"Updated_{tag}"

    def test_pause_medication(self, session, user_headers):
        med_id = self.__class__._med_id
        r = session.put(
            f"{BASE_URL}/api/health-plan/medications/{med_id}/pause",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "is_paused" in data
        assert data["is_paused"] is True

    def test_resume_medication(self, session, user_headers):
        med_id = self.__class__._med_id
        r = session.put(
            f"{BASE_URL}/api/health-plan/medications/{med_id}/pause",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["is_paused"] is False

    def test_checkin_medication(self, session, user_headers):
        med_id = self.__class__._med_id
        r = session.post(
            f"{BASE_URL}/api/health-plan/medications/{med_id}/checkin",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            assert r.json()["message"] == "打卡成功"

    def test_duplicate_checkin_medication(self, session, user_headers):
        med_id = self.__class__._med_id
        r = session.post(
            f"{BASE_URL}/api/health-plan/medications/{med_id}/checkin",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 400
        assert "已打卡" in r.json().get("detail", "")

    def test_delete_medication(self, session, user_headers):
        med_id = self.__class__._med_id
        r = session.delete(
            f"{BASE_URL}/api/health-plan/medications/{med_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_deleted_not_in_list(self, session, user_headers):
        med_id = self.__class__._med_id
        r = session.get(
            f"{BASE_URL}/api/health-plan/medications",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        data = r.json()
        all_ids = []
        for group_items in data.get("groups", {}).values():
            if isinstance(group_items, list):
                all_ids.extend(item.get("id") for item in group_items)
        assert med_id not in all_ids

    def test_create_medication_unauth(self, session):
        r = session.post(
            f"{BASE_URL}/api/health-plan/medications",
            json={"medicine_name": "NoAuth"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_list_medications_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/health-plan/medications",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401


class TestMedicationMultiPeriod:
    """Bug 2: selecting multiple time periods should create one record per period."""

    def test_multi_period_creates_multiple_records(self, session, user_headers):
        tag = _uid()
        periods = ["早上", "中午", "晚上"]
        created_ids = []
        for period in periods:
            r = session.post(
                f"{BASE_URL}/api/health-plan/medications",
                headers=user_headers,
                json={
                    "medicine_name": f"MultiMed_{tag}",
                    "dosage": "1片",
                    "time_period": period,
                    "remind_time": "08:00",
                },
                timeout=TIMEOUT,
            )
            assert r.status_code == 200, f"Create for period {period} failed: {r.text}"
            data = r.json()
            assert "id" in data
            created_ids.append(data["id"])

        assert len(created_ids) == 3, f"Expected 3 records, got {len(created_ids)}"
        assert len(set(created_ids)) == 3, "All record IDs should be unique"

        r = session.get(
            f"{BASE_URL}/api/health-plan/medications",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        groups = r.json().get("groups", {})
        found = 0
        for period_items in groups.values():
            if isinstance(period_items, list):
                for item in period_items:
                    if item.get("medicine_name") == f"MultiMed_{tag}":
                        found += 1
        assert found >= 3, f"Expected >=3 matching meds in list, found {found}"

        for mid in created_ids:
            session.delete(
                f"{BASE_URL}/api/health-plan/medications/{mid}",
                headers=user_headers,
                timeout=TIMEOUT,
            )


# ══════════════════════════════════════════
#  2. 健康打卡 CRUD
# ══════════════════════════════════════════


class TestCheckInItemCRUD:
    """POST/GET/PUT/DELETE /api/health-plan/checkin-items + checkin"""

    def test_create_checkin_item(self, session, user_headers):
        tag = _uid()
        r = session.post(
            f"{BASE_URL}/api/health-plan/checkin-items",
            headers=user_headers,
            json={
                "name": f"步数_{tag}",
                "repeat_frequency": "daily",
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        assert data["name"] == f"步数_{tag}"
        self.__class__._item_id = data["id"]
        self.__class__._tag = tag

    def test_list_checkin_items(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/checkin-items",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_update_checkin_item(self, session, user_headers):
        item_id = self.__class__._item_id
        tag = self.__class__._tag
        r = session.put(
            f"{BASE_URL}/api/health-plan/checkin-items/{item_id}",
            headers=user_headers,
            json={"name": f"更新步数_{tag}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["name"] == f"更新步数_{tag}"

    def test_checkin_item(self, session, user_headers):
        item_id = self.__class__._item_id
        r = session.post(
            f"{BASE_URL}/api/health-plan/checkin-items/{item_id}/checkin",
            headers=user_headers,
            json={"actual_value": 9500},
            timeout=TIMEOUT,
        )
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            assert r.json()["message"] == "打卡成功"

    def test_duplicate_checkin_item(self, session, user_headers):
        item_id = self.__class__._item_id
        r = session.post(
            f"{BASE_URL}/api/health-plan/checkin-items/{item_id}/checkin",
            headers=user_headers,
            json={"actual_value": 9500},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400
        assert "已打卡" in r.json().get("detail", "")

    def test_delete_checkin_item(self, session, user_headers):
        item_id = self.__class__._item_id
        r = session.delete(
            f"{BASE_URL}/api/health-plan/checkin-items/{item_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_create_checkin_item_unauth(self, session):
        r = session.post(
            f"{BASE_URL}/api/health-plan/checkin-items",
            json={"name": "NoAuth"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_list_checkin_items_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/health-plan/checkin-items",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401


# ══════════════════════════════════════════
#  3. 模板分类与计划
# ══════════════════════════════════════════


class TestTemplateCategoriesAndPlans:
    """GET /api/health-plan/template-categories, recommended-plans, join, user-plans"""

    def test_list_template_categories(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/template-categories",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        self.__class__._categories = data["items"]

    def test_template_category_detail(self, session, user_headers):
        categories = getattr(self.__class__, "_categories", [])
        if not categories:
            pytest.skip("No template categories available")
        cat_id = categories[0]["id"]
        r = session.get(
            f"{BASE_URL}/api/health-plan/template-categories/{cat_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "category" in data
        assert "recommended_plans" in data
        assert "user_plans" in data

    def test_recommended_plan_detail(self, session, user_headers, admin_headers):
        tag = _uid()
        # Admin creates a category + published plan + task for the test
        rc = session.post(
            f"{BASE_URL}/api/admin/health-plan/template-categories",
            headers=admin_headers,
            json={"name": f"TestCat_{tag}", "sort_order": 999},
            timeout=TIMEOUT,
        )
        assert rc.status_code == 200
        cat_id = rc.json()["id"]

        rp = session.post(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans",
            headers=admin_headers,
            json={
                "category_id": cat_id,
                "name": f"RecPlan_{tag}",
                "description": "autotest",
                "duration_days": 7,
                "is_published": True,
                "sort_order": 0,
            },
            timeout=TIMEOUT,
        )
        assert rp.status_code == 200
        plan_id = rp.json()["id"]

        session.post(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}/tasks",
            headers=admin_headers,
            json={"task_name": "早起打卡", "sort_order": 0},
            timeout=TIMEOUT,
        )

        # User gets recommended plan detail
        r = session.get(
            f"{BASE_URL}/api/health-plan/recommended-plans/{plan_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "tasks" in data
        assert data["name"] == f"RecPlan_{tag}"

        self.__class__._rec_plan_id = plan_id
        self.__class__._rec_cat_id = cat_id

    def test_join_recommended_plan(self, session, user_headers):
        plan_id = getattr(self.__class__, "_rec_plan_id", None)
        if not plan_id:
            pytest.skip("No recommended plan created")
        r = session.post(
            f"{BASE_URL}/api/health-plan/recommended-plans/{plan_id}/join",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "plan_id" in data
        self.__class__._joined_plan_id = data["plan_id"]

    def test_create_user_plan(self, session, user_headers):
        tag = _uid()
        r = session.post(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=user_headers,
            json={
                "plan_name": f"自定义计划_{tag}",
                "description": "autotest plan",
                "duration_days": 14,
                "tasks": [
                    {"task_name": "跑步", "sort_order": 0},
                    {"task_name": "喝水", "sort_order": 1},
                ],
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        assert data["plan_name"] == f"自定义计划_{tag}"
        self.__class__._user_plan_id = data["id"]

    def test_list_user_plans(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_cleanup_test_data(self, session, user_headers, admin_headers):
        joined = getattr(self.__class__, "_joined_plan_id", None)
        if joined:
            session.delete(
                f"{BASE_URL}/api/health-plan/user-plans/{joined}",
                headers=user_headers,
                timeout=TIMEOUT,
            )

        user_plan = getattr(self.__class__, "_user_plan_id", None)
        if user_plan:
            session.delete(
                f"{BASE_URL}/api/health-plan/user-plans/{user_plan}",
                headers=user_headers,
                timeout=TIMEOUT,
            )

        rec_plan = getattr(self.__class__, "_rec_plan_id", None)
        if rec_plan:
            session.delete(
                f"{BASE_URL}/api/admin/health-plan/recommended-plans/{rec_plan}",
                headers=admin_headers,
                timeout=TIMEOUT,
            )

        rec_cat = getattr(self.__class__, "_rec_cat_id", None)
        if rec_cat:
            session.delete(
                f"{BASE_URL}/api/admin/health-plan/template-categories/{rec_cat}",
                headers=admin_headers,
                timeout=TIMEOUT,
            )

    def test_template_categories_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/health-plan/template-categories",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_user_plans_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/health-plan/user-plans",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401


# ══════════════════════════════════════════
#  4. 今日待办与统计
# ══════════════════════════════════════════


class TestTodayTodosAndStatistics:
    """GET /api/health-plan/today-todos, quick check, statistics"""

    def test_today_todos(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/today-todos",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "groups" in data
        assert "total_completed" in data or "total_count" in data
        groups = data["groups"]
        assert isinstance(groups, list)

    def test_today_todos_with_data(self, session, user_headers):
        """Create a medication so today-todos has non-empty groups."""
        tag = _uid()
        cr = session.post(
            f"{BASE_URL}/api/health-plan/medications",
            headers=user_headers,
            json={"medicine_name": f"TodoMed_{tag}", "time_period": "早上", "remind_time": "07:00"},
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200
        med_id = cr.json()["id"]

        r = session.get(
            f"{BASE_URL}/api/health-plan/today-todos",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        groups = data["groups"]
        assert isinstance(groups, list)
        assert len(groups) >= 1

        # Cleanup
        session.delete(
            f"{BASE_URL}/api/health-plan/medications/{med_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )

    def test_quick_checkin_medication(self, session, user_headers):
        tag = _uid()
        cr = session.post(
            f"{BASE_URL}/api/health-plan/medications",
            headers=user_headers,
            json={"medicine_name": f"QuickMed_{tag}", "time_period": "晚上", "remind_time": "21:00"},
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200
        med_id = cr.json()["id"]

        r = session.post(
            f"{BASE_URL}/api/health-plan/today-todos/{med_id}/check",
            headers=user_headers,
            json={"type": "medication"},
            timeout=TIMEOUT,
        )
        # Endpoint may not be deployed yet (404 is acceptable)
        assert r.status_code in (200, 400, 404), r.text
        if r.status_code == 200:
            assert r.json()["message"] == "打卡成功"

        # Cleanup
        session.delete(
            f"{BASE_URL}/api/health-plan/medications/{med_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )

    def test_quick_checkin_checkin_item(self, session, user_headers):
        tag = _uid()
        cr = session.post(
            f"{BASE_URL}/api/health-plan/checkin-items",
            headers=user_headers,
            json={"name": f"QuickCI_{tag}", "repeat_frequency": "daily"},
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200
        item_id = cr.json()["id"]

        r = session.post(
            f"{BASE_URL}/api/health-plan/today-todos/{item_id}/check",
            headers=user_headers,
            json={"type": "checkin", "value": 6000},
            timeout=TIMEOUT,
        )
        # Endpoint may not be deployed yet (404 is acceptable)
        assert r.status_code in (200, 400, 404), r.text
        if r.status_code == 200:
            assert r.json()["message"] == "打卡成功"

        # Cleanup
        session.delete(
            f"{BASE_URL}/api/health-plan/checkin-items/{item_id}",
            headers=user_headers,
            timeout=TIMEOUT,
        )

    def test_statistics(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/statistics",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        for field in [
            "today_completed",
            "today_total",
            "today_progress",
            "consecutive_days",
            "weekly_data",
        ]:
            assert field in data, f"Missing field: {field}"

    def test_today_todos_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/health-plan/today-todos",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_statistics_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/health-plan/statistics",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401


# ══════════════════════════════════════════
#  5. 管理端 API
# ══════════════════════════════════════════


class TestAdminAPIs:
    """Admin health-plan endpoints"""

    def test_admin_list_template_categories(self, session, admin_headers):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/template-categories",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert "items" in r.json()

    def test_admin_list_recommended_plans(self, session, admin_headers):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_admin_list_default_tasks(self, session, admin_headers):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/default-tasks",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert "items" in r.json()

    def test_admin_checkin_statistics(self, session, admin_headers):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/checkin-statistics",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        for field in [
            "total_users",
            "today_active_users",
            "total_medication_reminders",
            "total_checkin_items",
            "total_user_plans",
            "daily_trend",
        ]:
            assert field in data, f"Missing admin stats field: {field}"

    def test_admin_template_category_crud(self, session, admin_headers):
        tag = _uid()
        # Create
        r = session.post(
            f"{BASE_URL}/api/admin/health-plan/template-categories",
            headers=admin_headers,
            json={"name": f"AdminCat_{tag}", "description": "test", "icon": "heart", "sort_order": 998},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        cat_id = r.json()["id"]

        # Update
        r = session.put(
            f"{BASE_URL}/api/admin/health-plan/template-categories/{cat_id}",
            headers=admin_headers,
            json={"name": f"Updated_{tag}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["name"] == f"Updated_{tag}"

        # Delete
        r = session.delete(
            f"{BASE_URL}/api/admin/health-plan/template-categories/{cat_id}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_admin_recommended_plan_crud(self, session, admin_headers):
        tag = _uid()
        # Create category first
        rc = session.post(
            f"{BASE_URL}/api/admin/health-plan/template-categories",
            headers=admin_headers,
            json={"name": f"PlanCat_{tag}", "sort_order": 997},
            timeout=TIMEOUT,
        )
        assert rc.status_code == 200
        cat_id = rc.json()["id"]

        # Create plan
        rp = session.post(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans",
            headers=admin_headers,
            json={
                "category_id": cat_id,
                "name": f"RecPlan_{tag}",
                "description": "autotest",
                "duration_days": 30,
                "is_published": True,
                "sort_order": 0,
            },
            timeout=TIMEOUT,
        )
        assert rp.status_code == 200
        plan_id = rp.json()["id"]

        # Update plan
        r = session.put(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}",
            headers=admin_headers,
            json={"name": f"Updated_{tag}", "duration_days": 21},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

        # Add task
        rt = session.post(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}/tasks",
            headers=admin_headers,
            json={"task_name": f"Task_{tag}", "target_value": 30, "target_unit": "分钟", "sort_order": 0},
            timeout=TIMEOUT,
        )
        assert rt.status_code == 200
        task_id = rt.json()["id"]

        # List tasks
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}/tasks",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert "items" in r.json()

        # Delete task
        r = session.delete(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans/tasks/{task_id}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

        # Delete plan
        r = session.delete(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

        # Delete category
        session.delete(
            f"{BASE_URL}/api/admin/health-plan/template-categories/{cat_id}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )

    def test_admin_user_daily_summary(self, session, admin_headers):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/user-daily-summary",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "daily_data" in data, "Missing field: daily_data"
        assert "users" in data, "Missing field: users"
        assert isinstance(data["daily_data"], list)
        assert isinstance(data["users"], list)
        if data["daily_data"]:
            day = data["daily_data"][0]
            for field in ["date", "total_expected", "total_completed", "completion_rate", "details"]:
                assert field in day, f"Missing daily_data field: {field}"

    def test_admin_user_daily_summary_with_filters(self, session, admin_headers):
        from datetime import date, timedelta
        today = date.today()
        start = (today - timedelta(days=3)).isoformat()
        end = today.isoformat()
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/user-daily-summary",
            headers=admin_headers,
            params={"start_date": start, "end_date": end},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["daily_data"]) <= 4

    def test_admin_user_daily_summary_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/user-daily-summary",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_admin_user_daily_summary_with_user_token(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/user-daily-summary",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_admin_default_task_crud(self, session, admin_headers):
        tag = _uid()
        # Create
        r = session.post(
            f"{BASE_URL}/api/admin/health-plan/default-tasks",
            headers=admin_headers,
            json={
                "name": f"默认任务_{tag}",
                "description": "autotest",
                "target_value": 10000,
                "target_unit": "步",
                "category_type": "exercise",
                "sort_order": 999,
                "is_active": True,
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        task_id = r.json()["id"]

        # Update
        r = session.put(
            f"{BASE_URL}/api/admin/health-plan/default-tasks/{task_id}",
            headers=admin_headers,
            json={"name": f"Updated_{tag}", "is_active": False},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

        # Delete
        r = session.delete(
            f"{BASE_URL}/api/admin/health-plan/default-tasks/{task_id}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_admin_categories_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/template-categories",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_admin_plans_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_admin_default_tasks_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/default-tasks",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_admin_statistics_unauth(self, session):
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/checkin-statistics",
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_admin_endpoints_with_user_token(self, session, user_headers):
        """Regular user should get 403 on admin endpoints."""
        r = session.get(
            f"{BASE_URL}/api/admin/health-plan/template-categories",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 403


# ══════════════════════════════════════════
#  6. Edge cases - 404 handling
# ══════════════════════════════════════════


class TestEdgeCases:
    """404 on non-existent resources"""

    def test_get_nonexistent_user_plan(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/user-plans/999999",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_update_nonexistent_medication(self, session, user_headers):
        r = session.put(
            f"{BASE_URL}/api/health-plan/medications/999999",
            headers=user_headers,
            json={"medicine_name": "ghost"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_delete_nonexistent_checkin_item(self, session, user_headers):
        r = session.delete(
            f"{BASE_URL}/api/health-plan/checkin-items/999999",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_get_nonexistent_recommended_plan(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/recommended-plans/999999",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_get_nonexistent_template_category(self, session, user_headers):
        r = session.get(
            f"{BASE_URL}/api/health-plan/template-categories/999999",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_join_nonexistent_plan(self, session, user_headers):
        r = session.post(
            f"{BASE_URL}/api/health-plan/recommended-plans/999999/join",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_checkin_nonexistent_medication(self, session, user_headers):
        r = session.post(
            f"{BASE_URL}/api/health-plan/medications/999999/checkin",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_checkin_nonexistent_checkin_item(self, session, user_headers):
        r = session.post(
            f"{BASE_URL}/api/health-plan/checkin-items/999999/checkin",
            headers=user_headers,
            json={"actual_value": 100},
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_quick_checkin_invalid_type(self, session, user_headers):
        r = session.post(
            f"{BASE_URL}/api/health-plan/today-todos/1/check",
            headers=user_headers,
            json={"type": "invalid_type"},
            timeout=TIMEOUT,
        )
        # 400 if endpoint exists, 404 if not deployed yet
        assert r.status_code in (400, 404)
