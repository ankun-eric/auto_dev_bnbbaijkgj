"""
[PRD-HEALTH-ARCHIVE-FAMILY-MEMBER-V1 2026-06-02 改动点3]
家庭成员 Tab 与入口卡口径统一回归测试。

修复前：/api/family/members 用 status == 'active'，会漏掉 cancelled_by_target / pending 等中间态成员，
       导致顶部 Tab 显示 3 人，入口卡显示 5 人，前后口径不一致。

修复后：/api/family/members 改为 status != 'deleted'，与官方权威状态机
       /api/family/member/state/list 和入口卡的 count_managed_family_members 完全一致。

本测试覆盖：
1. cancelled_by_target 状态成员仍出现在 Tab 列表中
2. 自定义中间态成员（如 pending、left）仍出现在 Tab 列表中
3. deleted 状态成员不再出现在 Tab 列表中（保证软删除依然生效）
"""
import pytest
from httpx import AsyncClient

from app.models.models import FamilyMember
from sqlalchemy import select

# 复用 conftest.py 中创建的 in-memory 测试 sessionmaker，
# 否则在 mysql/sqlite 不同 DB 之间写读会读不到。
from tests.conftest import test_session


async def _set_member_status(member_id: int, new_status: str) -> None:
    """直接通过 ORM 修改成员 status，模拟解绑/退出等中间态。"""
    async with test_session() as db:
        result = await db.execute(select(FamilyMember).where(FamilyMember.id == member_id))
        m = result.scalars().first()
        assert m is not None, f"member_id={member_id} not found"
        m.status = new_status
        await db.commit()


@pytest.mark.asyncio
async def test_list_members_includes_cancelled_by_target(client: AsyncClient, auth_headers):
    """cancelled_by_target 状态的成员必须出现在 /api/family/members 列表中。"""
    # 先添加 2 个家人（加上自动创建的本人，应共 3 个）
    r1 = await client.post(
        "/api/family/members",
        json={
            "relationship_type": "parent",
            "name": "父亲",
            "nickname": "父亲",
            "gender": "male",
            "birthday": "1960-01-01",
        },
        headers=auth_headers,
    )
    assert r1.status_code == 200
    member_id_a = r1.json()["id"]

    r2 = await client.post(
        "/api/family/members",
        json={
            "relationship_type": "spouse",
            "name": "配偶",
            "nickname": "配偶",
            "gender": "female",
            "birthday": "1990-01-01",
        },
        headers=auth_headers,
    )
    assert r2.status_code == 200

    # 把第一个成员的状态改为 cancelled_by_target（对方已退出）
    await _set_member_status(member_id_a, "cancelled_by_target")

    # 列表接口必须仍返回 3 个成员（本人 + 2 个家人，含已退出）
    resp = await client.get("/api/family/members", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3, f"expected total=3, got {data['total']}, items={data['items']}"
    ids = [it["id"] for it in data["items"]]
    assert member_id_a in ids, "已退出成员应仍出现在 Tab 列表中"


@pytest.mark.asyncio
async def test_list_members_includes_pending_state(client: AsyncClient, auth_headers):
    """pending（邀请中）等其他非 active/非 deleted 状态成员，必须出现在列表中。"""
    r = await client.post(
        "/api/family/members",
        json={
            "relationship_type": "child",
            "name": "孩子",
            "nickname": "孩子",
            "gender": "male",
            "birthday": "2010-01-01",
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    mid = r.json()["id"]

    await _set_member_status(mid, "pending")

    resp = await client.get("/api/family/members", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = [it["id"] for it in data["items"]]
    assert mid in ids, "pending 状态成员必须出现在 Tab 列表中"


@pytest.mark.asyncio
async def test_list_members_excludes_removed(client: AsyncClient, auth_headers):
    """通过 DELETE 接口软删除（status='removed'）的成员必须从列表中排除。"""
    r = await client.post(
        "/api/family/members",
        json={
            "relationship_type": "sibling",
            "name": "兄弟",
            "nickname": "兄弟",
            "gender": "male",
            "birthday": "1985-01-01",
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    mid = r.json()["id"]

    # 调用真实的 DELETE 接口，会把 status 设置为 'removed'
    del_resp = await client.delete(f"/api/family/members/{mid}", headers=auth_headers)
    assert del_resp.status_code == 200

    resp = await client.get("/api/family/members", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = [it["id"] for it in data["items"]]
    assert mid not in ids, "已软删除（removed）的成员必须从 Tab 列表中排除"
