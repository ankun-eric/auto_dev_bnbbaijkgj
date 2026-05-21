"""Non-UI automated test for PRD-MED-OPTIM-V2 deployment verification."""
import sys
sys.path.insert(0, '/app')

from app.api.medication_plans_v1 import _apply_consultant_filter
from sqlalchemy import select
from app.models.models import MedicationReminder

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1

print("=== PRD-MED-OPTIM-V2 Backend Tests ===")
print()

print("[Test 1] _apply_consultant_filter consistency")
stmt = select(MedicationReminder)
r_none = _apply_consultant_filter(stmt, None)
r_neg1 = _apply_consultant_filter(stmt, -1)
r_zero = _apply_consultant_filter(stmt, 0)
r_pos = _apply_consultant_filter(stmt, 5)

check("consultant_id=None returns unmodified stmt", str(r_none.compile()) == str(stmt.compile()))
check("consultant_id=-1 returns unmodified stmt", str(r_neg1.compile()) == str(stmt.compile()))
check("consultant_id=0 adds IS NULL filter", "NULL" in str(r_zero.compile()))
check("consultant_id=5 adds == filter", str(r_pos.compile()) != str(stmt.compile()))

print()
print("[Test 2] badge and today API use same _apply_consultant_filter")
from app.api.medication_reminder import badge
from app.api.medication_plans_v1 import reminder_today
import inspect
badge_src = inspect.getsource(badge)
today_src = inspect.getsource(reminder_today)
check("badge imports _list_today_active_reminders", "_list_today_active_reminders" in badge_src)
check("today uses _list_today_active_reminders", "_list_today_active_reminders" in today_src)

print()
print(f"=== Results: {passed} passed, {failed} failed ===")
if failed > 0:
    sys.exit(1)
print("ALL_TESTS_PASSED")
