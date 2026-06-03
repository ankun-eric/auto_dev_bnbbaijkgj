"""[BUGFIX-SAFETY-ROPE-V1 2026-06-03] 远程冒烟测试：4 个 Bug 端到端验证

测试场景：
1. 创建测试用户 A（主用户）+ 用户 B（联系人）
2. Bug3 验证：
   - check-phone 未注册手机号 → registered=false
   - check-phone 已注册手机号 → registered=true
   - create_contact 用未注册手机号 → 400
   - create_contact 用已注册手机号 → 200 + 立即出现在 list
3. Bug4 验证：
   - 签到后 status 接口立即返回 last_checkin 和 today_checked=true
4. Bug1/Bug2：H5 页面渲染检查（HTML 中包含关键 testid）
"""
import json
import random
import urllib.request
import urllib.parse
import ssl

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def http(method: str, path: str, *, token: str = None, body: dict = None, params: dict = None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            text = resp.read().decode("utf-8", "ignore")
            try:
                return resp.status, json.loads(text)
            except Exception:
                return resp.status, text
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text


def get_h5(path: str):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8", "ignore")


def random_phone(prefix="138"):
    return prefix + "".join([str(random.randint(0, 9)) for _ in range(8)])


def register_login(phone: str, nickname: str) -> str:
    """注册并登录，返回 access_token。"""
    pwd = "test1234"
    # 注册
    code, body = http("POST", "/api/auth/register", body={
        "phone": phone, "password": pwd, "nickname": nickname,
    })
    if code not in (200, 201, 400):
        raise RuntimeError(f"register failed: {code} {body}")
    # 登录
    code, body = http("POST", "/api/auth/login", body={"phone": phone, "password": pwd})
    if code != 200:
        raise RuntimeError(f"login failed: {code} {body}")
    return body["access_token"]


def main():
    results = []
    failures = []

    print("=" * 60)
    print("准备阶段：创建两个测试用户")
    print("=" * 60)
    phone_a = random_phone("138")
    phone_b = random_phone("139")
    print(f"用户A（主用户）: {phone_a}")
    print(f"用户B（联系人）: {phone_b}")

    token_a = register_login(phone_a, "测试用户A")
    register_login(phone_b, "测试用户B")  # 仅用于注册
    print("✓ 两个用户创建成功")

    # ---- 鉴权 ----
    print("\n" + "=" * 60)
    print("[T1] 鉴权：未登录访问 status 应 401")
    print("=" * 60)
    code, body = http("GET", "/api/safety-rope/status")
    ok = code in (401, 403)
    print(f"  status_code={code} body={body}")
    (results if ok else failures).append(f"T1 鉴权 {'PASS' if ok else 'FAIL'}")

    # ---- Bug3-a: check-phone 未注册 ----
    print("\n" + "=" * 60)
    print("[T2 / Bug3-a] check-phone：未注册手机号应返回 registered=false")
    print("=" * 60)
    unregistered = random_phone("137")
    code, body = http("GET", "/api/safety-rope/contacts/check-phone",
                       token=token_a, params={"phone": unregistered})
    ok = code == 200 and body.get("registered") is False
    print(f"  code={code} body={body}")
    (results if ok else failures).append(f"T2 check-phone未注册 {'PASS' if ok else 'FAIL'}")

    # ---- Bug3-b: check-phone 已注册 ----
    print("\n" + "=" * 60)
    print("[T3 / Bug3-b] check-phone：已注册手机号应返回 registered=true")
    print("=" * 60)
    code, body = http("GET", "/api/safety-rope/contacts/check-phone",
                       token=token_a, params={"phone": phone_b})
    ok = code == 200 and body.get("registered") is True and "B" in (body.get("name") or "")
    print(f"  code={code} body={body}")
    (results if ok else failures).append(f"T3 check-phone已注册 {'PASS' if ok else 'FAIL'}")

    # ---- Bug3-c: check-phone 格式错误 ----
    print("\n" + "=" * 60)
    print("[T4] check-phone：格式错误应返回 valid=false")
    print("=" * 60)
    code, body = http("GET", "/api/safety-rope/contacts/check-phone",
                       token=token_a, params={"phone": "123"})
    ok = code == 200 and body.get("valid") is False
    print(f"  code={code} body={body}")
    (results if ok else failures).append(f"T4 check-phone格式校验 {'PASS' if ok else 'FAIL'}")

    # ---- Bug3-d: create_contact 拒绝未注册 ----
    print("\n" + "=" * 60)
    print("[T5 / Bug3-d] create_contact：未注册手机号必须 400")
    print("=" * 60)
    code, body = http("POST", "/api/safety-rope/contacts",
                       token=token_a,
                       body={"name": "假联系人", "phone": unregistered, "relation": "子女"})
    ok = code == 400
    print(f"  code={code} body={body}")
    (results if ok else failures).append(f"T5 create_contact拒绝未注册 {'PASS' if ok else 'FAIL'}")

    # ---- Bug3-e: create_contact 拒绝缺手机号 ----
    print("\n" + "=" * 60)
    print("[T6] create_contact：缺手机号应被拒")
    print("=" * 60)
    code, body = http("POST", "/api/safety-rope/contacts",
                       token=token_a, body={"name": "无手机", "relation": "子女"})
    ok = code in (400, 422)
    print(f"  code={code} body={body}")
    (results if ok else failures).append(f"T6 create_contact无手机号 {'PASS' if ok else 'FAIL'}")

    # ---- Bug3-f: 关系字段非法 ----
    print("\n" + "=" * 60)
    print("[T7] create_contact：关系字段必须在 7 芯片白名单")
    print("=" * 60)
    code, body = http("POST", "/api/safety-rope/contacts",
                       token=token_a,
                       body={"name": "B", "phone": phone_b, "relation": "情人"})
    ok = code == 400
    print(f"  code={code} body={body}")
    (results if ok else failures).append(f"T7 关系白名单 {'PASS' if ok else 'FAIL'}")

    # ---- Bug3 核心: create + list 立即可见 ----
    print("\n" + "=" * 60)
    print("[T8 / Bug3 核心] create_contact 成功后立即在 list 中可见")
    print("=" * 60)
    # 先清空一下当前用户已有的联系人（用 list+delete 兜底）
    code, body = http("GET", "/api/safety-rope/contacts", token=token_a)
    if code == 200:
        for c in body.get("items", []):
            http("DELETE", f"/api/safety-rope/contacts/{c['id']}", token=token_a)

    code, body = http("POST", "/api/safety-rope/contacts",
                       token=token_a,
                       body={"name": "测试用户B", "phone": phone_b, "relation": "子女"})
    create_ok = code == 200 and body.get("success") is True
    print(f"  create code={code} body={body}")

    code, body = http("GET", "/api/safety-rope/contacts", token=token_a)
    items = body.get("items", []) if isinstance(body, dict) else []
    print(f"  list code={code} count={len(items)}")
    if items:
        print(f"  first item: {items[0]}")
    list_ok = code == 200 and len(items) >= 1 and any(c.get("phone") == phone_b for c in items)
    ok = create_ok and list_ok
    (results if ok else failures).append(f"T8 添加联系人立即可见 {'PASS' if ok else 'FAIL'}")

    # ---- Bug3-g: 不传 email 也能成功 ----
    print("\n" + "=" * 60)
    print("[T9] create_contact：不传 email 字段也能成功")
    print("=" * 60)
    phone_c = random_phone("136")
    # 先注册一个 C
    register_login(phone_c, "测试用户C")
    code, body = http("POST", "/api/safety-rope/contacts",
                       token=token_a,
                       body={"name": "测试用户C", "phone": phone_c, "relation": "朋友"})
    ok = code == 200
    print(f"  code={code} body={body}")
    (results if ok else failures).append(f"T9 邮箱字段可省略 {'PASS' if ok else 'FAIL'}")

    # ---- Bug4: 签到 + status 立即反映 ----
    print("\n" + "=" * 60)
    print("[T10 / Bug4] 签到后 status 立即返回 today_checked=true + last_checkin")
    print("=" * 60)
    code, body = http("POST", "/api/safety-rope/checkin",
                       token=token_a, body={"location_address": "冒烟测试地址"})
    print(f"  checkin code={code} body={body}")
    checkin_ok = code == 200 and body.get("success") is True
    code, body = http("GET", "/api/safety-rope/status", token=token_a)
    print(f"  status today_checked={body.get('today_checked')} last_checkin={body.get('last_checkin')}")
    status_ok = (
        code == 200
        and body.get("today_checked") is True
        and body.get("last_checkin") is not None
        and body.get("next_checkin_at") is not None  # 用于"下次截止"
    )
    ok = checkin_ok and status_ok
    (results if ok else failures).append(f"T10 签到立即更新状态 {'PASS' if ok else 'FAIL'}")

    # ---- 配置阈值修改 ----
    print("\n" + "=" * 60)
    print("[T11] 阈值修改 24/48 应该成功，其他值应被拒")
    print("=" * 60)
    code, body = http("PUT", "/api/safety-rope/config", token=token_a, body={"threshold_hours": 24})
    ok1 = code == 200 and body.get("config", {}).get("threshold_hours") == 24
    code, body = http("PUT", "/api/safety-rope/config", token=token_a, body={"threshold_hours": 48})
    ok2 = code == 200 and body.get("config", {}).get("threshold_hours") == 48
    code, body = http("PUT", "/api/safety-rope/config", token=token_a, body={"threshold_hours": 99})
    ok3 = code == 400
    ok = ok1 and ok2 and ok3
    print(f"  set 24={ok1}, set 48={ok2}, reject 99={ok3}")
    (results if ok else failures).append(f"T11 阈值校验 {'PASS' if ok else 'FAIL'}")

    # ---- Bug1: H5 关怀首页含数字安全绳入口 ----
    print("\n" + "=" * 60)
    print("[T12 / Bug1] H5 关怀首页 HTML 含数字安全绳入口（卡片 + 悬浮球）")
    print("=" * 60)
    code, html = get_h5("/care-home")
    has_entry_card = "care-home-safety-rope-entry" in html
    has_fab = "care-home-safety-rope-fab" in html
    has_text = "数字安全绳" in html
    ok = code == 200 and has_text and (has_entry_card or has_fab)
    print(f"  code={code} card={has_entry_card} fab={has_fab} text={has_text}")
    (results if ok else failures).append(f"T12 关怀首页入口可见 {'PASS' if ok else 'FAIL'}")

    # ---- Bug2: H5 安全绳页 JS bundle 中含阈值/横幅相关字符串 ----
    print("\n" + "=" * 60)
    print("[T13 / Bug2] H5 安全绳页 JS chunk 中含阈值 selected / 横幅 / 关系芯片 / 检查点")
    print("=" * 60)
    # Next.js 客户端组件代码会出现在 _next/static/chunks/*.js 中（路径前缀含 basePath）
    code, html = get_h5("/care-safety-rope")
    import re
    # 匹配各种形式的 js 资源（含 basePath 前缀）
    js_paths = re.findall(r'["\']((?:/autodev/[^"\']*?)?/_next/static/[^"\']+?\.js)["\']', html)
    js_paths = list(set(js_paths))
    print(f"  found {len(js_paths)} js chunks")
    combined = html
    for jp in js_paths[:80]:
        full = jp if jp.startswith("http") else f"https://newbb.test.bangbangvip.com{jp}"
        try:
            with urllib.request.urlopen(full, context=ctx, timeout=15) as r:
                combined += r.read().decode("utf-8", "ignore")
        except Exception as e:
            print(f"   fetch fail {full[:100]}: {e}")
    has_threshold = "sr-threshold-" in combined  # 模板字符串：动态拼 24/48
    has_threshold_arr = "[24,48]" in combined or "[24, 48]" in combined
    has_check_mark = "sr-threshold-" in combined and "-check" in combined
    has_chip = "sr-relation-" in combined and "子女" in combined and "护工" in combined
    has_banner = "上次签到" in combined and "下次签到截止" in combined
    has_phone_check = "sr-contact-phone-check" in combined and "check-phone" in combined
    ok = code == 200 and has_threshold and has_threshold_arr and has_chip and has_banner and has_phone_check
    print(f"  threshold={has_threshold} arr={has_threshold_arr} check={has_check_mark} chip={has_chip} banner={has_banner} phone_check={has_phone_check}")
    (results if ok else failures).append(f"T13 安全绳页内容渲染 {'PASS' if ok else 'FAIL'}")

    # ---- 总结 ----
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    for r in results:
        print(f"  ✓ {r}")
    for r in failures:
        print(f"  ✗ {r}")
    print(f"\nTOTAL: {len(results)+len(failures)} / PASS: {len(results)} / FAIL: {len(failures)}")
    return len(failures) == 0


if __name__ == "__main__":
    ok = main()
    import sys
    sys.exit(0 if ok else 1)
