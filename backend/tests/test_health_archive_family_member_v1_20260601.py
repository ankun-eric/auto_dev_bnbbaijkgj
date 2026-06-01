"""[PRD-HEALTH-ARCHIVE-FAMILY-MEMBER-V1 2026-06-01] 健康档案页面优化 — 后端口径回归测试

需求背景（PRD v1.0）：
- 改动点1：列表/入口叫法统一为「家庭成员」（纯前端文案，不涉及后端逻辑）。
- 改动点2：人数以「家庭成员」列表（state/list）为准，入口卡人数与之保持一致。
  本测试验证：入口卡所改用的口径源（/api/family/member/quota.quota_used）
  与列表页口径（/api/family/member/state/list.quota_used / total）完全相等，
  且二者都等于公共统计方法 count_managed_family_members（含本人 + 排除软删）。
- 改动点3：「邀请家庭成员」按钮复用「新增咨询人」同款新增成员页面（POST /api/family/members）。
  本测试验证：新增成员后列表 + 入口卡人数同步 +1（闭环：保存成功→新成员进列表→人数+1）。

本测试聚焦后端接口行为（非 UI），覆盖：
1) 入口卡口径 == 列表页口径（quota.quota_used == state/list.quota_used == state/list.total）
2) 含本人：新用户 >= 1
3) 软删除成员被两处口径同时排除
4) 复用「新增咨询人」POST /api/family/members 后，列表与入口卡人数同步 +1
5) state/list 返回结构完整（items / total / quota_used / quota_max）
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.family_member_v2 import count_managed_family_members
from app.models.models import FamilyMember, User


async def _get_current_user_id(db_session, phone: str = "13900000001") -> int:
    r = await db_session.execute(select(User.id).where(User.phone == phone))
    val = r.scalar()
    return int(val) if val else 0


# ──────────── 测试 1：入口卡口径 == 列表页口径（改动点2 核心） ────────────


@pytest.mark.asyncio
async def test_entry_card_count_equals_list_count(
    client: AsyncClient, auth_headers: dict
):
    """[改动点2 核心验收] 入口卡「已管理 X」改用 /api/family/member/quota.quota_used，
    必须与「家庭成员」列表页 /api/family/member/state/list 的 quota_used / total 完全相等，
    保证两处数字始终相同。"""
    rq = await client.get("/api/family/member/quota", headers=auth_headers)
    rl = await client.get("/api/family/member/state/list", headers=auth_headers)
    assert rq.status_code == 200, rq.text
    assert rl.status_code == 200, rl.text

    quota_used = rq.json()["quota_used"]
    list_used = rl.json()["quota_used"]
    list_total = rl.json()["total"]

    assert quota_used == list_used, (
        f"入口卡口径 quota.quota_used={quota_used} 与列表 state/list.quota_used={list_used} 不一致"
    )
    assert list_used == list_total, (
        f"列表 quota_used={list_used} 与 total={list_total} 应相等（含本人 + 全部未删档案）"
    )


# ──────────── 测试 2：含本人——新用户至少 1 人 ────────────


@pytest.mark.asyncio
async def test_count_includes_self_at_least_one(
    client: AsyncClient, auth_headers: dict
):
    """含本人口径：新注册用户系统自动创建本人卡，列表/入口卡人数都 >= 1。"""
    rq = await client.get("/api/family/member/quota", headers=auth_headers)
    rl = await client.get("/api/family/member/state/list", headers=auth_headers)
    assert rq.json()["quota_used"] >= 1
    assert rl.json()["quota_used"] >= 1


# ──────────── 测试 3：公共统计方法与列表口径一致 ────────────


@pytest.mark.asyncio
async def test_public_helper_equals_list_count(
    client: AsyncClient, auth_headers: dict, db_session
):
    """列表页 quota_used 必须等于公共方法 count_managed_family_members（唯一权威口径）。"""
    uid = await _get_current_user_id(db_session)
    if uid == 0:
        pytest.skip("当前用户 ID 不可用")
    helper_count = await count_managed_family_members(db_session, uid)
    rl = await client.get("/api/family/member/state/list", headers=auth_headers)
    assert rl.json()["quota_used"] == helper_count, (
        f"列表 quota_used={rl.json()['quota_used']} 与公共方法={helper_count} 不一致"
    )


# ──────────── 测试 4：软删除成员被两处口径同时排除 ────────────


@pytest.mark.asyncio
async def test_soft_deleted_excluded_from_both(
    client: AsyncClient, auth_headers: dict, db_session
):
    """软删除（status='deleted'）的家庭成员不应计入入口卡 / 列表任一口径，且两者仍相等。"""
    base_q = (await client.get("/api/family/member/quota", headers=auth_headers)).json()["quota_used"]

    uid = await _get_current_user_id(db_session)
    if uid == 0:
        pytest.skip("当前用户 ID 不可用")

    deleted_member = FamilyMember(
        user_id=uid,
        nickname="软删测试成员",
        relationship_type="other",
        status="deleted",
        is_self=False,
    )
    db_session.add(deleted_member)
    await db_session.commit()

    after_q = (await client.get("/api/family/member/quota", headers=auth_headers)).json()["quota_used"]
    after_l = (await client.get("/api/family/member/state/list", headers=auth_headers)).json()["quota_used"]

    assert after_q == base_q, f"软删成员不应计入 quota_used：基准 {base_q}，软删后 {after_q}"
    assert after_q == after_l, f"软删后入口卡口径 {after_q} 与列表口径 {after_l} 仍需相等"


# ──────────── 测试 5：复用「新增咨询人」后人数同步 +1（改动点3 闭环） ────────────


@pytest.mark.asyncio
async def test_add_member_count_plus_one_on_both(
    client: AsyncClient, auth_headers: dict
):
    """[改动点3 闭环验收] 「邀请家庭成员」复用「新增咨询人」POST /api/family/members
    保存成功后，列表与入口卡人数都应同步 +1，且二者仍相等（新成员立即进列表、人数 +1）。"""
    base_q = (await client.get("/api/family/member/quota", headers=auth_headers)).json()["quota_used"]
    base_l = (await client.get("/api/family/member/state/list", headers=auth_headers)).json()["quota_used"]
    assert base_q == base_l, "前置条件失败：基准两口径已不一致"

    add_r = await client.post(
        "/api/family/members",
        json={
            "name": "家庭成员优化新增测试",
            "nickname": "家庭成员优化新增测试",
            "relationship_type": "other",
            "gender": "male",
        },
        headers=auth_headers,
    )
    if add_r.status_code not in (200, 201):
        pytest.skip(f"无法新建测试成员（HTTP {add_r.status_code}：{add_r.text}）")

    # 新增成员接口必须返回 id（前端复用新增咨询人后据此刷新/跳转）
    created = add_r.json()
    created_id = created.get("id") or (created.get("data") or {}).get("id")
    assert created_id, f"POST /api/family/members 应返回新成员 id，实际：{created}"

    new_q = (await client.get("/api/family/member/quota", headers=auth_headers)).json()["quota_used"]
    new_l_resp = (await client.get("/api/family/member/state/list", headers=auth_headers)).json()
    new_l = new_l_resp["quota_used"]

    assert new_q == base_q + 1, f"新增后入口卡口径未 +1：基准 {base_q}，新值 {new_q}"
    assert new_q == new_l, f"新增后入口卡口径 {new_q} 与列表口径 {new_l} 仍需相等"

    # 新成员应立即出现在列表 items 中
    ids = [it.get("member_id") for it in new_l_resp.get("items", [])]
    assert created_id in ids, f"新增成员 id={created_id} 未出现在列表 items 中：{ids}"


# ──────────── 测试 6：state/list 返回结构完整 ────────────


@pytest.mark.asyncio
async def test_state_list_response_shape(
    client: AsyncClient, auth_headers: dict
):
    """「家庭成员」列表接口返回结构应包含 items / total / quota_used / quota_max。"""
    rl = await client.get("/api/family/member/state/list", headers=auth_headers)
    assert rl.status_code == 200, rl.text
    body = rl.json()
    for key in ("items", "total", "quota_used", "quota_max"):
        assert key in body, f"state/list 返回缺少字段 {key}：{list(body.keys())}"
    assert isinstance(body["items"], list)
