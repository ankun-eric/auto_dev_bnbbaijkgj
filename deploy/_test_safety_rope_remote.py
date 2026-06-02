"""远程测试数字安全绳完整 E2E（注册用户 + API 调用）"""
import paramiko
import requests
import time
import random

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def main():
    # 1) 创建测试用户（通过 SMS 验证码流程）
    phone = f"1399{random.randint(1000000, 9999999)}"
    print(f"[test] phone={phone}")

    # 注册：sms-code + register
    r = requests.post(f"{BASE}/api/auth/register", json={
        "phone": phone, "password": "test_safety_rope", "nickname": "测试用户"
    }, verify=False, timeout=10)
    print(f"  register: {r.status_code} {r.text[:200]}")

    r = requests.post(f"{BASE}/api/auth/login", json={
        "phone": phone, "password": "test_safety_rope"
    }, verify=False, timeout=10)
    print(f"  login: {r.status_code}")
    token = r.json().get("access_token")
    if not token:
        print(f"  login failed: {r.text[:200]}")
        return
    H = {"Authorization": f"Bearer {token}"}

    # 2) GET /status
    r = requests.get(f"{BASE}/api/safety-rope/status", headers=H, verify=False, timeout=10)
    print(f"\n[1] GET status: {r.status_code}")
    assert r.status_code == 200, r.text
    body = r.json()
    print(f"  cfg={body['config']}, runtime={body['runtime_status']}, last_checkin={body['last_checkin']}")
    assert body["config"]["threshold_hours"] == 48
    assert body["config"]["status"] == "normal"

    # 3) PUT /config 修改阈值
    r = requests.put(f"{BASE}/api/safety-rope/config", headers=H, json={"threshold_hours": 24}, verify=False, timeout=10)
    print(f"\n[2] PUT config threshold=24: {r.status_code}")
    assert r.status_code == 200
    assert r.json()["config"]["threshold_hours"] == 24

    # 4) POST /checkin
    r = requests.post(f"{BASE}/api/safety-rope/checkin", headers=H, json={
        "location_address": "北京市朝阳区测试地址"
    }, verify=False, timeout=10)
    print(f"\n[3] POST checkin: {r.status_code}")
    assert r.status_code == 200
    assert r.json()["success"] is True

    # 5) GET /status 验证签到
    r = requests.get(f"{BASE}/api/safety-rope/status", headers=H, verify=False, timeout=10)
    body = r.json()
    print(f"\n[4] GET status after checkin: last_checkin_addr={body['last_checkin']['location_address']}, today_checked={body['today_checked']}")
    assert body["today_checked"] is True
    assert body["last_checkin"]["location_address"] == "北京市朝阳区测试地址"

    # 6) POST /contacts 添加联系人（最多 3 位）
    for i in range(3):
        r = requests.post(f"{BASE}/api/safety-rope/contacts", headers=H, json={
            "name": f"联系人{i}", "email": f"contact{i}_{phone}@test.com", "relation": "子女"
        }, verify=False, timeout=10)
        print(f"\n[5.{i+1}] POST contact: {r.status_code}")
        assert r.status_code == 200

    # 7) 第 4 个被拒
    r = requests.post(f"{BASE}/api/safety-rope/contacts", headers=H, json={
        "name": "多余", "email": f"extra_{phone}@test.com"
    }, verify=False, timeout=10)
    print(f"\n[6] POST 4th contact: {r.status_code}")
    assert r.status_code == 400

    # 8) GET /contacts
    r = requests.get(f"{BASE}/api/safety-rope/contacts", headers=H, verify=False, timeout=10)
    items = r.json()["items"]
    print(f"\n[7] GET contacts: count={len(items)}")
    assert len(items) == 3

    # 9) PUT /config 暂停 + 恢复
    r = requests.put(f"{BASE}/api/safety-rope/config", headers=H, json={"paused": True, "paused_days": 7}, verify=False, timeout=10)
    print(f"\n[8] PUT pause: {r.status_code}, status={r.json()['config']['status']}")
    assert r.json()["config"]["status"] == "paused"
    r = requests.put(f"{BASE}/api/safety-rope/config", headers=H, json={"paused": False}, verify=False, timeout=10)
    print(f"[9] PUT resume: {r.status_code}, status={r.json()['config']['status']}")
    assert r.json()["config"]["status"] == "normal"

    # 10) GET /alerts
    r = requests.get(f"{BASE}/api/safety-rope/alerts", headers=H, verify=False, timeout=10)
    print(f"\n[10] GET alerts: {r.status_code}, total={r.json()['total']}")
    assert r.status_code == 200

    # 11) DELETE contact
    cid = items[0]["id"]
    r = requests.delete(f"{BASE}/api/safety-rope/contacts/{cid}", headers=H, verify=False, timeout=10)
    print(f"\n[11] DELETE contact {cid}: {r.status_code}")
    assert r.status_code == 200

    # 12) PUT contact
    cid2 = items[1]["id"]
    r = requests.put(f"{BASE}/api/safety-rope/contacts/{cid2}", headers=H, json={"name": "更新名"}, verify=False, timeout=10)
    print(f"\n[12] PUT contact {cid2}: {r.status_code}")
    assert r.status_code == 200

    print("\n========== ALL E2E TESTS PASSED ==========")


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    main()
