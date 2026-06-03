"""[PRD-MY-DEVICES-V1] HTTP 烟雾测试。

不依赖容器内 pytest（容器精简了 dev 依赖），直接通过 HTTP 接口走端到端流程。
"""
from __future__ import annotations

import json
import sys
import time
import uuid

import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"


def hr(title: str) -> None:
    print(f"\n────── {title} ──────")


def ok(cond: bool, msg: str) -> None:
    print(("✅" if cond else "❌") + " " + msg)
    if not cond:
        global FAIL
        FAIL += 1


FAIL = 0


def register_user(phone: str, password: str = "user123", nickname: str = "tester") -> str:
    requests.post(f"{BASE}/api/auth/register", json={
        "phone": phone, "password": password, "nickname": nickname,
    }, verify=False, timeout=30)
    res = requests.post(f"{BASE}/api/auth/login", json={
        "phone": phone, "password": password,
    }, verify=False, timeout=30)
    return res.json().get("access_token") or res.json().get("token") or ""


def main() -> int:
    hr("基础探活")
    r = requests.get(f"{BASE}/api/health", verify=False, timeout=15)
    ok(r.status_code == 200, f"/api/health → {r.status_code}")
    r = requests.get(f"{BASE}/devices/", verify=False, timeout=15)
    ok(r.status_code == 200, f"/devices/ → {r.status_code}")

    hr("匿名访问 /api/devices/catalog 应 401")
    r = requests.get(f"{BASE}/api/devices/catalog", verify=False, timeout=15)
    ok(r.status_code in (401, 403), f"/api/devices/catalog 未授权 → {r.status_code}")

    # 注册账号 A
    suffix = uuid.uuid4().hex[:6]
    phone_a = f"139{int(time.time()) % 100000000:08d}"[-11:]
    phone_a = "139" + str(int(time.time()) % 100000000).zfill(8)[-8:]
    # 使用唯一手机号
    phone_a = f"139{(int(time.time()) % 100000000):08d}"
    token_a = register_user(phone_a, nickname="设备测试A")
    if not token_a:
        print("⚠️ 注册/登录失败", phone_a)
        return 1
    h_a = {"Authorization": f"Bearer {token_a}", "Client-Type": "h5-user"}

    hr("GET /api/devices/catalog（鉴权后）")
    r = requests.get(f"{BASE}/api/devices/catalog", headers=h_a, verify=False, timeout=15)
    ok(r.status_code == 200, f"status={r.status_code}")
    data = r.json()
    groups = {g["brand_code"]: g for g in data.get("groups", [])}
    for b in ["binni", "huawei", "xiaomi", "apple", "other"]:
        ok(b in groups, f"包含品牌 {b}")
    if "binni" in groups:
        ok(len(groups["binni"]["items"]) == 7, f"宾尼 7 项 (实际 {len(groups['binni']['items'])})")
        smoke = [it for it in groups["binni"]["items"] if it["category_code"] == "smoke_alarm"]
        ok(bool(smoke) and smoke[0]["is_unique"] is False, "烟雾报警器 is_unique=False")
    if "apple" in groups:
        ok(all(not it["is_active"] for it in groups["apple"]["items"]), "苹果敬请期待")
    if "huawei" in groups:
        band = [it for it in groups["huawei"]["items"] if it["category_code"] == "band"]
        ok(bool(band) and band[0]["is_active"], "华为手环已接通")

    # 选一项宾尼智能手表绑定
    binni_watch_id = None
    binni_smoke_id = None
    if "binni" in groups:
        for it in groups["binni"]["items"]:
            if it["category_code"] == "smartwatch":
                binni_watch_id = it["id"]
            if it["category_code"] == "smoke_alarm":
                binni_smoke_id = it["id"]
    apple_id = None
    if "apple" in groups and groups["apple"]["items"]:
        apple_id = groups["apple"]["items"][0]["id"]

    hr("GET /api/devices/my 初始空")
    r = requests.get(f"{BASE}/api/devices/my", headers=h_a, verify=False, timeout=15)
    ok(r.status_code == 200, f"status={r.status_code}")
    ok(r.json().get("total", -1) >= 0, "my 接口返回 ok")

    hr("POST /api/devices/bind 宾尼智能手表")
    sn1 = f"SMOKE-SN-{suffix}-01"
    r = requests.post(f"{BASE}/api/devices/bind", headers=h_a,
                      json={"catalog_id": binni_watch_id, "sn": sn1, "alias": "我的手表"},
                      verify=False, timeout=15)
    ok(r.status_code == 200, f"绑定 → {r.status_code} {r.text[:200]}")
    bid1 = r.json().get("id") if r.status_code == 200 else None
    if r.status_code == 200:
        b = r.json()["binding"]
        ok(b["sn_masked"] != b["sn"], f"SN 已脱敏 {b['sn_masked']}")
        ok(b["alias"] == "我的手表", "别名正确")

    hr("POST /api/devices/bind 同一唯一类设备应 409")
    r = requests.post(f"{BASE}/api/devices/bind", headers=h_a,
                      json={"catalog_id": binni_watch_id, "sn": f"DUP-{suffix}"},
                      verify=False, timeout=15)
    ok(r.status_code == 409, f"重复绑定唯一类 → {r.status_code}")

    hr("POST /api/devices/bind Apple Watch 应 400（敬请期待）")
    if apple_id:
        r = requests.post(f"{BASE}/api/devices/bind", headers=h_a,
                          json={"catalog_id": apple_id, "sn": f"APPLE-{suffix}"},
                          verify=False, timeout=15)
        ok(r.status_code == 400, f"未接通 → {r.status_code}")

    hr("POST /api/devices/bind 烟雾报警器多绑 3 台")
    if binni_smoke_id:
        for i in range(3):
            r = requests.post(f"{BASE}/api/devices/bind", headers=h_a,
                              json={"catalog_id": binni_smoke_id, "sn": f"SMK-{suffix}-{i}"},
                              verify=False, timeout=15)
            ok(r.status_code == 200, f"烟雾报警器 #{i} → {r.status_code}")

    hr("GET /api/devices/my 列表已含 4 台（1 手表 + 3 烟雾）")
    r = requests.get(f"{BASE}/api/devices/my", headers=h_a, verify=False, timeout=15)
    items = r.json().get("items", [])
    ok(len([x for x in items if x["category_code"] == "smartwatch"]) == 1, "1 块手表")
    ok(len([x for x in items if x["category_code"] == "smoke_alarm"]) == 3, "3 个烟雾报警器")

    hr("PATCH /api/devices/binding/{id} 改别名")
    if bid1:
        r = requests.patch(f"{BASE}/api/devices/binding/{bid1}", headers=h_a,
                            json={"alias": "新别名"}, verify=False, timeout=15)
        ok(r.status_code == 200, f"编辑 → {r.status_code}")
        if r.status_code == 200:
            ok(r.json()["binding"]["alias"] == "新别名", "别名已更新")

    hr("POST /api/devices/unbind 解绑手表 + bound_count 联动")
    if bid1:
        r = requests.post(f"{BASE}/api/devices/unbind", headers=h_a,
                          json={"binding_id": bid1}, verify=False, timeout=15)
        ok(r.status_code == 200, f"解绑 → {r.status_code}")
    # catalog 再次拉取，宾尼智能手表 bound_count 应为 0
    r = requests.get(f"{BASE}/api/devices/catalog", headers=h_a, verify=False, timeout=15)
    g2 = {g["brand_code"]: g for g in r.json().get("groups", [])}
    sw_item = next((it for it in g2["binni"]["items"] if it["category_code"] == "smartwatch"), None)
    if sw_item:
        ok(sw_item["bound_count"] == 0, f"解绑后 bound_count=0 (实际 {sw_item['bound_count']})")

    hr("解绑后再次绑定同型号应成功")
    r = requests.post(f"{BASE}/api/devices/bind", headers=h_a,
                      json={"catalog_id": binni_watch_id, "sn": f"REBIND-{suffix}"},
                      verify=False, timeout=15)
    ok(r.status_code == 200, f"重新绑定 → {r.status_code}")

    hr("同 SN 跨账户共享")
    # 注册 B
    phone_b = f"139{(int(time.time()) + 7) % 100000000:08d}"
    token_b = register_user(phone_b, nickname="设备测试B")
    h_b = {"Authorization": f"Bearer {token_b}", "Client-Type": "h5-user"}
    shared_sn = f"SHARED-SN-{suffix}"
    r1 = requests.post(f"{BASE}/api/devices/bind", headers=h_a,
                       json={"catalog_id": binni_smoke_id, "sn": shared_sn},
                       verify=False, timeout=15)
    r2 = requests.post(f"{BASE}/api/devices/bind", headers=h_b,
                       json={"catalog_id": binni_smoke_id, "sn": shared_sn},
                       verify=False, timeout=15)
    ok(r1.status_code == 200 and r2.status_code == 200,
       f"同 SN 跨账户共享 r1={r1.status_code} r2={r2.status_code}")

    print(f"\n────── 总结：失败 {FAIL} 项 ──────")
    return 0 if FAIL == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
