"""[BUGFIX-MY-GUARDIAN-CARD-2-20260528] 端到端冒烟测试

直接走 HTTPS 网关，注册 → 登录 → 建孤儿档案 → 查 list（验证 is_orphan=True）→ 调 remove（两次） → 验证幂等
"""
import random
import string
import time

import requests

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"


def rand_phone() -> str:
    return "138" + "".join(random.choices(string.digits, k=8))


def main():
    s = requests.Session()
    s.verify = False
    requests.packages.urllib3.disable_warnings()

    phone = rand_phone()
    pwd = "abc12345"

    # 1. 注册
    r = s.post(f"{BASE}/api/auth/register", json={"phone": phone, "password": pwd, "nickname": "冒烟用户"})
    print("注册:", r.status_code, r.text[:200])

    # 2. 登录
    r = s.post(f"{BASE}/api/auth/login", json={"phone": phone, "password": pwd})
    print("登录:", r.status_code, r.text[:120])
    assert r.status_code == 200
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}

    # 3. 外部"我的家人"Tab 建档（接口 POST /api/family/members）
    r = s.post(
        f"{BASE}/api/family/members",
        headers=h,
        json={"nickname": "外婆冒烟", "relationship_type": "祖母", "gender": "female"},
    )
    print("建档:", r.status_code, r.text[:200])
    assert r.status_code in (200, 201)
    member_id = r.json().get("id")
    print(f"  member_id={member_id}")

    # 4. 查 list，验证 is_orphan
    r = s.get(f"{BASE}/api/guardian/v13/family/list", headers=h)
    print("list:", r.status_code)
    data = r.json()
    items = data.get("items", [])
    orphans = [it for it in items if it.get("managed_member_id") == member_id]
    print(f"  孤儿条目数={len(orphans)}, max_guardians={data.get('max_guardians')}, can_invite={data.get('can_invite_count')}")
    assert len(orphans) == 1
    assert orphans[0].get("is_orphan") is True
    assert orphans[0].get("bind_status") == "unbound"

    # 5. 第一次 remove → deleted=true
    r = s.post(f"{BASE}/api/guardian/v13/family/remove", headers=h, json={"managed_member_id": member_id})
    print("remove#1:", r.status_code, r.text[:200])
    assert r.status_code == 200
    d1 = r.json()
    assert d1.get("deleted") is True, f"expected deleted=true, got {d1}"

    # 6. 第二次 remove → deleted=false（幂等，不报 404）
    r = s.post(f"{BASE}/api/guardian/v13/family/remove", headers=h, json={"managed_member_id": member_id})
    print("remove#2:", r.status_code, r.text[:200])
    assert r.status_code == 200, f"应幂等返 200，实际 {r.status_code} {r.text}"
    d2 = r.json()
    assert d2.get("deleted") is False
    assert d2.get("should_refresh") is True

    # 7. 不存在的 management 调用 → 也应 200
    r = s.post(f"{BASE}/api/guardian/v13/family/remove", headers=h, json={"managed_member_id": 99999999})
    print("remove 不存在:", r.status_code, r.text[:200])
    assert r.status_code == 200

    print("\n✅ 端到端冒烟测试全部通过")


if __name__ == "__main__":
    main()
