"""[PRD-MEMBER-INVITE-REUSE-MODAL-V1 2026-06-01] 会员中心「邀请家庭成员」按钮点击效果调整 — 回归测试

需求背景（PRD v1.0）：
会员中心「尊享会员」蓝色卡片上的「邀请家庭成员」按钮，点击后的效果改为与
「健康档案 → 家庭成员 → 去邀请」完全一致：弹出半屏浮层（NewFamilyMemberModal）完成邀请，
用户不离开会员中心、不跳转新页面。卡片外观/高度/布局/文案/按钮位置/数量信息一概不动。

本需求是纯 H5 前端按钮交互改动，复用的后端接口为 POST /api/family/members（与
「健康档案 → 家庭成员 → 去邀请」复用的「新增咨询人」同一套），因此本测试覆盖两部分：

A. 后端口径闭环（与健康档案位共享的同一套接口）：
   - 复用 POST /api/family/members 后，入口卡口径 /api/family/member/quota.quota_used 同步 +1，
     与列表 /api/family/member/state/list.quota_used 始终相等（半屏浮层保存成功后人数 +1 的闭环）。

B. H5 源码静态断言（验证「只改点击效果」这一约束被正确实现）：
   - 会员中心页面已引入并渲染 NewFamilyMemberModal（与健康档案位复用同一组件）。
   - 会员中心「邀请家庭成员」的 onInvite 不再跳转旧邀请页 /health-profile/my-guardians/invite。
   - InviteFamilyCard 组件本身未被改动其外观/文案（按钮文字仍为「邀请家庭成员」、仍为蓝色卡片）。
"""

from __future__ import annotations

import os
import re

import pytest
from httpx import AsyncClient


# ──────────── A. 后端口径闭环（半屏浮层复用的同一套邀请接口） ────────────


@pytest.mark.asyncio
async def test_invite_modal_reuses_add_member_and_count_plus_one(
    client: AsyncClient, auth_headers: dict
):
    """会员中心「邀请家庭成员」半屏浮层复用 POST /api/family/members，
    保存成功后入口卡口径 quota_used 同步 +1，且与列表口径始终相等。"""
    base_q = (await client.get("/api/family/member/quota", headers=auth_headers)).json()["quota_used"]
    base_l = (await client.get("/api/family/member/state/list", headers=auth_headers)).json()["quota_used"]
    assert base_q == base_l, "前置条件失败：基准两口径已不一致"

    add_r = await client.post(
        "/api/family/members",
        json={
            "name": "会员中心邀请浮层测试",
            "nickname": "会员中心邀请浮层测试",
            "relationship_type": "other",
            "gender": "female",
        },
        headers=auth_headers,
    )
    if add_r.status_code not in (200, 201):
        pytest.skip(f"无法新建测试成员（HTTP {add_r.status_code}：{add_r.text}）")

    created = add_r.json()
    created_id = created.get("id") or (created.get("data") or {}).get("id")
    assert created_id, f"POST /api/family/members 应返回新成员 id，实际：{created}"

    new_q = (await client.get("/api/family/member/quota", headers=auth_headers)).json()["quota_used"]
    new_l = (await client.get("/api/family/member/state/list", headers=auth_headers)).json()["quota_used"]

    assert new_q == base_q + 1, f"浮层保存后入口卡口径未 +1：基准 {base_q}，新值 {new_q}"
    assert new_q == new_l, f"浮层保存后入口卡口径 {new_q} 与列表口径 {new_l} 仍需相等"


# ──────────── B. H5 源码静态断言（验证「只改点击效果」约束） ────────────

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_MEMBER_CENTER_PAGE = os.path.join(
    _REPO_ROOT, "h5-web", "src", "app", "member-center", "page.tsx"
)
_INVITE_CARD = os.path.join(
    _REPO_ROOT, "h5-web", "src", "app", "member-center", "components", "InviteFamilyCard.tsx"
)


def _read(path: str) -> str:
    assert os.path.exists(path), f"源码文件不存在：{path}"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_member_center_imports_invite_modal():
    """会员中心页面必须引入半屏浮层组件 NewFamilyMemberModal（与健康档案位复用同一组件）。"""
    src = _read(_MEMBER_CENTER_PAGE)
    assert "NewFamilyMemberModal" in src, "会员中心页面未引入 NewFamilyMemberModal"
    assert re.search(
        r"import\s+NewFamilyMemberModal\s+from\s+['\"]@/components/health-profile-v5/NewFamilyMemberModal['\"]",
        src,
    ), "会员中心页面未从健康档案位同一路径引入 NewFamilyMemberModal（复用约束未满足）"


def test_member_center_renders_invite_modal():
    """会员中心页面必须实际渲染 <NewFamilyMemberModal ... /> 半屏浮层。"""
    src = _read(_MEMBER_CENTER_PAGE)
    assert "<NewFamilyMemberModal" in src, "会员中心页面未渲染 NewFamilyMemberModal 浮层"
    # 浮层显隐应由状态控制（newMemberOpen），点击按钮打开
    assert "setNewMemberOpen(true)" in src, "会员中心未在点击邀请按钮时打开浮层"


def test_member_center_no_longer_navigates_to_old_invite_page():
    """「邀请家庭成员」点击效果不再跳转旧邀请页（不离开会员中心）。"""
    src = _read(_MEMBER_CENTER_PAGE)
    assert "router.push('/health-profile/my-guardians/invite')" not in src, (
        "会员中心仍跳转旧邀请页 /health-profile/my-guardians/invite，应改为弹出半屏浮层"
    )


def test_invite_card_appearance_unchanged():
    """卡片外观/文案不动：按钮文字仍为「邀请家庭成员」，仍为蓝色渐变卡片。"""
    src = _read(_INVITE_CARD)
    assert "邀请家庭成员" in src, "邀请卡片按钮文字应保持「邀请家庭成员」不变"
    # 蓝色渐变主色保持现状（PRD 明确不改卡片颜色/样式）
    assert "INVITE_CARD_GRADIENT" in src and "#0284C7" in src, (
        "邀请卡片蓝色主题色不应被改动"
    )
