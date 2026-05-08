"""端到端 smoke：注册顾客 → 用 pc-web Header 调改期接口应该被拒；用 h5-user 应该走到业务层。"""
import requests, json, random, string

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def rnd(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def post(path, body, headers=None):
    r = requests.post(f"{BASE}{path}", json=body, headers=headers, timeout=15)
    print(f"POST {path} [{r.status_code}] {r.text[:200]}")
    return r


# 1. 注册（user-side）
phone = "139" + "".join(random.choices(string.digits, k=8))
pwd = "Test1234!"
r = post("/api/auth/register", {"phone": phone, "password": pwd, "name": "smoke367"})
if r.status_code not in (200, 201):
    print("register failed, abort")
    raise SystemExit(1)

# 2. 登录
r = post("/api/auth/login", {"phone": phone, "password": pwd})
token = r.json().get("access_token") or r.json().get("token") or r.json().get("data", {}).get("access_token")
print(f"token = {token[:30]}...")
auth = {"Authorization": f"Bearer {token}"}

# 3. 用 pc-web 调改期 → 应该 403 客户端家族错误
print("\n=== 商家端 Client-Type 调顾客接口 → 期望 403 客户端拦截 ===")
r = post(
    "/api/orders/unified/999999/appointment",
    {"appointment_date": "2026-06-01", "appointment_time": "10:00"},
    {**auth, "Client-Type": "pc-web"},
)
assert r.status_code == 403, f"应 403 但收到 {r.status_code}"
assert "客户端" in r.text or "顾客" in r.text, f"应包含客户端家族错误文案，实际：{r.text}"
print("  -> pc-web 被正确拦截 ✓")

body = {"appointment_date": "2026-06-01", "appointment_time": "2026-06-01T10:00:00"}

# 4. 用 h5-user 调改期 → 通过 client-type 校验，进入业务层（404 订单不存在）
print("\n=== 顾客端 Client-Type 调顾客接口 → 期望放行到业务层（404） ===")
r = post("/api/orders/unified/999999/appointment", body, {**auth, "Client-Type": "h5-user"})
assert r.status_code in (404, 400), f"h5-user 应放行（期 404/400），实际 {r.status_code}"
assert "客户端" not in r.text and "顾客 APP" not in r.text, f"h5-user 不应被 client-type 拦截：{r.text}"

# 5. miniprogram-user
print("\n=== miniprogram-user → 期望放行到业务层 ===")
r = post("/api/orders/unified/999999/appointment", body, {**auth, "Client-Type": "miniprogram-user"})
assert r.status_code in (404, 400), f"miniprogram-user 应放行，实际 {r.status_code}"
assert "客户端" not in r.text and "顾客 APP" not in r.text

# 6. app-user
print("\n=== app-user → 期望放行到业务层 ===")
r = post("/api/orders/unified/999999/appointment", body, {**auth, "Client-Type": "app-user"})
assert r.status_code in (404, 400), f"app-user 应放行，实际 {r.status_code}"
assert "客户端" not in r.text and "顾客 APP" not in r.text

# 7. 不带 Client-Type → 应 403
print("\n=== 不带 Client-Type → 期望 403 ===")
r = post("/api/orders/unified/999999/appointment", body, auth)
assert r.status_code == 403, f"应 403 但收到 {r.status_code}"

# 8. verify-miniprogram → 商家核销小程序，应 403
print("\n=== verify-miniprogram → 期望 403 ===")
r = post("/api/orders/unified/999999/appointment", body, {**auth, "Client-Type": "verify-miniprogram"})
assert r.status_code == 403, f"应 403 但收到 {r.status_code}"

# 9. h5-mobile（商家端 H5） → 应 403
print("\n=== h5-mobile → 期望 403 ===")
r = post("/api/orders/unified/999999/appointment", body, {**auth, "Client-Type": "h5-mobile"})
assert r.status_code == 403, f"应 403 但收到 {r.status_code}"

print("\n*** 全部 9 个 smoke 通过！Bug 367 远程修复有效。***")
