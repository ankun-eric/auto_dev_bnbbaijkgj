"""[PRD-HOME-SAFETY-V1] HTTPS E2E 烟雾测试（通过外部 HTTPS 调用真实接口）"""
import json
import sys
import time
import requests

BASE_URL = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

PASS = 0
FAIL = 0
RESULTS = []


def check(name, ok, info=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  -- {info}")
    RESULTS.append((name, ok, info))


def step(title):
    print(f"\n=== {title} ===")


def main():
    # 1) 未鉴权访问受保护接口应为 401
    step("1. 鉴权保护检查")
    for path in [
        "/api/home_safety/devices",
        "/api/admin/home_safety/dict/device_types",
        "/api/admin/home_safety/bindings",
        "/api/admin/home_safety/callback_config",
    ]:
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        check(f"GET {path} == 401", r.status_code == 401, f"got {r.status_code}")

    # 2) 注册并登录一个测试用户
    step("2. 注册+登录测试用户")
    phone = f"139{int(time.time()) % 100000000:08d}"
    pw = "Test123456"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"phone": phone, "password": pw, "nickname": "HS测试用户"},
        timeout=15,
    )
    check("register 200", r.status_code in (200, 201), f"{r.status_code} {r.text[:160]}")

    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"phone": phone, "password": pw},
        timeout=15,
    )
    check("login 200", r.status_code == 200, f"{r.status_code}")
    if r.status_code != 200:
        print("登录失败，中止后续测试")
        return
    token = r.json().get("access_token") or r.json().get("token")
    headers = {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}

    # 3) 设备列表（空）
    step("3. 用户接口")
    r = requests.get(f"{BASE_URL}/api/home_safety/devices", headers=headers, timeout=15)
    check("GET /devices 200", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
    data = r.json() if r.status_code == 200 else {}
    groups = data.get("groups") or []
    check("groups 包含 3 类设备", len(groups) == 3, str(len(groups)))

    # 4) 绑定设备
    r = requests.post(
        f"{BASE_URL}/api/home_safety/devices/bind",
        json={"device_type": 7, "gateway_sn": "GWWATER00001", "device_sn": "WATERSM1"},
        headers=headers,
        timeout=15,
    )
    check("POST bind device_type=7 200", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
    binding_id = r.json().get("id") if r.status_code == 200 else None

    # 5) 上游报警回调
    step("5. 上游报警回调")
    r = requests.post(
        f"{BASE_URL}/api/home_safety/callback/alarm",
        json={"device_sn": "WATERSM1", "type": 7, "alarm_time": "2026-05-27T19:00:00"},
        timeout=15,
    )
    check("callback alarm 200", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
    if r.status_code == 200:
        body = r.json()
        check("matched >= 1", (body.get("matched") or 0) >= 1, json.dumps(body))

    # 6) 同窗口重复 → 去重
    r = requests.post(
        f"{BASE_URL}/api/home_safety/callback/alarm",
        json={"device_sn": "WATERSM1", "type": 7, "alarm_time": "2026-05-27T19:01:30"},
        timeout=15,
    )
    if r.status_code == 200:
        body = r.json()
        check("去重 dedup_skipped >= 1", (body.get("dedup_skipped") or 0) >= 1, json.dumps(body))

    # 7) 报警记录列表
    r = requests.get(
        f"{BASE_URL}/api/home_safety/alarms?device_type=7", headers=headers, timeout=15
    )
    check("GET /alarms 200", r.status_code == 200, f"{r.status_code}")
    items = r.json().get("items") if r.status_code == 200 else []
    check("alarms 列表非空", len(items or []) >= 1, str(items))

    # 8) 紧急联系人
    r = requests.get(f"{BASE_URL}/api/home_safety/emergency_contacts", headers=headers, timeout=15)
    check("GET /emergency_contacts 200", r.status_code == 200, f"{r.status_code}")

    # 9) 解绑
    if binding_id:
        r = requests.post(
            f"{BASE_URL}/api/home_safety/devices/{binding_id}/unbind",
            headers=headers,
            timeout=15,
        )
        check("POST unbind 200", r.status_code == 200, f"{r.status_code}")

    # 10) AI 外呼回调（占位接口）
    r = requests.post(
        f"{BASE_URL}/api/home_safety/callback/ai_call_result",
        json={"request_id": "rid1", "status": "success"},
        timeout=15,
    )
    check("AI 外呼回调 200", r.status_code == 200, f"{r.status_code}")

    # 11) 前端页面
    step("11. H5 页面 200")
    for p in ["/home-safety/", "/health-profile/"]:
        r = requests.get(f"{BASE_URL}{p}", timeout=15)
        check(f"GET {p} 200", r.status_code == 200, f"{r.status_code}")

    print(f"\n=========== 汇总: PASS={PASS}  FAIL={FAIL} ===========")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
