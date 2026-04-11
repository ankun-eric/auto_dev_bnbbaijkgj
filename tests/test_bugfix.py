"""
Bug Fix Verification Tests — 3 Bugs
  Bug 1: today-todos custom group items should contain plan_name in extra
  Bug 2: CSS-only change (skipped)
  Bug 3: user-plans CRUD — create, get detail, update, delete
"""
import uuid
import warnings

import pytest
import requests

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = (
    "https://newbb.bangbangvip.com"
    "/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
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
    """Obtain user token via SMS login (test phone auto-returns code 123456)."""
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
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# ══════════════════════════════════════════
#  Bug 1: today-todos custom group items 包含 plan_name
# ══════════════════════════════════════════


class TestBug1TodayTodosPlanName:
    """Bug 1: 首页今日待办 - 健康计划不显示计划名称
    验证：custom 分组中每个 item.extra 包含 plan_name 字段。"""

    @pytest.fixture(autouse=True)
    def _create_test_plan(self, session, headers):
        """Create a plan with tasks so custom group is non-empty."""
        tag = _uid()
        self._plan_name = f"BugTest1_{tag}"
        r = session.post(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=headers,
            json={
                "plan_name": self._plan_name,
                "description": "bug1 verification",
                "duration_days": 7,
                "tasks": [
                    {"task_name": f"task_a_{tag}", "sort_order": 0},
                    {"task_name": f"task_b_{tag}", "sort_order": 1},
                ],
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Create plan failed: {r.text}"
        self._plan_id = r.json()["id"]
        yield
        session.delete(
            f"{BASE_URL}/api/health-plan/user-plans/{self._plan_id}",
            headers=headers,
            timeout=TIMEOUT,
        )

    def test_today_todos_returns_groups(self, session, headers):
        """today-todos endpoint should return 200 with groups list."""
        r = session.get(
            f"{BASE_URL}/api/health-plan/today-todos",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "groups" in data, f"Response missing 'groups': {data.keys()}"
        assert isinstance(data["groups"], list)

    def test_custom_group_exists(self, session, headers):
        """A group with group_type='custom' should be present."""
        r = session.get(
            f"{BASE_URL}/api/health-plan/today-todos",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        groups = r.json()["groups"]
        custom = [g for g in groups if g.get("group_type") == "custom"]
        assert len(custom) >= 1, (
            f"No 'custom' group found. Groups: {[g.get('group_type') for g in groups]}"
        )

    def test_custom_items_have_plan_name_in_extra(self, session, headers):
        """Each item in the custom group must have extra.plan_name set."""
        r = session.get(
            f"{BASE_URL}/api/health-plan/today-todos",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        groups = r.json()["groups"]
        custom = next((g for g in groups if g.get("group_type") == "custom"), None)
        assert custom is not None

        items = custom.get("items", [])
        assert len(items) > 0, "Custom group has no items"

        for item in items:
            extra = item.get("extra")
            assert extra is not None, f"Item {item.get('id')} missing 'extra' field"
            assert "plan_name" in extra, (
                f"Item {item.get('id')} extra missing 'plan_name': {extra}"
            )
            assert isinstance(extra["plan_name"], str) and len(extra["plan_name"]) > 0, (
                f"Item {item.get('id')} plan_name is empty or not a string: {extra['plan_name']}"
            )

    def test_our_plan_name_appears(self, session, headers):
        """The plan we created should have its name in the items."""
        r = session.get(
            f"{BASE_URL}/api/health-plan/today-todos",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        groups = r.json()["groups"]
        custom = next((g for g in groups if g.get("group_type") == "custom"), None)
        assert custom is not None

        plan_names_found = {
            item.get("extra", {}).get("plan_name")
            for item in custom.get("items", [])
            if item.get("extra")
        }
        assert self._plan_name in plan_names_found, (
            f"Our plan '{self._plan_name}' not found in items. Found: {plan_names_found}"
        )


# ══════════════════════════════════════════
#  Bug 2: CSS layout change — SKIPPED (no API to verify)
# ══════════════════════════════════════════


class TestBug2CheckinButtonLayout:
    """Bug 2: 健康打卡列表页 - 修改和删除按钮位置不合理
    This is a pure CSS/layout change. Cannot verify via API."""

    @pytest.mark.skip(reason="Pure frontend CSS change — cannot verify via API")
    def test_placeholder(self):
        pass


# ══════════════════════════════════════════
#  Bug 3: user-plans CRUD (edit page loads data)
# ══════════════════════════════════════════


class TestBug3UserPlanCRUD:
    """Bug 3: 自定义计划编辑页 - 内容为空
    验证：create → get detail → update → verify update → delete"""

    def test_full_crud_lifecycle(self, session, headers):
        tag = _uid()
        plan_name = f"CRUDTest_{tag}"
        updated_name = f"CRUDUpdated_{tag}"

        # Step 1: CREATE
        cr = session.post(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=headers,
            json={
                "plan_name": plan_name,
                "description": "CRUD test plan",
                "duration_days": 14,
                "tasks": [
                    {"task_name": "task_1", "sort_order": 0},
                    {"task_name": "task_2", "sort_order": 1},
                ],
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200, f"Create failed: {cr.text}"
        plan_data = cr.json()
        plan_id = plan_data["id"]
        assert plan_data["plan_name"] == plan_name
        assert "tasks" in plan_data
        assert len(plan_data["tasks"]) == 2

        try:
            # Step 2: GET DETAIL
            gr = session.get(
                f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
                headers=headers,
                timeout=TIMEOUT,
            )
            assert gr.status_code == 200, f"Get detail failed: {gr.text}"
            detail = gr.json()
            assert detail["id"] == plan_id
            assert detail["plan_name"] == plan_name
            assert detail["description"] == "CRUD test plan"
            assert detail["duration_days"] == 14
            assert "tasks" in detail
            assert len(detail["tasks"]) == 2

            # Step 3: UPDATE
            ur = session.put(
                f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
                headers=headers,
                json={
                    "plan_name": updated_name,
                    "description": "Updated description",
                },
                timeout=TIMEOUT,
            )
            assert ur.status_code == 200, f"Update failed: {ur.text}"
            updated = ur.json()
            assert updated["plan_name"] == updated_name
            assert updated["description"] == "Updated description"

            # Step 4: GET DETAIL AGAIN to confirm update persisted
            gr2 = session.get(
                f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
                headers=headers,
                timeout=TIMEOUT,
            )
            assert gr2.status_code == 200
            detail2 = gr2.json()
            assert detail2["plan_name"] == updated_name, (
                f"Plan name not updated: expected '{updated_name}', got '{detail2['plan_name']}'"
            )
            assert detail2["description"] == "Updated description"

        finally:
            # Step 5: DELETE (cleanup)
            dr = session.delete(
                f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
                headers=headers,
                timeout=TIMEOUT,
            )
            assert dr.status_code == 200, f"Delete failed: {dr.text}"

    def test_get_detail_returns_tasks(self, session, headers):
        """Detail endpoint must return task list with correct fields."""
        tag = _uid()
        cr = session.post(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=headers,
            json={
                "plan_name": f"TaskDetail_{tag}",
                "description": "task field check",
                "duration_days": 7,
                "tasks": [
                    {"task_name": "morning_run", "sort_order": 0, "target_value": 5, "target_unit": "km"},
                ],
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200
        plan_id = cr.json()["id"]

        try:
            gr = session.get(
                f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
                headers=headers,
                timeout=TIMEOUT,
            )
            assert gr.status_code == 200
            detail = gr.json()
            assert len(detail["tasks"]) == 1
            task = detail["tasks"][0]
            assert task["task_name"] == "morning_run"
            assert "id" in task
            assert "sort_order" in task
        finally:
            session.delete(
                f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
                headers=headers,
                timeout=TIMEOUT,
            )

    def test_get_nonexistent_plan_returns_404(self, session, headers):
        """Requesting a non-existent plan should return 404."""
        r = session.get(
            f"{BASE_URL}/api/health-plan/user-plans/999999",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_delete_plan_removes_from_list(self, session, headers):
        """After deletion, the plan must not appear in the list endpoint."""
        tag = _uid()
        cr = session.post(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=headers,
            json={
                "plan_name": f"DeleteCheck_{tag}",
                "description": "delete check",
                "duration_days": 3,
                "tasks": [{"task_name": "t1", "sort_order": 0}],
            },
            timeout=TIMEOUT,
        )
        assert cr.status_code == 200
        plan_id = cr.json()["id"]

        dr = session.delete(
            f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert dr.status_code == 200

        lr = session.get(
            f"{BASE_URL}/api/health-plan/user-plans",
            headers=headers,
            timeout=TIMEOUT,
        )
        assert lr.status_code == 200
        ids = [p["id"] for p in lr.json().get("items", [])]
        assert plan_id not in ids, f"Deleted plan {plan_id} still in list"
