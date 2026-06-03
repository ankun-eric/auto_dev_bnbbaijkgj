"""[PRD-MED-PLAN-OPTIM-V1] 公网端到端 smoke 测试"""
import json
import random
import string
import sys
import urllib.request
import urllib.parse
import ssl

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def req(method, path, body=None, token=None):
    url = BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        resp = urllib.request.urlopen(r, context=ctx, timeout=30)
        raw = resp.read().decode("utf-8")
        return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def rand_phone():
    return "139" + "".join(random.choices(string.digits, k=8))


def main():
    phone = rand_phone()
    pwd = "Pass1234!"
    print(f"[1] 注册 {phone}")
    code, body = req("POST", "/api/auth/register", {
        "phone": phone, "password": pwd, "code": "0000", "nickname": "smoke",
    })
    print(f"    -> {code} {str(body)[:200]}")
    if code != 200:
        # 尝试登录
        code, body = req("POST", "/api/auth/login", {"phone": phone, "password": pwd})
        print(f"    login fallback -> {code} {str(body)[:200]}")
    code, body = req("POST", "/api/auth/login", {"phone": phone, "password": pwd})
    assert code == 200, body
    token = body.get("access_token") or (body.get("data") or {}).get("access_token")
    assert token, f"no token: {body}"

    print("\n[2] 普通计划：start+end+long_term=False")
    code, body = req("POST", "/api/health-plan/medications", {
        "medicine_name": "smoke-阿司匹林",
        "dosage": "1 片",
        "dosage_value": "1",
        "dosage_unit": "片",
        "frequency_per_day": 2,
        "custom_times": ["08:00", "20:00"],
        "remind_time": "08:00",
        "time_period": "custom",
        "start_date": "2026-05-17",
        "end_date": "2026-06-15",
        "duration_days": 30,
        "long_term": False,
        "guidance": "饭后",
        "notes": "smoke",
        "reminder_enabled": True,
    }, token=token)
    print(f"    -> {code}")
    assert code == 200, body
    item = body
    rid = item["id"]
    assert item["long_term"] is False, item
    assert item["end_date"] == "2026-06-15", item

    print("\n[3] 长期计划：long_term=True 时 end_date 应为 null")
    code, body = req("POST", "/api/health-plan/medications", {
        "medicine_name": "smoke-二甲双胍",
        "dosage": "1 片", "dosage_value": "1", "dosage_unit": "片",
        "frequency_per_day": 2, "custom_times": ["08:00", "20:00"], "remind_time": "08:00",
        "time_period": "custom",
        "start_date": "2026-05-17",
        "end_date": "2026-12-31",
        "long_term": True,
        "guidance": "饭后",
    }, token=token)
    print(f"    -> {code}")
    assert code == 200, body
    assert body["long_term"] is True, body
    assert body["end_date"] is None, body

    print("\n[4] 服用时机老枚举写入 -> 自动迁移到新枚举")
    code, body = req("POST", "/api/health-plan/medications", {
        "medicine_name": "smoke-早上药",
        "dosage": "1 片", "dosage_value": "1", "dosage_unit": "片",
        "frequency_per_day": 1, "custom_times": ["08:00"], "remind_time": "08:00",
        "time_period": "custom",
        "start_date": "2026-05-17", "end_date": "2026-06-15",
        "long_term": False,
        "guidance": "早上",
    }, token=token)
    print(f"    -> {code} guidance={body.get('guidance')}")
    assert code == 200, body
    assert body["guidance"] == "饭前", body  # 早上 → 饭前

    print("\n[5] 列表接口返回 long_term/end_date 字段")
    code, body = req("GET", "/api/health-plan/medications/list?tab=in_progress", token=token)
    print(f"    -> {code} total={body.get('total')}")
    assert code == 200, body
    items = body.get("items", [])
    long_item = [x for x in items if x["medicine_name"] == "smoke-二甲双胍"]
    assert long_item and long_item[0]["long_term"] is True and long_item[0]["end_date"] is None, long_item

    print("\n[6] 切换为长期：PUT long_term=True 应清空 end_date")
    code, body = req("PUT", f"/api/health-plan/medications/{rid}", {
        "long_term": True,
    }, token=token)
    print(f"    -> {code} long_term={body.get('long_term')} end_date={body.get('end_date')}")
    assert code == 200, body
    assert body["long_term"] is True and body["end_date"] is None

    print("\n[7] 详情接口")
    code, body = req("GET", f"/api/health-plan/medications/{rid}", token=token)
    assert code == 200, body
    assert body["long_term"] is True and body["end_date"] is None

    print("\n[8] 联想接口")
    code, body = req("GET", "/api/medication-library/suggest?q=" + urllib.parse.quote("阿莫"), token=token)
    print(f"    -> {code} items_count={len((body or {}).get('items', []))}")
    assert code == 200, body

    print("\nALL PASSED ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
