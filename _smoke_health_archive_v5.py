"""[PRD-HEALTH-ARCHIVE-V5-20260521] 部署后烟雾测试。

通过注册临时用户 + 调用关键接口，确认远端流程通畅：
1. /api/health-archive-v5/overview         200
2. /api/health-alerts/_seed                200 + 24h 合并
3. /api/medical-records POST/GET/DELETE    流程闭环
"""
from __future__ import annotations

import sys
import time

import requests

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def register_and_login() -> str:
    phone = f"139{int(time.time())%10000000:07d}"
    pw = "Test123456"
    requests.post(f"{BASE}/api/auth/register", json={
        "phone": phone, "password": pw, "nickname": "v5烟雾",
    }, verify=False, timeout=20)
    r = requests.post(f"{BASE}/api/auth/login", json={
        "phone": phone, "password": pw,
    }, verify=False, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> int:
    token = register_and_login()
    h = {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}
    print("=== 1. overview ===")
    r = requests.get(f"{BASE}/api/health-archive-v5/overview", headers=h, verify=False, timeout=20)
    print(r.status_code, r.json())
    assert r.status_code == 200
    assert r.json()["alerts_unresolved"] == 0

    print("\n=== 2. seed 预警 + 合并 ===")
    r = requests.post(f"{BASE}/api/health-alerts/_seed", headers=h, verify=False, json={
        "items": [{"alert_type": "device", "indicator": "bp", "title": "血压偏高", "severity": "high"}],
    }, timeout=20)
    print(r.status_code, r.json())
    assert r.json()["created"] == 1
    r = requests.post(f"{BASE}/api/health-alerts/_seed", headers=h, verify=False, json={
        "items": [{"alert_type": "device", "indicator": "bp", "title": "血压偏高"}],
    }, timeout=20)
    print("merge:", r.json())
    assert r.json()["merged"] == 1

    print("\n=== 3. 列表 + 解决 ===")
    r = requests.get(f"{BASE}/api/health-alerts?status=open", headers=h, verify=False, timeout=20)
    items = r.json()["items"]
    print("open count:", len(items), "merged_count:", items[0]["merged_count"])
    assert items[0]["merged_count"] == 2
    aid = items[0]["id"]
    r = requests.post(f"{BASE}/api/health-alerts/{aid}/resolve", headers=h, verify=False, timeout=20)
    print("resolve:", r.json())
    assert r.json()["ok"]

    print("\n=== 4. 就医资料 CRUD ===")
    r = requests.post(f"{BASE}/api/medical-records", headers=h, verify=False, json={
        "category": "checkup_report",
        "title": "体检报告 2026.05",
        "record_date": "2026-05-21",
        "source": "manual",
        "files": [{"file_url": "/uploads/test.jpg", "file_name": "test.jpg", "file_type": "image"}],
    }, timeout=20)
    print(r.status_code, r.json().get("id"), r.json().get("title"))
    assert r.status_code == 200
    rid = r.json()["id"]

    r = requests.get(f"{BASE}/api/medical-records", headers=h, verify=False, timeout=20)
    print("list grouped:", r.json()["grouped"])

    r = requests.delete(f"{BASE}/api/medical-records/{rid}", headers=h, verify=False, timeout=20)
    print("soft delete:", r.json())
    assert r.json()["purge_after_days"] == 30

    r = requests.get(f"{BASE}/api/medical-records/trash", headers=h, verify=False, timeout=20)
    print("trash count:", r.json()["total"])

    print("\n=== 5. AI 首页 hero-count ===")
    r = requests.get(f"{BASE}/api/medication-plans/hero-count?consultant_id=0", headers=h, verify=False, timeout=20)
    d = r.json()
    print(d)
    assert d["ai_home_label"] == "今日无用药"
    print("\n✅ 全部烟雾测试通过")
    return 0


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"❌ 断言失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 异常: {e}")
        sys.exit(2)
