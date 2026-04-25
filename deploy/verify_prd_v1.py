"""核心链接可达性测试（PRD V1.0 关键端点 + 页面）"""
import urllib.request
import urllib.error
import ssl
import json

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

# 后端关键端点 (M7 验证码、profile、change-password)
API_GET = [
    "/api/captcha/image",                # 验证码生成
    "/api/admin/profile",                # 401 也算可达
    "/api/merchant/profile",             # 401 也算可达
]

# 前端页面（所有应返回 200 或 3xx）
PAGES = [
    "/admin/login",
    "/admin/profile",
    "/admin/profile/change-password",
    "/admin/merchant/accounts",
    "/merchant/login",
    "/merchant/profile",
    "/merchant/profile/change-password",
    "/merchant/staff",
    "/merchant/m/login",
    "/merchant/m/profile",
    "/merchant/m/profile/change-password",
    "/merchant/m/profile/force-change-password",
    "/merchant/m/staff",
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

results: list[tuple[str, str, int | str]] = []

def fetch(url: str, method: str = "GET", expect: tuple[int, ...] = (200, 301, 302, 401, 403)):
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"ERR:{type(e).__name__}:{e}"


print("=" * 60)
print("API 端点测试")
print("=" * 60)
for path in API_GET:
    url = BASE + path
    code = fetch(url)
    ok = "✓" if (isinstance(code, int) and code in (200, 401, 403)) else "✗"
    print(f"  {ok} {path}: {code}")
    results.append(("api", path, code))

print()
print("=" * 60)
print("前端页面测试")
print("=" * 60)
for path in PAGES:
    url = BASE + path
    code = fetch(url)
    ok = "✓" if (isinstance(code, int) and code in (200, 301, 302, 307, 308, 401, 403)) else "✗"
    print(f"  {ok} {path}: {code}")
    results.append(("page", path, code))

# 验证 captcha 接口返回结构
print()
print("=" * 60)
print("验证码接口返回结构")
print("=" * 60)
try:
    req = urllib.request.Request(BASE + "/api/captcha/image")
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        keys = list(data.keys())
        has_id = "captcha_id" in data
        has_img = "image_base64" in data or "image" in data or "data" in data
        print(f"  返回字段: {keys}")
        print(f"  包含 captcha_id: {has_id}")
        print(f"  包含 image: {has_img}")
        if isinstance(data.get('image_base64'), str):
            print(f"  image_base64 长度: {len(data['image_base64'])}")
except Exception as e:
    print(f"  ERR: {e}")

# 汇总
fails = [r for r in results if not (isinstance(r[2], int) and r[2] in (200, 301, 302, 307, 308, 401, 403))]
print()
print("=" * 60)
print(f"汇总: {len(results) - len(fails)}/{len(results)} 通过")
if fails:
    print("失败:")
    for kind, p, c in fails:
        print(f"  - [{kind}] {p}: {c}")
print("=" * 60)
