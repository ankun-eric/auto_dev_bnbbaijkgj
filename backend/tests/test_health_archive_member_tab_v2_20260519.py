"""[BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 顶部成员 Tab V2 后端验收测试。

覆盖：
- /api/family/members 返回 avatar_color_index / relation_badge_char / guard_status
- 关系徽章字映射：本人→我、爸爸→爸、妈妈→妈、儿子→儿、女儿→女、伴侣→爱、爷爷→爷、外公→外
- 创建新成员时 avatar_color_index = 已入档数 % 5（循环）
- 本人始终排第一
- /api/family-archive-v2/members 也按新规则返回 儿/女（与 /api/family/members 保持一致）
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture
def _h(auth_headers):
    return auth_headers


@pytest.mark.asyncio
async def test_members_v1_endpoint_has_new_fields(client: AsyncClient, _h):
    """/api/family/members 必须返回 V2 新字段。"""
    await client.post(
        "/api/family/members",
        json={"relationship_type": "妈妈", "nickname": "老妈"},
        headers=_h,
    )
    r = await client.get("/api/family/members", headers=_h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) >= 1
    for it in items:
        assert "avatar_color_index" in it
        assert it["avatar_color_index"] in (0, 1, 2, 3, 4)
        assert "relation_badge_char" in it
        assert isinstance(it["relation_badge_char"], str) and len(it["relation_badge_char"]) >= 1
        assert "guard_status" in it
        assert it["guard_status"] in ("self", "guarded", "unguarded")


@pytest.mark.asyncio
async def test_self_member_first(client: AsyncClient, _h):
    """本人必须始终排第一。"""
    await client.post(
        "/api/family/members",
        json={"relationship_type": "爸爸", "nickname": "老爸"},
        headers=_h,
    )
    r = await client.get("/api/family/members", headers=_h)
    items = r.json()["items"]
    if any(it["is_self"] for it in items):
        assert items[0]["is_self"] is True


@pytest.mark.asyncio
async def test_badge_char_son_daughter_split(client: AsyncClient, _h):
    """V2 微调：儿子→儿，女儿→女，不再统一显示'娃'。"""
    r1 = await client.post(
        "/api/family/members",
        json={"relationship_type": "儿子", "nickname": "大宝"},
        headers=_h,
    )
    assert r1.status_code == 200, r1.text
    son_badge = r1.json()["relation_badge_char"]
    assert son_badge == "儿", f"儿子应映射为'儿'，实际：{son_badge}"

    r2 = await client.post(
        "/api/family/members",
        json={"relationship_type": "女儿", "nickname": "小宝"},
        headers=_h,
    )
    assert r2.status_code == 200, r2.text
    daughter_badge = r2.json()["relation_badge_char"]
    assert daughter_badge == "女", f"女儿应映射为'女'，实际：{daughter_badge}"


@pytest.mark.asyncio
async def test_badge_char_full_mapping(client: AsyncClient, _h):
    """全量关系→徽章字映射用例。"""
    cases = [
        ("爸爸", "爸"),
        ("妈妈", "妈"),
        ("老公", "爱"),
        ("老婆", "爱"),
        ("丈夫", "爱"),
        ("妻子", "爱"),
        ("伴侣", "爱"),
        ("哥哥", "哥"),
        ("弟弟", "弟"),
        ("姐姐", "姐"),
        ("妹妹", "妹"),
        ("爷爷", "爷"),
        ("奶奶", "奶"),
        ("外公", "外"),
        ("外婆", "外"),
    ]
    for relation, expected_badge in cases:
        r = await client.post(
            "/api/family/members",
            json={"relationship_type": relation, "nickname": f"测试_{relation}"},
            headers=_h,
        )
        assert r.status_code == 200, f"创建 {relation} 失败: {r.text}"
        got = r.json()["relation_badge_char"]
        assert got == expected_badge, f"{relation} 应映射为 {expected_badge}，实际：{got}"


@pytest.mark.asyncio
async def test_avatar_color_index_cycles_mod5(client: AsyncClient, _h):
    """连续新增 6 个成员，avatar_color_index 应在 0-4 之间循环。"""
    # 先取已有数量
    r0 = await client.get("/api/family/members", headers=_h)
    base_count = len(r0.json()["items"])

    indices = []
    for i in range(6):
        r = await client.post(
            "/api/family/members",
            json={"relationship_type": "其他亲属", "nickname": f"亲属{i}"},
            headers=_h,
        )
        assert r.status_code == 200, r.text
        idx = r.json()["avatar_color_index"]
        assert idx in (0, 1, 2, 3, 4)
        indices.append(idx)

    # 期望：从 (base_count) % 5 开始，依次 +1 mod 5
    expected = [(base_count + i) % 5 for i in range(6)]
    assert indices == expected, f"avatar_color_index 不是按 mod 5 循环：{indices}，期望 {expected}"


@pytest.mark.asyncio
async def test_v2_endpoint_badge_son_daughter_split(client: AsyncClient, _h):
    """/api/family-archive-v2/members 也应使用 儿/女 分别映射。"""
    await client.post(
        "/api/family/members",
        json={"relationship_type": "儿子", "nickname": "儿子v2"},
        headers=_h,
    )
    await client.post(
        "/api/family/members",
        json={"relationship_type": "女儿", "nickname": "女儿v2"},
        headers=_h,
    )
    r = await client.get("/api/family-archive-v2/members", headers=_h)
    items = r.json()["items"]
    son_items = [it for it in items if it["relationship_type"] == "儿子"]
    daughter_items = [it for it in items if it["relationship_type"] == "女儿"]
    assert son_items, "未找到儿子成员"
    assert daughter_items, "未找到女儿成员"
    assert all(it["relation_badge_char"] == "儿" for it in son_items)
    assert all(it["relation_badge_char"] == "女" for it in daughter_items)
