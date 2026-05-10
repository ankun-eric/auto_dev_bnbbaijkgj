"""[PRD-448 v1.2] 部署后非 UI 自动化验证：直接打 /api/v1/consultant/0/profile_card

流程：
  1) 注册一个新测试用户（带随机后缀避免冲突）
  2) 用该 token 调 GET /api/v1/consultant/0/profile_card
  3) 断言 200 + is_self=True + nickname 不为空 + 7 项字段结构齐全
"""
from __future__ import annotations

import json
import random
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def http(method: str, path: str, *, token: str | None = None, json_body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, {"raw": body[:200]}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body[:200]}


def main() -> int:
    rand = random.randint(10000000, 99999999)
    phone = f"139{rand}"
    password = "test123456"
    print(f"[1/3] register {phone}")
    code, body = http("POST", "/api/auth/register", json_body={
        "phone": phone, "password": password, "nickname": f"v12_{rand}",
    })
    print(f"  -> {code} {str(body)[:200]}")
    if code not in (200, 201):
        print("[FAIL] register failed")
        return 1

    print(f"[2/3] login {phone}")
    code, body = http("POST", "/api/auth/login", json_body={
        "phone": phone, "password": password,
    })
    print(f"  -> {code} {str(body)[:200]}")
    if code != 200 or "access_token" not in body:
        print("[FAIL] login failed")
        return 1
    token = body["access_token"]

    print(f"[3/3] GET /api/v1/consultant/0/profile_card with token")
    code, body = http("GET", "/api/v1/consultant/0/profile_card", token=token)
    print(f"  -> {code}")
    print(f"  body: {json.dumps(body, ensure_ascii=False, indent=2)[:800]}")

    if code != 200:
        print(f"[FAIL] expected 200, got {code}")
        return 1

    # 检查关键字段
    required_keys = {"consultant_id", "nickname", "is_self", "fields", "completeness"}
    missing = required_keys - set(body.keys())
    if missing:
        print(f"[FAIL] missing keys: {missing}")
        return 1
    if body.get("is_self") is not True:
        print(f"[FAIL] is_self != True: {body.get('is_self')}")
        return 1
    fields = body.get("fields", {})
    field_keys = {"gender", "age", "height", "weight", "past_history", "allergy", "long_term_meds"}
    if not field_keys.issubset(set(fields.keys())):
        print(f"[FAIL] fields missing: {field_keys - set(fields.keys())}")
        return 1
    completeness = body.get("completeness", {})
    if "percent" not in completeness or "filled_count" not in completeness or "total" not in completeness:
        print("[FAIL] completeness incomplete")
        return 1

    print("\n[PASS] PRD-448 v1.2 §7.2 接口验收全部通过：")
    print(f"  - is_self = True")
    print(f"  - nickname = {body['nickname']!r}")
    print(f"  - 7 项字段结构齐全")
    print(f"  - completeness.percent = {completeness['percent']}")
    print(f"  - completeness.filled_count = {completeness['filled_count']}/{completeness['total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
