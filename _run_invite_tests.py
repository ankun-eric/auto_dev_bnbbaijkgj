"""运行新增的 test_invite_no_phantom_tab 测试用例。

直接对线上 BASE_URL 发起测试请求，与 backend/tests/test_invite_no_phantom_tab_20260525.py
保持同一套用例口径。
"""
import os
import random
import string
import sys
import time

import httpx

BASE_URL = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api"

random.seed()


def rphone():
    return "138" + "".join(random.choices(string.digits, k=8))


def reg_login(c: httpx.Client, phone=None):
    phone = phone or rphone()
    c.post(f"{BASE_URL}/auth/register", json={"phone": phone, "password": "Test123456", "nickname": f"t_{phone[-4:]}"})
    r = c.post(f"{BASE_URL}/auth/login", json={"phone": phone, "password": "Test123456"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], phone


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def list_members(c, tok):
    r = c.get(f"{BASE_URL}/family/members", headers=hdr(tok))
    assert r.status_code == 200, f"list members failed: {r.status_code} {r.text}"
    return r.json().get("items", [])


def create_member(c, tok, rel="父亲"):
    r = c.post(f"{BASE_URL}/family/members", headers=hdr(tok), json={
        "nickname": f"成员_{random.randint(1000, 9999)}",
        "relationship_type": rel,
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def create_invite(c, tok, member_id=None, relation_type=None):
    body = {}
    if member_id:
        body["member_id"] = member_id
    if relation_type:
        body["relation_type"] = relation_type
    return c.post(f"{BASE_URL}/family/invitation", headers=hdr(tok), json=body)


def get_invite_detail(c, tok, code):
    return c.get(f"{BASE_URL}/family/invitation/{code}", headers=hdr(tok))


def accept_invite(c, tok, code):
    return c.post(f"{BASE_URL}/family/invitation/{code}/accept", headers=hdr(tok), json={})


def run_tests():
    results = []

    with httpx.Client(verify=False, timeout=60) as c:
        # ─── T1: 情况 2 不预创建 Tab ───
        try:
            tok_a, _ = reg_login(c)
            members_before = list_members(c, tok_a)
            len_before = len(members_before)
            r = create_invite(c, tok_a, relation_type="妈妈")
            assert r.status_code == 200, f"T1 create_invite: {r.status_code} {r.text}"
            data = r.json()
            assert "invite_code" in data and data["invite_code"], f"T1 invite_code missing: {data}"
            members_after = list_members(c, tok_a)
            assert len(members_after) == len_before, (
                f"T1 expect len before == after: {len_before} vs {len(members_after)}\n"
                f"  before: {[m.get('nickname') or m.get('relationship_type') for m in members_before]}\n"
                f"  after:  {[m.get('nickname') or m.get('relationship_type') for m in members_after]}"
            )
            results.append(("T1_情况2不预创建Tab", "PASS", f"列表长度保持 {len_before}"))
        except AssertionError as e:
            results.append(("T1_情况2不预创建Tab", "FAIL", str(e)))
        except Exception as e:
            results.append(("T1_情况2不预创建Tab", "ERROR", repr(e)))

        # ─── T2: 情况 1 正常 Tab 邀请 ───
        try:
            tok_a, _ = reg_login(c)
            mid = create_member(c, tok_a, "父亲")
            r = create_invite(c, tok_a, member_id=mid, relation_type="父亲")
            assert r.status_code == 200, f"T2: {r.status_code} {r.text}"
            results.append(("T2_情况1正常Tab邀请", "PASS", f"member_id={mid} 创建邀请成功"))
        except AssertionError as e:
            results.append(("T2_情况1正常Tab邀请", "FAIL", str(e)))
        except Exception as e:
            results.append(("T2_情况1正常Tab邀请", "ERROR", repr(e)))

        # ─── T3: 情况 2 接受后才建 Tab ───
        try:
            tok_a, _ = reg_login(c)
            tok_b, _ = reg_login(c)
            members_a_before = list_members(c, tok_a)
            len_a_before = len(members_a_before)

            r = create_invite(c, tok_a, relation_type="爸爸")
            assert r.status_code == 200, f"T3 create_invite: {r.status_code} {r.text}"
            invite_code = r.json()["invite_code"]

            # 确认 A 列表没新增
            members_a_mid = list_members(c, tok_a)
            assert len(members_a_mid) == len_a_before, f"T3 在接受前 A 已新增 Tab"

            # B 接受
            ra = accept_invite(c, tok_b, invite_code)
            assert ra.status_code == 200, f"T3 accept: {ra.status_code} {ra.text}"

            # 此时 A 列表应该新增
            members_a_after = list_members(c, tok_a)
            assert len(members_a_after) == len_a_before + 1, (
                f"T3 接受后未新增 Tab: before={len_a_before} after={len(members_a_after)}"
            )
            # 新 Tab 的 relationship_type 应该为"爸爸"
            new_tabs = [m for m in members_a_after if m not in members_a_mid and not m.get("is_self")]
            # 不一定能直接 set 差，因为 dict 不 hashable；用 id
            ids_mid = {m["id"] for m in members_a_mid}
            new_tabs = [m for m in members_a_after if m["id"] not in ids_mid]
            assert new_tabs, "T3 未找到新 Tab"
            new_tab = new_tabs[0]
            assert new_tab.get("relationship_type") == "爸爸", f"T3 新 Tab relationship_type={new_tab.get('relationship_type')}"
            results.append(("T3_情况2接受后才建Tab", "PASS", f"新 Tab id={new_tab['id']}, relationship_type=爸爸"))
        except AssertionError as e:
            results.append(("T3_情况2接受后才建Tab", "FAIL", str(e)))
        except Exception as e:
            results.append(("T3_情况2接受后才建Tab", "ERROR", repr(e)))

        # ─── T5: 情况 2 并存多条 pending ───
        try:
            tok_a, _ = reg_login(c)
            codes = []
            for _ in range(3):
                r = create_invite(c, tok_a, relation_type="妈妈")
                assert r.status_code == 200, f"T5: {r.status_code} {r.text}"
                codes.append(r.json()["invite_code"])
            assert len(set(codes)) == 3, "T5 三条 invite_code 应该互不相同"
            # 每条 detail 都应该是 pending
            for code in codes:
                d = get_invite_detail(c, tok_a, code)
                assert d.status_code == 200, f"T5 detail: {d.status_code} {d.text}"
                assert d.json()["status"] == "pending", f"T5 detail status={d.json()['status']}"
            results.append(("T5_情况2并存多条pending", "PASS", f"3 条 pending 邀请并存：{[c[:8] for c in codes]}"))
        except AssertionError as e:
            results.append(("T5_情况2并存多条pending", "FAIL", str(e)))
        except Exception as e:
            results.append(("T5_情况2并存多条pending", "ERROR", repr(e)))

        # ─── T6: member_id=NULL 的邀请详情 ───
        try:
            tok_a, _ = reg_login(c)
            r = create_invite(c, tok_a, relation_type="奶奶")
            assert r.status_code == 200, f"T6 create: {r.status_code} {r.text}"
            invite_code = r.json()["invite_code"]
            d = get_invite_detail(c, tok_a, invite_code)
            assert d.status_code == 200, f"T6 detail: {d.status_code} {d.text}"
            body = d.json()
            assert body.get("member_id") is None, f"T6 member_id should be None: {body.get('member_id')}"
            assert body.get("relation_type") == "奶奶", f"T6 relation_type={body.get('relation_type')}"
            results.append(("T6_memberID为NULL邀请详情", "PASS", "member_id=None 且 relation_type=奶奶"))
        except AssertionError as e:
            results.append(("T6_memberID为NULL邀请详情", "FAIL", str(e)))
        except Exception as e:
            results.append(("T6_memberID为NULL邀请详情", "ERROR", repr(e)))

        # ─── T7: pending_invitation 字段在 family/members 上注入 ───
        try:
            tok_a, _ = reg_login(c)
            mid = create_member(c, tok_a, "父亲")
            r = create_invite(c, tok_a, member_id=mid, relation_type="父亲")
            assert r.status_code == 200, f"T7 invite: {r.status_code} {r.text}"
            members = list_members(c, tok_a)
            target = next((m for m in members if m["id"] == mid), None)
            assert target is not None, "T7 找不到目标 member"
            pi = target.get("pending_invitation")
            assert pi is not None, f"T7 pending_invitation 字段未注入: {target}"
            assert "invite_code" in pi and "expires_at" in pi and "remaining_hours" in pi, f"T7 pi 字段不全: {pi}"
            assert isinstance(pi["remaining_hours"], int), f"T7 remaining_hours 不是 int: {pi}"
            results.append(("T7_列表注入pending_invitation", "PASS", f"remaining_hours={pi['remaining_hours']}h"))
        except AssertionError as e:
            results.append(("T7_列表注入pending_invitation", "FAIL", str(e)))
        except Exception as e:
            results.append(("T7_列表注入pending_invitation", "ERROR", repr(e)))

    print("\n" + "=" * 80)
    print("测试用例执行结果")
    print("=" * 80)
    pass_count = 0
    for name, status, msg in results:
        flag = "✅" if status == "PASS" else "❌"
        print(f"{flag} {name}: {status}")
        print(f"   {msg}")
        if status == "PASS":
            pass_count += 1
    print("=" * 80)
    print(f"通过：{pass_count}/{len(results)}")
    return 0 if pass_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(run_tests())
