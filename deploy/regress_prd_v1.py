"""端到端业务回归：登录、个人信息、修改密码、员工管理"""
import base64
import io
import json
import ssl
import urllib.error
import urllib.request

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def http(method: str, path: str, body=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, None


def get_captcha():
    code, body = http("GET", "/api/captcha/image")
    return body["captcha_id"], body["image_base64"]


# ─────────── 1. 验证码生成 ───────────
print("【1】验证码生成")
cid, img_b64 = get_captcha()
raw_b64 = img_b64.split(",", 1)[-1] if img_b64.startswith("data:") else img_b64
print(f"  OK captcha_id={cid[:12]}...  PNG bytes={len(base64.b64decode(raw_b64))}  data-uri={img_b64[:30]}")

# ─────────── 2. admin 登录 - 验证码错误 ───────────
print("\n【2】admin 登录 - 验证码错误")
code, body = http("POST", "/api/admin/login", {
    "phone": "13000000001", "password": "wrong",
    "captcha_id": cid, "captcha_code": "WRONG",
})
print(f"  HTTP {code} -> {body}")
print(f"  {'✓' if code in (400, 401, 403) else '✗'} 验证码/密码错误时被拒绝")

# ─────────── 3. admin 登录 - 缺少验证码字段 ───────────
print("\n【3】admin 登录 - 完全无验证码字段")
code, body = http("POST", "/api/admin/login", {
    "phone": "13000000001", "password": "admin123",
})
print(f"  HTTP {code} -> {body}")
print(f"  {'✓' if code in (400, 401, 422, 403) else '✗'} 缺验证码字段时被拒")

# ─────────── 4. 商家 PC 登录 - 短信通道已禁 ───────────
print("\n【4】商家 PC 登录 - 旧的短信通道（应被拒绝）")
cid2, _ = get_captcha()
code, body = http("POST", "/api/merchant/auth/login", {
    "phone": "13900000001", "sms_code": "1234",
    "captcha_id": cid2, "captcha_code": "ABCD",
})
print(f"  HTTP {code} -> {body}")

# ─────────── 5. 商家 PC 登录 - 验证码错误 ───────────
print("\n【5】商家 PC 登录 - 验证码错误")
cid3, _ = get_captcha()
code, body = http("POST", "/api/merchant/auth/login", {
    "phone": "13900000001", "password": "wrongpass",
    "captcha_id": cid3, "captcha_code": "WRONG",
})
print(f"  HTTP {code} -> {body}")
print(f"  {'✓' if code in (400, 401) else '✗'} 错误验证码被拒")

# ─────────── 6. 个人信息 / 改密码（无 token 应 401） ───────────
print("\n【6】个人信息 / 改密码 接口鉴权（无 token）")
for path, method in [
    ("/api/admin/profile", "GET"),
    ("/api/admin/password", "PUT"),
    ("/api/merchant/profile", "GET"),
    ("/api/merchant/password", "PUT"),
    ("/api/merchant/staff/create", "POST"),
    ("/api/merchant/staff/reset-password", "POST"),
    ("/api/merchant/staff/toggle-status", "POST"),
]:
    body = {} if method != "GET" else None
    code, _ = http(method, path, body)
    ok = code in (401, 403, 422)
    print(f"  {'✓' if ok else '✗'} {method} {path}: {code}")

# ─────────── 7. 商家员工列表 - 应返回 401 ───────────
print("\n【7】员工列表（无 token）")
code, _ = http("GET", "/api/merchant/v1/staff")
print(f"  {'✓' if code in (401, 403) else '✗'} GET /api/merchant/v1/staff: {code}")

print("\n" + "=" * 60)
print("回归测试完成")
print("=" * 60)
