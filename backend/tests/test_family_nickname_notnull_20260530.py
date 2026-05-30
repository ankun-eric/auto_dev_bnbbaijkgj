"""[BUG_FIX-FAMILY-NICKNAME-NOTNULL-20260530] 健康档案空姓名清理回归测试

覆盖：
- 用例 1：新建档案，姓名留空 → 400 "姓名不能为空"
- 用例 2：新建档案，姓名为纯空格 → 400 "姓名不能为空"
- 用例 3：编辑档案，nickname 改为空字符串 → 400 "姓名不能为空"
- 用例 4：编辑档案，nickname 改为纯空格 → 400 "姓名不能为空"
- 用例 5：新注册用户自动建本人档，nickname 不再是 "本人"，而是 用户{后4位}
- 用例 6：列表接口不会回显姓名为空字符串的本人档（按现有规则即可）
- 用例 7：新建档案，正常 nickname → 200
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_family_member_empty_nickname_rejected(
    client: AsyncClient, auth_headers
):
    """姓名为空字符串应被后端拒绝（400）。"""
    resp = await client.post(
        "/api/family/members",
        json={
            "relationship_type": "spouse",
            "name": "",
            "nickname": "",
            "gender": "female",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "姓名不能为空" in detail


@pytest.mark.asyncio
async def test_create_family_member_whitespace_nickname_rejected(
    client: AsyncClient, auth_headers
):
    """姓名为纯空格应被后端拒绝（400）。"""
    resp = await client.post(
        "/api/family/members",
        json={
            "relationship_type": "parent",
            "name": "   ",
            "nickname": "   ",
            "gender": "male",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "姓名不能为空" in detail


@pytest.mark.asyncio
async def test_create_family_member_valid_nickname_ok(
    client: AsyncClient, auth_headers
):
    """姓名正常，应创建成功并 nickname 持久化。"""
    resp = await client.post(
        "/api/family/members",
        json={
            "relationship_type": "spouse",
            "name": "张三",
            "nickname": "张三",
            "gender": "female",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["nickname"] == "张三"


@pytest.mark.asyncio
async def test_update_family_member_empty_nickname_rejected(
    client: AsyncClient, auth_headers
):
    """编辑档案：把 nickname 清空应被拒绝。"""
    create = await client.post(
        "/api/family/members",
        json={
            "relationship_type": "parent",
            "name": "父亲",
            "nickname": "父亲",
            "gender": "male",
        },
        headers=auth_headers,
    )
    assert create.status_code == 200, create.text
    member_id = create.json()["id"]

    upd = await client.put(
        f"/api/family/members/{member_id}",
        json={"nickname": ""},
        headers=auth_headers,
    )
    assert upd.status_code == 400
    assert "姓名不能为空" in upd.json().get("detail", "")


@pytest.mark.asyncio
async def test_update_family_member_whitespace_nickname_rejected(
    client: AsyncClient, auth_headers
):
    """编辑档案：把 nickname 改为纯空格应被拒绝。"""
    create = await client.post(
        "/api/family/members",
        json={
            "relationship_type": "child",
            "name": "孩子",
            "nickname": "孩子",
            "gender": "male",
        },
        headers=auth_headers,
    )
    assert create.status_code == 200
    member_id = create.json()["id"]

    upd = await client.put(
        f"/api/family/members/{member_id}",
        json={"nickname": "  "},
        headers=auth_headers,
    )
    assert upd.status_code == 400
    assert "姓名不能为空" in upd.json().get("detail", "")


@pytest.mark.asyncio
async def test_self_family_member_default_nickname_uses_user4(client: AsyncClient):
    """新注册手机号用户，自动建本人档的 nickname 应：
    - 优先 user.nickname（注册时传入"测试用户A"则为 "测试用户A"）
    - 当注册未传 nickname 时，自动用 用户{后4位}
    """
    # 场景 A：注册时未传 nickname → users.nickname 由后端兜底为「用户{后4位}」
    #         本人档 nickname 取 user.nickname → 即 "用户4567"
    phone_a = "13900004567"
    reg_a = await client.post(
        "/api/auth/register",
        json={"phone": phone_a, "password": "user123"},
    )
    assert reg_a.status_code == 200, reg_a.text

    login_a = await client.post(
        "/api/auth/login", json={"phone": phone_a, "password": "user123"}
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "Client-Type": "h5-user"}

    lst_a = await client.get("/api/family/members", headers=headers_a)
    assert lst_a.status_code == 200
    items = lst_a.json()["items"]
    self_a = next((x for x in items if x.get("is_self")), None)
    assert self_a is not None, "应自动建本人档"
    # 关键断言：nickname 不再是 "本人"
    assert self_a["nickname"] != "本人"
    # 取本人档 nickname：应为 "用户4567" 或与用户 nickname 一致
    assert "4567" in (self_a["nickname"] or "") or (self_a["nickname"] or "").startswith("用户")


@pytest.mark.asyncio
async def test_self_family_member_nickname_never_empty(client: AsyncClient):
    """新注册用户自动建本人档时，nickname 必非空。"""
    phone = "13800007777"
    reg = await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "user123"},
    )
    assert reg.status_code == 200

    login = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "user123"}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}

    lst = await client.get("/api/family/members", headers=headers)
    assert lst.status_code == 200
    items = lst.json()["items"]
    self_one = next((x for x in items if x.get("is_self")), None)
    assert self_one is not None
    nick = self_one.get("nickname") or ""
    assert nick.strip() != "", "本人档 nickname 不能为空"
