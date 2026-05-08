"""[Bug-419] 端到端冒烟：注册/登录 → 复现 H5 ai-home 早期 422 → 验证修复后 200 + 兜底。"""
import time
import requests

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
API = f"{BASE}/api"

phone = f"139{int(time.time()) % 100000000:08d}"
print(f"[smoke] using phone={phone}")

# 1. register
r = requests.post(
    f"{API}/auth/register",
    json={"phone": phone, "password": "TestPass123!", "nickname": "bug419smoke"},
    headers={"Client-Type": "h5-user"},
    timeout=20,
)
print(f"register: {r.status_code} {r.text[:200]}")
assert r.status_code in (200, 201), r.text

# 2. login
r = requests.post(
    f"{API}/auth/login",
    json={"phone": phone, "password": "TestPass123!"},
    headers={"Client-Type": "h5-user"},
    timeout=20,
)
print(f"login: {r.status_code} {r.text[:200]}")
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}

# 3. 复现历史 H5 ai-home 错误请求（缺 session_type + 错误字段名 member_id）
r = requests.post(
    f"{API}/chat/sessions",
    json={"member_id": None},
    headers=H,
    timeout=20,
)
print(f"\n[T1] ai-home 历史错误 payload (member_id=null,no session_type): {r.status_code}")
print(f"     body: {r.text[:300]}")
assert r.status_code == 200, f"修复后应自动兜底: {r.text}"

# 4. 完全空 payload
r = requests.post(f"{API}/chat/sessions", json={}, headers=H, timeout=20)
print(f"\n[T2] 完全空 payload: {r.status_code}")
print(f"     body: {r.text[:300]}")
assert r.status_code == 200, f"完全空 payload 应自动兜底: {r.text}"
session_data = r.json()
assert session_data.get("session_type") == "health_qa"

# 5. 标准 H5 调用（修复后字段）
r = requests.post(
    f"{API}/chat/sessions",
    json={"session_type": "health_qa"},
    headers=H,
    timeout=20,
)
print(f"\n[T3] 标准 health_qa: {r.status_code}")
assert r.status_code == 200

# 6. session_type 别名
r = requests.post(
    f"{API}/chat/sessions",
    json={"session_type": "general"},
    headers=H,
    timeout=20,
)
print(f"\n[T4] session_type='general' 别名归一化: {r.status_code}")
print(f"     resolved session_type = {r.json().get('session_type')}")
assert r.status_code == 200
assert r.json().get("session_type") == "health_qa"

# 7. 非法 family_member_id 类型（应 422 中文）
r = requests.post(
    f"{API}/chat/sessions",
    json={"session_type": "health_qa", "family_member_id": "not-a-number"},
    headers=H,
    timeout=20,
)
print(f"\n[T5] 非法 family_member_id 类型: {r.status_code}")
print(f"     body: {r.text[:300]}")
assert r.status_code == 422
assert "family_member_id" in r.text or "咨询对象" in r.text, "应中文化错误消息"

# 8. ai-home-config 200 校验（H5 首页配置接口未受影响）
r = requests.get(f"{API}/ai-home-config", headers=H, timeout=20)
print(f"\n[T6] /api/ai-home-config: {r.status_code}")
assert r.status_code == 200

print("\n所有 smoke 用例通过！")
