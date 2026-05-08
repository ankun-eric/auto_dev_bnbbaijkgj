"""[PRD-420 2026-05-08] AI 对话模式 - 咨询对象选择器 端到端 smoke 测试。

复现真实用户在 H5 ai-home 上的全部交互链路：
1. 注册新用户 → 自动创建本人成员
2. 列出家庭成员（GET /api/family/members）→ 看到本人
3. 列出关系字典（GET /api/relation-types）→ 看到 15 个关系
4. AI 对话模式新建家庭成员"老婆·朱小妹"（POST /api/family/members）
5. 再列出 → 现在多了一个"老婆"
6. 创建会话指定 family_member_id=老婆 → 200 + 关联
7. 切换会话归属人为本人（family_member_id=null）→ 200
8. 切换回老婆 → 200
9. AI 对话模式新建家庭成员"儿子·苏俊林"（覆盖 F4 全字段）
10. 创建会话指定儿子 → 200 + 关联

PRD F7 数据共享：菜单模式 GET /api/family/members 应能立即看到 AI 模式新增的成员。
"""
from __future__ import annotations

import json
import random
import sys
import time
from urllib import request, error, parse


BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def _req(method: str, path: str, *, token: str | None = None, body: dict | None = None) -> tuple[int, dict | None]:
    url = f"{BASE_URL}{path}"
    data = None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["Client-Type"] = "h5-user"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw) if raw else None
            except Exception:
                return resp.status, {"_raw": raw}
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw) if raw else None
        except Exception:
            return e.code, {"_raw": raw}


def main() -> int:
    failed: list[str] = []

    def expect(name: str, cond: bool, detail: str = ""):
        status = "OK" if cond else "FAIL"
        print(f"[{status}] {name}{(' - ' + detail) if detail else ''}")
        if not cond:
            failed.append(name)

    # 1. 注册新用户
    suffix = random.randint(100000, 999999)
    phone = f"139{suffix:08d}"[:11]
    pwd = "test12345"
    code, body = _req("POST", "/api/auth/register", body={
        "phone": phone, "password": pwd, "nickname": f"prd420测试{suffix}",
    })
    expect("T1 注册新用户", code == 200, f"code={code}")
    if code != 200:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 1

    # 登录拿 token
    code, body = _req("POST", "/api/auth/login", body={"phone": phone, "password": pwd})
    expect("T1.1 登录获取 token", code == 200 and body and "access_token" in body)
    token = body["access_token"]

    # 2. 列出家庭成员
    code, body = _req("GET", "/api/family/members", token=token)
    expect("T2 列出家庭成员", code == 200 and "items" in body)
    items = body["items"]
    self_member = next((m for m in items if m.get("is_self")), None)
    expect("T2.1 默认存在本人成员（is_self=True）", self_member is not None)

    # 3. 列出关系字典
    code, body = _req("GET", "/api/relation-types", token=token)
    expect("T3 列出关系字典", code == 200 and "items" in body)
    rel_names = {r.get("name") for r in body["items"]}
    expected_relations = {"爸爸", "妈妈", "老公", "老婆", "儿子", "女儿", "其他"}
    expect(
        "T3.1 包含 PRD F3 关系九宫格关键关系",
        expected_relations.issubset(rel_names),
        f"缺失={expected_relations - rel_names}",
    )

    # 4. AI 对话模式新建"老婆"
    code, body = _req("POST", "/api/family/members", token=token, body={
        "nickname": "朱小妹",
        "name": "朱小妹",
        "relationship_type": "老婆",
        "gender": "female",
        "birthday": "1992-08-15",
        "height": 165,
        "weight": 52.5,
    })
    expect("T4 AI模式新建老婆-朱小妹", code == 200, f"code={code}")
    if code == 200:
        wife_id = body["id"]
        expect("T4.1 关系=老婆", body.get("relationship_type") == "老婆")
        expect("T4.2 is_self=False", body.get("is_self") is False)
    else:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        wife_id = None

    # 5. 再列出
    code, body = _req("GET", "/api/family/members", token=token)
    items = body.get("items") if body else []
    expect(
        "T5 列表中能看到老婆",
        any(m.get("nickname") == "朱小妹" and m.get("relationship_type") == "老婆" for m in items),
    )

    # 6. 创建会话指定老婆为咨询对象
    if wife_id:
        code, body = _req("POST", "/api/chat/sessions", token=token, body={
            "session_type": "health_qa",
            "family_member_id": wife_id,
            "title": "为老婆的咨询",
        })
        expect("T6 创建会话(family_member_id=老婆)", code == 200, f"code={code}")
        if code == 200:
            sess_id = body["id"]

            # 7. 切换为本人
            code, body = _req(
                "POST",
                f"/api/chat/sessions/{sess_id}/switch-member",
                token=token,
                body={"family_member_id": None},
            )
            expect("T7 切换为本人(family_member_id=null)", code == 200, f"code={code}")
            expect(
                "T7.1 切换响应 family_member_id=None",
                code == 200 and body.get("family_member_id") is None,
            )

            # 8. 切回老婆
            code, body = _req(
                "POST",
                f"/api/chat/sessions/{sess_id}/switch-member",
                token=token,
                body={"family_member_id": wife_id},
            )
            expect("T8 切换回老婆", code == 200, f"code={code}")
            expect(
                "T8.1 切换响应 family_member_id 正确",
                code == 200 and body.get("family_member_id") == wife_id,
            )

    # 9. AI 模式新建"儿子"（F4 全字段）
    code, body = _req("POST", "/api/family/members", token=token, body={
        "nickname": "苏俊林",
        "name": "苏俊林",
        "relationship_type": "儿子",
        "gender": "male",
        "birthday": "2010-06-01",
        "height": 145,
        "weight": 38.5,
        "medical_histories": ["哮喘"],
        "allergies": ["花粉"],
    })
    expect("T9 AI模式新建儿子-苏俊林(全字段)", code == 200, f"code={code}")
    if code == 200:
        son_id = body["id"]
        expect("T9.1 medical_histories 持久化", body.get("medical_histories") == ["哮喘"])
        expect("T9.2 allergies 持久化", body.get("allergies") == ["花粉"])

        # 10. 为儿子开新会话
        code, body = _req("POST", "/api/chat/sessions", token=token, body={
            "session_type": "health_qa",
            "family_member_id": son_id,
            "title": "为儿子的咨询",
        })
        expect("T10 创建会话(family_member_id=儿子)", code == 200, f"code={code}")

    # 11. F7 数据共享：菜单模式（同一接口）应包含 AI 模式新增的全部成员
    code, body = _req("GET", "/api/family/members", token=token)
    items = body.get("items") if body else []
    nicknames = {m.get("nickname") for m in items}
    expect(
        "T11 F7 数据共享 - 菜单模式可看到 AI 模式新增的所有成员",
        {"朱小妹", "苏俊林"}.issubset(nicknames),
    )

    # 12. ai-home 页面可访问（最终用户路径）
    code, body = _req("GET", "/api/ai-home-config", token=token)
    expect("T12 /api/ai-home-config 可达", code == 200)

    print("\n" + "=" * 60)
    if failed:
        print(f"FAIL: {len(failed)} 个用例失败：")
        for n in failed:
            print(f"  - {n}")
        return 1
    print(f"PASS: 全部通过（{12} 类用例 / 多项断言）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
