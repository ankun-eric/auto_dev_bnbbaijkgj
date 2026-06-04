"""端到端验证：注册用户 → 创建计划 → 打卡 → 查总览 / 月历 / 汇总 / 补卡"""
import requests, json, time, random
BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

phone = f"139{random.randint(10000000, 99999999)}"
password = "User@2026"
print(f"[*] register {phone}")
r = requests.post(f"{BASE}/api/auth/register", json={"phone":phone,"password":password,"nickname":"E2E打卡"}, timeout=20)
print(" register:", r.status_code, r.text[:200])

r = requests.post(f"{BASE}/api/auth/login", json={"phone":phone,"password":password}, timeout=20)
print(" login:", r.status_code, r.text[:200])
tok = r.json().get("access_token") or r.json().get("token")
assert tok, f"no token: {r.text}"
H = {"Authorization": f"Bearer {tok}", "Client-Type":"h5-user"}

from datetime import date, timedelta
today = date.today().isoformat()

print("\n[1] create daily plan")
r = requests.post(f"{BASE}/api/health-plan/checkin-items", json={
    "name":"每天喝8杯水（E2E）","repeat_frequency":"daily","start_date":today
}, headers=H, timeout=20)
print(" ", r.status_code, r.text[:300])
item_id = r.json()["id"]

print("\n[2] create weekly plan (3 times/week)")
r = requests.post(f"{BASE}/api/health-plan/checkin-items", json={
    "name":"每周锻炼3次","repeat_frequency":"weekly","weekly_target_count":3,"start_date":today
}, headers=H, timeout=20)
print(" ", r.status_code, r.text[:300])

print("\n[3] today checkin")
r = requests.post(f"{BASE}/api/health-plan/checkin-items/{item_id}/checkin", json={}, headers=H, timeout=20)
print(" ", r.status_code, r.text[:200])

print("\n[4] overview")
r = requests.get(f"{BASE}/api/health-plan/checkin-overview", headers=H, timeout=20)
print(" ", r.status_code, r.text[:300])

print("\n[5] calendar")
r = requests.get(f"{BASE}/api/health-plan/checkin-calendar?year={date.today().year}&month={date.today().month}", headers=H, timeout=20)
print(" ", r.status_code, r.text[:400])

print("\n[6] stats-summary")
r = requests.get(f"{BASE}/api/health-plan/checkin-stats-summary", headers=H, timeout=20)
print(" ", r.status_code, r.text[:400])

print("\n[7] makeup yesterday")
y = (date.today() - timedelta(days=1)).isoformat()
r = requests.post(f"{BASE}/api/health-plan/checkin-items/{item_id}/makeup", json={"date":y}, headers=H, timeout=20)
print(" ", r.status_code, r.text[:300])

print("\n[8] makeup 4 days ago (should fail)")
old = (date.today() - timedelta(days=4)).isoformat()
r = requests.post(f"{BASE}/api/health-plan/checkin-items/{item_id}/makeup", json={"date":old}, headers=H, timeout=20)
print(" ", r.status_code, r.text[:300])

print("\n[9] list items")
r = requests.get(f"{BASE}/api/health-plan/checkin-items", headers=H, timeout=20)
print(" ", r.status_code, "items_count=", len(r.json().get("items",[])))

print("\n[10] delete item -> cascade records")
r = requests.delete(f"{BASE}/api/health-plan/checkin-items/{item_id}", headers=H, timeout=20)
print(" ", r.status_code, r.text[:200])

print("\n[OK] e2e done.")
