"""[BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03]
外部 HTTPS smoke：端到端验证多 pending 共存。
"""
import os
import sys
import time
import json
import random
import urllib.request
import urllib.parse
import ssl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _sshlib import DEPLOY_ID

BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def http(method, path, data=None, headers=None):
    url = BASE_URL + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {"raw": str(e)}
        return e.code, payload


def main():
    phone = f"139{random.randint(10000000, 99999999)}"
    print(f"[1] 注册用户 phone={phone}")
    code, data = http("POST", "/api/auth/register", {
        "phone": phone, "password": "pass1234", "nickname": "smoke守护测试",
    })
    print(f"  -> {code} {str(data)[:120]}")

    print(f"[2] 登录")
    code, data = http("POST", "/api/auth/login", {
        "phone": phone, "password": "pass1234",
    })
    print(f"  -> {code} keys={list(data.keys()) if isinstance(data,dict) else type(data)}")
    token = data.get("access_token")
    if not token:
        print("[!] no token, abort")
        return
    hdr = {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}

    print(f"[3] 初始 guardian-count")
    code, data = http("GET", "/api/reverse-guardian/guardian-count", headers=hdr)
    print(f"  -> {code} {data}")
    y_limit = data.get("max_guardians_for_me", 3)

    print(f"[4] 创建第 1 条邀请")
    code, data = http("POST", "/api/reverse-guardian/invite", {
        "guardian_name": "张三", "relation_type": "叔叔",
    }, headers=hdr)
    print(f"  -> {code} code={data.get('invite_code','')[:16]}…")
    code1 = data.get("invite_code")

    print(f"[5] 创建第 2 条邀请")
    code, data = http("POST", "/api/reverse-guardian/invite", {
        "guardian_name": "李四", "relation_type": "阿姨",
    }, headers=hdr)
    print(f"  -> {code} code={data.get('invite_code','')[:16]}…")
    code2 = data.get("invite_code")

    assert code1 != code2

    print(f"[6] 列表应有 2 条 pending")
    code, data = http("GET", "/api/reverse-guardian/my-guardians", headers=hdr)
    items = data.get("items", []) if isinstance(data, dict) else []
    pending = [i for i in items if i.get("item_type") == "pending"]
    print(f"  -> {code} pending_count={len(pending)} guardian_names={[p.get('guardian_name') for p in pending]}")
    assert len(pending) == 2, f"AT-6 FAILED: expected 2 pending, got {len(pending)}"

    print(f"[7] 第 3 条邀请（合法）")
    code, data = http("POST", "/api/reverse-guardian/invite", {
        "guardian_name": "王五", "relation_type": "其他",
    }, headers=hdr)
    print(f"  -> {code} code={str(data.get('invite_code',''))[:16]}…")

    print(f"[8] 第 4 条邀请，应被上限拦截")
    code, data = http("POST", "/api/reverse-guardian/invite", {
        "guardian_name": "超出", "relation_type": "朋友",
    }, headers=hdr)
    print(f"  -> {code} {data}")
    if y_limit == 3:
        assert code == 400, f"AT-7 expected 400, got {code}"
        detail = data.get("detail", {})
        assert isinstance(detail, dict)
        assert detail.get("code") == "GUARDIAN_LIMIT_REACHED", f"AT-7 expected GUARDIAN_LIMIT_REACHED, got {detail}"
        print("  ✓ AT-7 上限拦截正确")

    print(f"[9] 取消第 1 条邀请")
    code, data = http("POST", "/api/reverse-guardian/invite/cancel", {
        "invite_code": code1,
    }, headers=hdr)
    print(f"  -> {code} {data}")

    print(f"[10] 列表应剩 2 条 pending")
    code, data = http("GET", "/api/reverse-guardian/my-guardians", headers=hdr)
    items = data.get("items", []) if isinstance(data, dict) else []
    pending = [i for i in items if i.get("item_type") == "pending"]
    print(f"  -> {code} pending_count={len(pending)}")
    assert len(pending) == 2

    print("\nALL SMOKE TESTS PASSED ✓")


if __name__ == "__main__":
    main()
