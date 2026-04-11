"""
Non-UI automated tests for Health Plan V2 module.
Runs against the deployed server at the configured BASE_URL.
"""
import sys
import time
import uuid

import requests

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
TIMEOUT = 15

PASS = 0
FAIL = 0
results = []


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        results.append(f"  PASS  {name}")
    else:
        FAIL += 1
        results.append(f"  FAIL  {name}" + (f" | {detail}" if detail else ""))


def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return {}


# ─── Auth helpers ───


def get_admin_token():
    resp = requests.post(
        f"{BASE_URL}/api/admin/login",
        json={"phone": "13800000000", "password": "admin123"},
        timeout=TIMEOUT,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token", "")
    return ""


def get_user_token():
    resp = requests.post(
        f"{BASE_URL}/api/auth/sms-code",
        json={"phone": "13800138000"},
        timeout=TIMEOUT,
    )
    resp = requests.post(
        f"{BASE_URL}/api/auth/sms-login",
        json={"phone": "13800138000", "code": "123456"},
        timeout=TIMEOUT,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token", "")
    return ""


# ─── 1. Medication Reminder CRUD + Check-in ───


def test_medication_crud():
    print("\n[1] Medication Reminder CRUD + Check-in")
    token = get_user_token()
    check("User token obtained", bool(token), "empty token")
    if not token:
        return
    h = {"Authorization": f"Bearer {token}"}
    uid = uuid.uuid4().hex[:6]

    # Create
    resp = requests.post(
        f"{BASE_URL}/api/health-plan/medications",
        headers=h,
        json={
            "medicine_name": f"TestMed_{uid}",
            "dosage": "1片",
            "time_period": "早上",
            "remind_time": "08:00",
            "notes": "autotest",
        },
        timeout=TIMEOUT,
    )
    check("POST /medications returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")
    data = safe_json(resp)
    med_id = data.get("id")
    check("Created medication has id", med_id is not None, str(data))

    if not med_id:
        return

    # List
    resp = requests.get(f"{BASE_URL}/api/health-plan/medications", headers=h, timeout=TIMEOUT)
    check("GET /medications returns 200", resp.status_code == 200, f"got {resp.status_code}")
    list_data = safe_json(resp)
    check("List response has groups", "groups" in list_data, str(list_data.keys()))

    # Update
    resp = requests.put(
        f"{BASE_URL}/api/health-plan/medications/{med_id}",
        headers=h,
        json={"medicine_name": f"UpdatedMed_{uid}", "dosage": "2片"},
        timeout=TIMEOUT,
    )
    check("PUT /medications/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")
    updated = safe_json(resp)
    check("Medicine name updated", updated.get("medicine_name") == f"UpdatedMed_{uid}", str(updated.get("medicine_name")))

    # Pause/Resume
    resp = requests.put(f"{BASE_URL}/api/health-plan/medications/{med_id}/pause", headers=h, timeout=TIMEOUT)
    check("PUT /medications/{id}/pause returns 200", resp.status_code == 200, f"got {resp.status_code}")
    pause_data = safe_json(resp)
    check("Pause response has is_paused", "is_paused" in pause_data, str(pause_data))

    # Resume (toggle back)
    resp = requests.put(f"{BASE_URL}/api/health-plan/medications/{med_id}/pause", headers=h, timeout=TIMEOUT)
    check("Toggle resume returns 200", resp.status_code == 200, f"got {resp.status_code}")

    # Check-in
    resp = requests.post(f"{BASE_URL}/api/health-plan/medications/{med_id}/checkin", headers=h, timeout=TIMEOUT)
    check("POST /medications/{id}/checkin returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")

    # Duplicate check-in should fail
    resp = requests.post(f"{BASE_URL}/api/health-plan/medications/{med_id}/checkin", headers=h, timeout=TIMEOUT)
    check("Duplicate checkin returns 400", resp.status_code == 400, f"got {resp.status_code}")

    # Delete
    resp = requests.delete(f"{BASE_URL}/api/health-plan/medications/{med_id}", headers=h, timeout=TIMEOUT)
    check("DELETE /medications/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}")

    # Verify deleted (should not appear in list)
    resp = requests.get(f"{BASE_URL}/api/health-plan/medications", headers=h, timeout=TIMEOUT)
    list_after = safe_json(resp)
    all_ids = []
    for group_items in list_after.get("groups", {}).values():
        if isinstance(group_items, list):
            for item in group_items:
                all_ids.append(item.get("id"))
    check("Deleted medication not in list", med_id not in all_ids)


# ─── 2. Health Check-in Item CRUD + Check-in ───


def test_checkin_item_crud():
    print("\n[2] Health Check-in Item CRUD + Check-in")
    token = get_user_token()
    if not token:
        print("  SKIP (no token)")
        return
    h = {"Authorization": f"Bearer {token}"}
    uid = uuid.uuid4().hex[:6]

    # Create
    resp = requests.post(
        f"{BASE_URL}/api/health-plan/checkin-items",
        headers=h,
        json={
            "name": f"步数_{uid}",
            "target_value": 8000,
            "target_unit": "步",
            "repeat_frequency": "daily",
        },
        timeout=TIMEOUT,
    )
    check("POST /checkin-items returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")
    data = safe_json(resp)
    item_id = data.get("id")
    check("Created checkin item has id", item_id is not None, str(data))

    if not item_id:
        return

    # List
    resp = requests.get(f"{BASE_URL}/api/health-plan/checkin-items", headers=h, timeout=TIMEOUT)
    check("GET /checkin-items returns 200", resp.status_code == 200, f"got {resp.status_code}")
    list_data = safe_json(resp)
    check("List has items field", "items" in list_data, str(list_data.keys()))

    # Update
    resp = requests.put(
        f"{BASE_URL}/api/health-plan/checkin-items/{item_id}",
        headers=h,
        json={"name": f"更新步数_{uid}", "target_value": 10000},
        timeout=TIMEOUT,
    )
    check("PUT /checkin-items/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")
    updated = safe_json(resp)
    check("Item name updated", updated.get("name") == f"更新步数_{uid}", str(updated.get("name")))

    # Check-in
    resp = requests.post(
        f"{BASE_URL}/api/health-plan/checkin-items/{item_id}/checkin",
        headers=h,
        json={"actual_value": 9500},
        timeout=TIMEOUT,
    )
    check("POST /checkin-items/{id}/checkin returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")

    # Duplicate check-in
    resp = requests.post(
        f"{BASE_URL}/api/health-plan/checkin-items/{item_id}/checkin",
        headers=h,
        json={"actual_value": 9500},
        timeout=TIMEOUT,
    )
    check("Duplicate checkin returns 400", resp.status_code == 400, f"got {resp.status_code}")

    # Delete
    resp = requests.delete(f"{BASE_URL}/api/health-plan/checkin-items/{item_id}", headers=h, timeout=TIMEOUT)
    check("DELETE /checkin-items/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}")


# ─── 3. Template Categories ───


def test_template_categories():
    print("\n[3] Template Categories")
    token = get_user_token()
    if not token:
        print("  SKIP (no token)")
        return
    h = {"Authorization": f"Bearer {token}"}

    resp = requests.get(f"{BASE_URL}/api/health-plan/template-categories", headers=h, timeout=TIMEOUT)
    check("GET /template-categories returns 200", resp.status_code == 200, f"got {resp.status_code}")
    data = safe_json(resp)
    check("Response has items", "items" in data, str(data.keys()))

    items = data.get("items", [])
    if items:
        cat_id = items[0]["id"]
        resp = requests.get(f"{BASE_URL}/api/health-plan/template-categories/{cat_id}", headers=h, timeout=TIMEOUT)
        check("GET /template-categories/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}")
        detail = safe_json(resp)
        check("Detail has category field", "category" in detail, str(detail.keys()))
        check("Detail has recommended_plans", "recommended_plans" in detail, str(detail.keys()))
    else:
        check("Template categories exist (need admin seed)", False, "no categories found")


# ─── 4. User Plan CRUD ───


def test_user_plan_crud():
    print("\n[4] User Plan CRUD")
    token = get_user_token()
    if not token:
        print("  SKIP (no token)")
        return
    h = {"Authorization": f"Bearer {token}"}
    uid = uuid.uuid4().hex[:6]

    # Create
    resp = requests.post(
        f"{BASE_URL}/api/health-plan/user-plans",
        headers=h,
        json={
            "plan_name": f"自定义计划_{uid}",
            "description": "autotest plan",
            "duration_days": 14,
            "tasks": [
                {"task_name": "跑步", "target_value": 5, "target_unit": "公里", "sort_order": 0},
                {"task_name": "喝水", "target_value": 2000, "target_unit": "ml", "sort_order": 1},
            ],
        },
        timeout=TIMEOUT,
    )
    check("POST /user-plans returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")
    data = safe_json(resp)
    plan_id = data.get("id")
    check("Created plan has id", plan_id is not None, str(data))

    if not plan_id:
        return

    # List
    resp = requests.get(f"{BASE_URL}/api/health-plan/user-plans", headers=h, timeout=TIMEOUT)
    check("GET /user-plans returns 200", resp.status_code == 200, f"got {resp.status_code}")
    list_data = safe_json(resp)
    check("List has items", "items" in list_data, str(list_data.keys()))

    # Detail
    resp = requests.get(f"{BASE_URL}/api/health-plan/user-plans/{plan_id}", headers=h, timeout=TIMEOUT)
    check("GET /user-plans/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}")
    detail = safe_json(resp)
    check("Detail has tasks", "tasks" in detail, str(detail.keys()))
    tasks = detail.get("tasks", [])
    check("Plan has 2 tasks", len(tasks) == 2, f"got {len(tasks)}")

    # Task check-in
    if tasks:
        task_id = tasks[0]["id"]
        resp = requests.post(
            f"{BASE_URL}/api/health-plan/user-plans/{plan_id}/tasks/{task_id}/checkin",
            headers=h,
            json={"actual_value": 6.5},
            timeout=TIMEOUT,
        )
        check("POST /user-plans/{id}/tasks/{tid}/checkin returns 200", resp.status_code == 200,
              f"got {resp.status_code}: {resp.text[:200]}")

        # Duplicate
        resp = requests.post(
            f"{BASE_URL}/api/health-plan/user-plans/{plan_id}/tasks/{task_id}/checkin",
            headers=h,
            json={"actual_value": 6.5},
            timeout=TIMEOUT,
        )
        check("Duplicate task checkin returns 400", resp.status_code == 400, f"got {resp.status_code}")

    # Update plan
    resp = requests.put(
        f"{BASE_URL}/api/health-plan/user-plans/{plan_id}",
        headers=h,
        json={"plan_name": f"更新计划_{uid}", "duration_days": 21},
        timeout=TIMEOUT,
    )
    check("PUT /user-plans/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")

    # Delete plan
    resp = requests.delete(f"{BASE_URL}/api/health-plan/user-plans/{plan_id}", headers=h, timeout=TIMEOUT)
    check("DELETE /user-plans/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}")


# ─── 5. Today Todos ───


def test_today_todos():
    print("\n[5] Today Todos")
    token = get_user_token()
    if not token:
        print("  SKIP (no token)")
        return
    h = {"Authorization": f"Bearer {token}"}

    resp = requests.get(f"{BASE_URL}/api/health-plan/today-todos", headers=h, timeout=TIMEOUT)
    check("GET /today-todos returns 200", resp.status_code == 200, f"got {resp.status_code}")
    data = safe_json(resp)
    check("Response has groups", "groups" in data, str(data.keys()))
    check("Response has total_completed", "total_completed" in data, str(data.keys()))
    check("Response has total_count", "total_count" in data, str(data.keys()))


# ─── 6. Statistics ───


def test_statistics():
    print("\n[6] Check-in Statistics")
    token = get_user_token()
    if not token:
        print("  SKIP (no token)")
        return
    h = {"Authorization": f"Bearer {token}"}

    resp = requests.get(f"{BASE_URL}/api/health-plan/statistics", headers=h, timeout=TIMEOUT)
    check("GET /statistics returns 200", resp.status_code == 200, f"got {resp.status_code}")
    data = safe_json(resp)
    for field in ["today_completed", "today_total", "today_progress", "consecutive_days", "weekly_data"]:
        check(f"Statistics has '{field}'", field in data, str(data.keys()))


# ─── 7. Admin: Template Category CRUD ───


def test_admin_template_category_crud():
    print("\n[7] Admin Template Category CRUD")
    token = get_admin_token()
    check("Admin token obtained", bool(token), "empty token")
    if not token:
        return
    h = {"Authorization": f"Bearer {token}"}
    uid = uuid.uuid4().hex[:6]

    # List
    resp = requests.get(f"{BASE_URL}/api/admin/health-plan/template-categories", headers=h, timeout=TIMEOUT)
    check("GET admin /template-categories returns 200", resp.status_code == 200, f"got {resp.status_code}")

    # Create
    resp = requests.post(
        f"{BASE_URL}/api/admin/health-plan/template-categories",
        headers=h,
        json={
            "name": f"测试分类_{uid}",
            "description": "autotest category",
            "icon": "heart",
            "sort_order": 999,
        },
        timeout=TIMEOUT,
    )
    check("POST admin /template-categories returns 200", resp.status_code == 200,
          f"got {resp.status_code}: {resp.text[:200]}")
    data = safe_json(resp)
    cat_id = data.get("id")
    check("Created category has id", cat_id is not None, str(data))

    if not cat_id:
        return

    # Update
    resp = requests.put(
        f"{BASE_URL}/api/admin/health-plan/template-categories/{cat_id}",
        headers=h,
        json={"name": f"更新分类_{uid}", "description": "updated"},
        timeout=TIMEOUT,
    )
    check("PUT admin /template-categories/{id} returns 200", resp.status_code == 200,
          f"got {resp.status_code}: {resp.text[:200]}")

    # Delete
    resp = requests.delete(
        f"{BASE_URL}/api/admin/health-plan/template-categories/{cat_id}",
        headers=h,
        timeout=TIMEOUT,
    )
    check("DELETE admin /template-categories/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}")

    return cat_id


# ─── 8. Admin: Recommended Plan CRUD ───


def test_admin_recommended_plan_crud():
    print("\n[8] Admin Recommended Plan CRUD")
    token = get_admin_token()
    if not token:
        print("  SKIP (no admin token)")
        return
    h = {"Authorization": f"Bearer {token}"}
    uid = uuid.uuid4().hex[:6]

    # First create a category to attach the plan to
    resp = requests.post(
        f"{BASE_URL}/api/admin/health-plan/template-categories",
        headers=h,
        json={"name": f"PlanCat_{uid}", "sort_order": 998},
        timeout=TIMEOUT,
    )
    cat_data = safe_json(resp)
    cat_id = cat_data.get("id")
    if not cat_id:
        check("Need category for recommended plan test", False, "could not create category")
        return

    # List
    resp = requests.get(f"{BASE_URL}/api/admin/health-plan/recommended-plans", headers=h, timeout=TIMEOUT)
    check("GET admin /recommended-plans returns 200", resp.status_code == 200, f"got {resp.status_code}")

    # Create
    resp = requests.post(
        f"{BASE_URL}/api/admin/health-plan/recommended-plans",
        headers=h,
        json={
            "category_id": cat_id,
            "name": f"推荐计划_{uid}",
            "description": "autotest recommended plan",
            "target_audience": "测试人群",
            "duration_days": 30,
            "is_published": True,
            "sort_order": 0,
        },
        timeout=TIMEOUT,
    )
    check("POST admin /recommended-plans returns 200", resp.status_code == 200,
          f"got {resp.status_code}: {resp.text[:200]}")
    data = safe_json(resp)
    plan_id = data.get("id")
    check("Created recommended plan has id", plan_id is not None, str(data))

    if not plan_id:
        # Cleanup category
        requests.delete(f"{BASE_URL}/api/admin/health-plan/template-categories/{cat_id}", headers=h, timeout=TIMEOUT)
        return

    # Update
    resp = requests.put(
        f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}",
        headers=h,
        json={"name": f"更新推荐_{uid}", "duration_days": 21},
        timeout=TIMEOUT,
    )
    check("PUT admin /recommended-plans/{id} returns 200", resp.status_code == 200,
          f"got {resp.status_code}: {resp.text[:200]}")

    # Toggle publish
    resp = requests.put(
        f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}/publish",
        headers=h,
        timeout=TIMEOUT,
    )
    check("PUT admin /recommended-plans/{id}/publish returns 200", resp.status_code == 200,
          f"got {resp.status_code}")
    pub_data = safe_json(resp)
    check("Publish toggle has is_published", "is_published" in pub_data, str(pub_data))

    # Add task to plan
    resp = requests.post(
        f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}/tasks",
        headers=h,
        json={"task_name": f"任务A_{uid}", "target_value": 30, "target_unit": "分钟", "sort_order": 0},
        timeout=TIMEOUT,
    )
    check("POST admin plan task returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")
    task_data = safe_json(resp)
    task_id = task_data.get("id")

    # List tasks
    resp = requests.get(
        f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}/tasks",
        headers=h,
        timeout=TIMEOUT,
    )
    check("GET admin plan tasks returns 200", resp.status_code == 200, f"got {resp.status_code}")
    tasks_list = safe_json(resp)
    check("Tasks list has items", "items" in tasks_list, str(tasks_list.keys()))

    # Update task
    if task_id:
        resp = requests.put(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans/tasks/{task_id}",
            headers=h,
            json={"task_name": f"更新任务A_{uid}", "target_value": 45},
            timeout=TIMEOUT,
        )
        check("PUT admin plan task returns 200", resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}")

        # Delete task
        resp = requests.delete(
            f"{BASE_URL}/api/admin/health-plan/recommended-plans/tasks/{task_id}",
            headers=h,
            timeout=TIMEOUT,
        )
        check("DELETE admin plan task returns 200", resp.status_code == 200, f"got {resp.status_code}")

    # Delete plan
    resp = requests.delete(
        f"{BASE_URL}/api/admin/health-plan/recommended-plans/{plan_id}",
        headers=h,
        timeout=TIMEOUT,
    )
    check("DELETE admin /recommended-plans/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}")

    # Cleanup category
    requests.delete(f"{BASE_URL}/api/admin/health-plan/template-categories/{cat_id}", headers=h, timeout=TIMEOUT)


# ─── 9. Admin: Default Health Task CRUD ───


def test_admin_default_task_crud():
    print("\n[9] Admin Default Health Task CRUD")
    token = get_admin_token()
    if not token:
        print("  SKIP (no admin token)")
        return
    h = {"Authorization": f"Bearer {token}"}
    uid = uuid.uuid4().hex[:6]

    # List
    resp = requests.get(f"{BASE_URL}/api/admin/health-plan/default-tasks", headers=h, timeout=TIMEOUT)
    check("GET admin /default-tasks returns 200", resp.status_code == 200, f"got {resp.status_code}")
    list_data = safe_json(resp)
    check("Default tasks has items", "items" in list_data, str(list_data.keys()))

    # Create
    resp = requests.post(
        f"{BASE_URL}/api/admin/health-plan/default-tasks",
        headers=h,
        json={
            "name": f"默认任务_{uid}",
            "description": "autotest default task",
            "target_value": 10000,
            "target_unit": "步",
            "category_type": "exercise",
            "sort_order": 999,
            "is_active": True,
        },
        timeout=TIMEOUT,
    )
    check("POST admin /default-tasks returns 200", resp.status_code == 200,
          f"got {resp.status_code}: {resp.text[:200]}")
    data = safe_json(resp)
    task_id = data.get("id")
    check("Created default task has id", task_id is not None, str(data))

    if not task_id:
        return

    # Update
    resp = requests.put(
        f"{BASE_URL}/api/admin/health-plan/default-tasks/{task_id}",
        headers=h,
        json={"name": f"更新默认任务_{uid}", "target_value": 15000, "is_active": False},
        timeout=TIMEOUT,
    )
    check("PUT admin /default-tasks/{id} returns 200", resp.status_code == 200,
          f"got {resp.status_code}: {resp.text[:200]}")

    # Delete
    resp = requests.delete(
        f"{BASE_URL}/api/admin/health-plan/default-tasks/{task_id}",
        headers=h,
        timeout=TIMEOUT,
    )
    check("DELETE admin /default-tasks/{id} returns 200", resp.status_code == 200, f"got {resp.status_code}")


# ─── 10. Admin: Check-in Statistics ───


def test_admin_checkin_statistics():
    print("\n[10] Admin Check-in Statistics")
    token = get_admin_token()
    if not token:
        print("  SKIP (no admin token)")
        return
    h = {"Authorization": f"Bearer {token}"}

    resp = requests.get(f"{BASE_URL}/api/admin/health-plan/checkin-statistics", headers=h, timeout=TIMEOUT)
    check("GET admin /checkin-statistics returns 200", resp.status_code == 200, f"got {resp.status_code}")
    data = safe_json(resp)
    for field in ["total_users", "today_active_users", "total_medication_reminders",
                   "total_checkin_items", "total_user_plans", "daily_trend"]:
        check(f"Admin stats has '{field}'", field in data, str(data.keys()))

    resp = requests.get(
        f"{BASE_URL}/api/admin/health-plan/user-checkin-details",
        headers=h,
        timeout=TIMEOUT,
    )
    check("GET admin /user-checkin-details returns 200", resp.status_code == 200, f"got {resp.status_code}")
    detail_data = safe_json(resp)
    check("Checkin details has items", "items" in detail_data, str(detail_data.keys()))


# ─── 11. User: Join Recommended Plan (E2E) ───


def test_join_recommended_plan():
    print("\n[11] Join Recommended Plan E2E")
    admin_token = get_admin_token()
    user_token_val = get_user_token()
    if not admin_token or not user_token_val:
        print("  SKIP (missing tokens)")
        return
    ah = {"Authorization": f"Bearer {admin_token}"}
    uh = {"Authorization": f"Bearer {user_token_val}"}
    uid = uuid.uuid4().hex[:6]

    # Admin: create category + plan + task
    resp = requests.post(
        f"{BASE_URL}/api/admin/health-plan/template-categories",
        headers=ah,
        json={"name": f"JoinCat_{uid}", "sort_order": 997},
        timeout=TIMEOUT,
    )
    cat_id = safe_json(resp).get("id")
    if not cat_id:
        check("Create category for join test", False, "failed")
        return

    resp = requests.post(
        f"{BASE_URL}/api/admin/health-plan/recommended-plans",
        headers=ah,
        json={
            "category_id": cat_id,
            "name": f"JoinPlan_{uid}",
            "description": "plan for join test",
            "duration_days": 7,
            "is_published": True,
            "sort_order": 0,
        },
        timeout=TIMEOUT,
    )
    rec_plan_id = safe_json(resp).get("id")
    if not rec_plan_id:
        check("Create recommended plan for join test", False, "failed")
        requests.delete(f"{BASE_URL}/api/admin/health-plan/template-categories/{cat_id}", headers=ah, timeout=TIMEOUT)
        return

    requests.post(
        f"{BASE_URL}/api/admin/health-plan/recommended-plans/{rec_plan_id}/tasks",
        headers=ah,
        json={"task_name": "早起打卡", "sort_order": 0},
        timeout=TIMEOUT,
    )
    requests.post(
        f"{BASE_URL}/api/admin/health-plan/recommended-plans/{rec_plan_id}/tasks",
        headers=ah,
        json={"task_name": "睡前冥想", "target_value": 10, "target_unit": "分钟", "sort_order": 1},
        timeout=TIMEOUT,
    )

    # User: get recommended plan detail
    resp = requests.get(
        f"{BASE_URL}/api/health-plan/recommended-plans/{rec_plan_id}",
        headers=uh,
        timeout=TIMEOUT,
    )
    check("GET /recommended-plans/{id} returns 200", resp.status_code == 200,
          f"got {resp.status_code}: {resp.text[:200]}")
    plan_detail = safe_json(resp)
    check("Recommended plan has tasks", "tasks" in plan_detail, str(plan_detail.keys()))

    # User: join plan
    resp = requests.post(
        f"{BASE_URL}/api/health-plan/recommended-plans/{rec_plan_id}/join",
        headers=uh,
        timeout=TIMEOUT,
    )
    check("POST /recommended-plans/{id}/join returns 200", resp.status_code == 200,
          f"got {resp.status_code}: {resp.text[:200]}")
    join_data = safe_json(resp)
    user_plan_id = join_data.get("plan_id")
    check("Join returns plan_id", user_plan_id is not None, str(join_data))

    if user_plan_id:
        # Verify user plan has tasks
        resp = requests.get(f"{BASE_URL}/api/health-plan/user-plans/{user_plan_id}", headers=uh, timeout=TIMEOUT)
        up_detail = safe_json(resp)
        check("Joined plan has tasks", len(up_detail.get("tasks", [])) == 2,
              f"got {len(up_detail.get('tasks', []))} tasks")

        # Cleanup user plan
        requests.delete(f"{BASE_URL}/api/health-plan/user-plans/{user_plan_id}", headers=uh, timeout=TIMEOUT)

    # Cleanup admin resources
    requests.delete(f"{BASE_URL}/api/admin/health-plan/recommended-plans/{rec_plan_id}", headers=ah, timeout=TIMEOUT)
    requests.delete(f"{BASE_URL}/api/admin/health-plan/template-categories/{cat_id}", headers=ah, timeout=TIMEOUT)


# ─── 12. Edge cases: 404 on non-existent resources ───


def test_edge_cases():
    print("\n[12] Edge Cases - 404 Handling")
    token = get_user_token()
    if not token:
        print("  SKIP (no token)")
        return
    h = {"Authorization": f"Bearer {token}"}

    resp = requests.get(f"{BASE_URL}/api/health-plan/user-plans/999999", headers=h, timeout=TIMEOUT)
    check("GET non-existent user plan returns 404", resp.status_code == 404, f"got {resp.status_code}")

    resp = requests.put(
        f"{BASE_URL}/api/health-plan/medications/999999",
        headers=h,
        json={"medicine_name": "test"},
        timeout=TIMEOUT,
    )
    check("PUT non-existent medication returns 404", resp.status_code == 404, f"got {resp.status_code}")

    resp = requests.delete(f"{BASE_URL}/api/health-plan/checkin-items/999999", headers=h, timeout=TIMEOUT)
    check("DELETE non-existent checkin item returns 404", resp.status_code == 404, f"got {resp.status_code}")

    resp = requests.get(f"{BASE_URL}/api/health-plan/recommended-plans/999999", headers=h, timeout=TIMEOUT)
    check("GET non-existent recommended plan returns 404", resp.status_code == 404, f"got {resp.status_code}")

    resp = requests.get(f"{BASE_URL}/api/health-plan/template-categories/999999", headers=h, timeout=TIMEOUT)
    check("GET non-existent template category returns 404", resp.status_code == 404, f"got {resp.status_code}")


# ─── 13. Unauthenticated access ───


def test_unauthenticated_access():
    print("\n[13] Unauthenticated Access")
    endpoints = [
        ("GET", f"{BASE_URL}/api/health-plan/medications"),
        ("GET", f"{BASE_URL}/api/health-plan/checkin-items"),
        ("GET", f"{BASE_URL}/api/health-plan/template-categories"),
        ("GET", f"{BASE_URL}/api/health-plan/user-plans"),
        ("GET", f"{BASE_URL}/api/health-plan/today-todos"),
        ("GET", f"{BASE_URL}/api/health-plan/statistics"),
    ]
    for method, url in endpoints:
        path = url.replace(BASE_URL, "")
        resp = requests.request(method, url, timeout=TIMEOUT)
        check(f"Unauth {method} {path} returns 401/403",
              resp.status_code in [401, 403, 422],
              f"got {resp.status_code}")


# ─── Main ───


if __name__ == "__main__":
    print("=" * 70)
    print("Health Plan V2 - Non-UI Automated Tests")
    print(f"Base URL: {BASE_URL}")
    print("=" * 70)

    test_medication_crud()
    test_checkin_item_crud()
    test_template_categories()
    test_user_plan_crud()
    test_today_todos()
    test_statistics()
    test_admin_template_category_crud()
    test_admin_recommended_plan_crud()
    test_admin_default_task_crud()
    test_admin_checkin_statistics()
    test_join_recommended_plan()
    test_edge_cases()
    test_unauthenticated_access()

    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    for r in results:
        print(r)
    total = PASS + FAIL
    print(f"\nTotal: {total} | PASS: {PASS} | FAIL: {FAIL}")

    if FAIL > 0:
        print("\n--- BUG LIST ---")
        for r in results:
            if r.strip().startswith("FAIL"):
                print(f"  BUG: {r.strip()}")

    sys.exit(0 if FAIL == 0 else 1)
