"""[PRD-MSG-CENTER-UNIFY-V1 2026-06-02] 统一消息中心 · 铃铛单入口合并 测试。

需求一句话：主页只留一个铃铛入口，把「今日待办」和「系统通知」合并到这一个入口里；
同时修好系统通知「红色加载失败」的 Bug，把后台三套接口收敛成一套（统一到 /api/messages/*）。

本次为 H5 + 后端接口收敛（后端 /api/messages/* 接口集已存在，本次复用并验证；
H5 停止调用 /api/v1/notifications/* 与 /api/notifications/*，小程序仍可用故后端接口保留）。

测试分两部分：
  任务 A —— 后端统一接口 /api/messages/* 行为全覆盖（列表分页/未读计数/单条已读/全部已读/权限）
  任务 B —— H5 前端源码静态断言（入口唯一化 / 接口收敛 / 铃铛抽屉合并待办+通知分段）
"""
from __future__ import annotations

import os
import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import SystemMessage, User

# conftest 中 user_token 注册的用户手机号
USER_PHONE = "13900000001"


# ──────────────────────── 辅助 ────────────────────────

async def _get_user_id(phone: str) -> int:
    from tests.conftest import test_session
    async with test_session() as session:
        res = await session.execute(select(User).where(User.phone == phone))
        u = res.scalar_one_or_none()
        assert u is not None, f"未找到用户 {phone}"
        return u.id


async def _seed_messages(recipient_id: int, items: list[dict]):
    from tests.conftest import test_session
    async with test_session() as session:
        for it in items:
            session.add(SystemMessage(
                message_type=it.get("message_type", "system"),
                recipient_user_id=recipient_id,
                title=it.get("title", "标题"),
                content=it.get("content", "内容"),
                is_read=it.get("is_read", False),
                click_action=it.get("click_action"),
                click_action_params=it.get("click_action_params"),
            ))
        await session.commit()


# ════════════════════════ 任务 A：后端 /api/messages/* 行为 ════════════════════════

# TC-A1 列表：正常返回 + 分页结构
@pytest.mark.asyncio
async def test_messages_list_pagination_structure(client: AsyncClient, user_token, auth_headers):
    uid = await _get_user_id(USER_PHONE)
    await _seed_messages(uid, [
        {"title": f"通知{i}", "content": f"内容{i}", "message_type": "system"}
        for i in range(25)
    ])
    resp = await client.get("/api/messages", params={"page": 1, "page_size": 20}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 分页结构：items / total / page / page_size
    assert set(["items", "total", "page", "page_size"]).issubset(data.keys())
    assert data["total"] == 25
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert len(data["items"]) == 20
    # 第二页
    resp2 = await client.get("/api/messages", params={"page": 2, "page_size": 20}, headers=auth_headers)
    assert resp2.status_code == 200
    assert len(resp2.json()["items"]) == 5


# TC-A2 列表：空列表（无消息）
@pytest.mark.asyncio
async def test_messages_list_empty(client: AsyncClient, user_token, auth_headers):
    resp = await client.get("/api/messages", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


# TC-A3 列表：按 message_type 过滤
@pytest.mark.asyncio
async def test_messages_list_filter_by_type(client: AsyncClient, user_token, auth_headers):
    uid = await _get_user_id(USER_PHONE)
    await _seed_messages(uid, [
        {"title": "系统", "message_type": "system"},
        {"title": "健康预警", "message_type": "health_alert"},
        {"title": "家人邀请", "message_type": "family_invite"},
    ])
    resp = await client.get("/api/messages", params={"message_type": "health_alert"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["message_type"] == "health_alert"


# TC-A4 未读计数：与列表未读数一致（根治红点≠列表）
@pytest.mark.asyncio
async def test_messages_unread_count_matches_list(client: AsyncClient, user_token, auth_headers):
    uid = await _get_user_id(USER_PHONE)
    await _seed_messages(uid, [
        {"title": "未读1", "is_read": False},
        {"title": "未读2", "is_read": False},
        {"title": "已读1", "is_read": True},
    ])
    resp = await client.get("/api/messages/unread-count", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "unread_count" in body
    assert body["unread_count"] == 2
    # 与列表里 is_read=False 的条目数一致
    lst = await client.get("/api/messages", params={"page": 1, "page_size": 100}, headers=auth_headers)
    unread_in_list = sum(1 for x in lst.json()["items"] if not x["is_read"])
    assert unread_in_list == body["unread_count"]


# TC-A5 单条已读
@pytest.mark.asyncio
async def test_messages_mark_single_read(client: AsyncClient, user_token, auth_headers):
    uid = await _get_user_id(USER_PHONE)
    await _seed_messages(uid, [{"title": "待读", "is_read": False}])
    lst = await client.get("/api/messages", headers=auth_headers)
    mid = lst.json()["items"][0]["id"]
    resp = await client.put(f"/api/messages/{mid}/read", headers=auth_headers)
    assert resp.status_code == 200
    after = await client.get("/api/messages/unread-count", headers=auth_headers)
    assert after.json()["unread_count"] == 0


# TC-A6 单条已读：不存在的消息 404
@pytest.mark.asyncio
async def test_messages_mark_read_not_found(client: AsyncClient, user_token, auth_headers):
    resp = await client.put("/api/messages/99999999/read", headers=auth_headers)
    assert resp.status_code == 404


# TC-A7 全部已读
@pytest.mark.asyncio
async def test_messages_mark_all_read(client: AsyncClient, user_token, auth_headers):
    uid = await _get_user_id(USER_PHONE)
    await _seed_messages(uid, [
        {"title": "未读A", "is_read": False},
        {"title": "未读B", "is_read": False},
        {"title": "未读C", "is_read": False},
    ])
    resp = await client.put("/api/messages/read-all", headers=auth_headers)
    assert resp.status_code == 200
    after = await client.get("/api/messages/unread-count", headers=auth_headers)
    assert after.json()["unread_count"] == 0


# TC-A8 权限：未带 token 拒绝
@pytest.mark.asyncio
async def test_messages_requires_auth(client: AsyncClient):
    resp = await client.get("/api/messages")
    assert resp.status_code in (401, 403)
    resp2 = await client.get("/api/messages/unread-count")
    assert resp2.status_code in (401, 403)


# TC-A9 数据隔离：只看自己的消息
@pytest.mark.asyncio
async def test_messages_isolated_per_user(client: AsyncClient, user_token, auth_headers):
    # 另注册一个用户，给他塞消息，确认当前用户看不到
    await client.post("/api/auth/register", json={
        "phone": "13900000099", "password": "user123", "nickname": "另一个用户",
    })
    other_id = await _get_user_id("13900000099")
    await _seed_messages(other_id, [{"title": "别人的消息", "is_read": False}])
    resp = await client.get("/api/messages", headers=auth_headers)
    titles = [x["title"] for x in resp.json()["items"]]
    assert "别人的消息" not in titles


# ════════════════════════ 任务 B：H5 前端源码静态断言 ════════════════════════

def _read(*rel_parts):
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "h5-web", "src", *rel_parts),
        os.path.join("/app", "h5-web", "src", *rel_parts),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return None


def _ai_home():
    return _read("app", "(ai-chat)", "ai-home", "page.tsx")


def _drawer():
    return _read("components", "ai-chat", "ReminderDrawer.tsx")


def _sidebar():
    return _read("components", "ai-chat", "Sidebar.tsx")


# ──── F0：接口收敛到 /api/messages/* ────

def test_b_ai_home_uses_messages_unread_count():
    """[F0-3] ai-home 未读计数改读 /api/messages/unread-count，不再调 /api/v1/notifications/*。"""
    src = _ai_home()
    assert src is not None
    assert "api.get('/api/messages/unread-count')" in src
    # 不再实际调用旧聚合接口（仅允许出现在注释里说明）
    assert "api.get('/api/v1/notifications/unread-count')" not in src


def test_b_sidebar_uses_messages_unread_count():
    """[F0-2/F0-4] Sidebar 铃铛红点改读 /api/messages/unread-count。"""
    src = _sidebar()
    assert src is not None
    assert "api\n      .get('/api/messages/unread-count')" in src or ".get('/api/messages/unread-count')" in src
    assert ".get('/api/v1/notifications/unread-count')" not in src


def test_b_no_h5_calls_to_deprecated_notification_apis():
    """[F0-4] H5 侧不再调用 /api/v1/notifications/* 与 /api/notifications/*（允许注释中提及）。"""
    for src in (_ai_home(), _drawer(), _sidebar()):
        assert src is not None
        # 去掉以 // 开头的注释行后再检测真实调用
        code_lines = [ln for ln in src.splitlines() if not ln.strip().startswith("//") and not ln.strip().startswith("*")]
        code = "\n".join(code_lines)
        assert "api.get('/api/v1/notifications" not in code
        assert "api.get('/api/notifications" not in code
        assert "api.put('/api/notifications" not in code
        assert "api.post('/api/notifications" not in code


# ──── F0-1：旧 /notifications 页删除 + 301 重定向 ────

def test_b_old_notifications_page_deleted():
    """[F0-1] 旧 /notifications 页面源文件已删除。"""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "h5-web", "src", "app", "notifications", "page.tsx"),
        os.path.join("/app", "h5-web", "src", "app", "notifications", "page.tsx"),
    ]
    assert all(not os.path.exists(p) for p in candidates), "旧 /notifications 页应已删除"


def test_b_notifications_redirect_to_messages():
    """[F0-1/§4.1] next.config.js 配置 /notifications 301 永久重定向到 /messages。"""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "h5-web", "next.config.js"),
        os.path.join("/app", "h5-web", "next.config.js"),
    ]
    cfg = None
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                cfg = f.read()
            break
    assert cfg is not None
    flat = re.sub(r"\s+", "", cfg)
    assert "source:'/notifications'" in flat
    assert "destination:'/messages'" in flat
    # 找到 /notifications 这条 redirect 块，确认 permanent:true
    assert re.search(r"source:'/notifications',destination:'/messages',permanent:true", flat), \
        "/notifications → /messages 应为 permanent:true (301)"


# ──── F1：入口唯一化 ────

def test_b_consult_badge_removed():
    """[F1-1/§4.1] 首页「咨询」旁红点徽标已移除（renderUnreadBadge 恒返回 null，不再跳 /messages）。"""
    src = _ai_home()
    assert src is not None
    assert "const renderUnreadBadge = () => null;" in src
    # 原徽标里点击跳 /messages 的行为已移除（旧实现里有 router.push('/messages') 在徽标 onClick 中）
    assert "data-testid=\"ai-home-unread-badge\"" not in src


def test_b_sidebar_bell_no_longer_points_to_notifications():
    """[F1-2] Sidebar 铃铛入口不再指向旧 /notifications（改 /messages）。"""
    src = _sidebar()
    assert src is not None
    assert "navigateTo('/notifications')" not in src
    assert "navigateTo('/messages')" in src


def test_b_topbar_bell_is_unique_entry():
    """[F1-3] 保留并强化首页顶栏右上角 🔔 铃铛为唯一入口。"""
    src = _ai_home()
    assert src is not None
    assert 'data-testid="ai-home-topbar-bell"' in src
    assert "setReminderOpen(true)" in src


# ──── F0-3/§二.4：铃铛红点合并计数 ────

def test_b_bell_badge_merged_count():
    """[§二.4/F0-3] 顶栏铃铛红点 = 待办未完成数(reminderBadge) + 系统通知未读数(unreadCount) 合并求和。"""
    src = _ai_home()
    assert src is not None
    assert "bellMergedCount" in src
    flat = re.sub(r"\s+", "", src)
    # 合并求和定义：reminderBadge + unreadCount
    assert "constbellMergedCount=" in flat
    assert "reminderBadge" in src and "unreadCount" in src
    # 顶栏红点改用合并计数渲染
    assert "{bellMergedCount > 0 &&" in src


# ──── F2：铃铛抽屉合并「待办 / 通知」分段 Tab ────

def test_b_drawer_has_segment_tabs():
    """[F2-1/§4.1] 抽屉顶部分段切换 Tab：待办（默认）/ 通知。"""
    src = _drawer()
    assert src is not None
    assert 'data-testid="bell-drawer-segment"' in src
    # 分段 testid 为模板字面量 `bell-drawer-tab-${seg.key}`，两个 key 为 todo / notice
    assert "data-testid={`bell-drawer-tab-${seg.key}`}" in src
    assert "key: 'todo'" in src and "key: 'notice'" in src
    # 待办默认选中
    assert "useState<DrawerTab>('todo')" in src


def test_b_drawer_todo_panel_keeps_medication_and_orders():
    """[F2-2] 待办分段沿用现有用药 + 订单逻辑与数据源，不改。"""
    src = _drawer()
    assert src is not None
    assert 'data-testid="bell-drawer-todo-panel"' in src
    # 用药 + 订单数据源未动
    assert "/api/medication-plans/today?consultant_id=0" in src
    assert "/api/medication-reminder/appointments" in src
    # SectionHeader 通过 testid 属性传入（渲染为 data-testid）
    assert 'testid="bell-section-medication"' in src
    assert 'testid="bell-section-order"' in src


def test_b_drawer_notice_panel_uses_messages_api():
    """[F2-3] 通知分段接入统一系统通知数据 /api/messages（分页）。"""
    src = _drawer()
    assert src is not None
    assert 'data-testid="bell-drawer-notice-panel"' in src
    assert "api.get('/api/messages'" in src
    assert 'data-testid="bell-notice-row"' in src


def test_b_drawer_notice_click_jump_and_read():
    """[F2-3/F3-2] 通知点击跳详情 + 单条已读 + 全部已读。"""
    src = _drawer()
    assert src is not None
    # 单条已读
    assert "api.put(`/api/messages/${item.id}/read`)" in src
    # 全部已读
    assert "api.put('/api/messages/read-all')" in src
    assert 'data-testid="bell-notice-read-all"' in src
    # 点击跳详情（订单 / 家人绑定 / 邀请页）
    assert "/unified-order/" in src
    assert "/family-bindlist" in src or "/family-invite" in src


def test_b_drawer_title_changes_with_tab():
    """[F2-4] 抽屉标题随当前分段变化：待办事项 (N) / 系统通知 (N)。"""
    src = _drawer()
    assert src is not None
    assert 'data-testid="bell-drawer-title"' in src
    assert "待办事项" in src and "系统通知" in src


# ──── F0-6：加载失败兜底 + 空态区分 ────

def test_b_drawer_notice_error_and_empty_states():
    """[F0-6] 通知分段：加载失败兜底「点击重试」+ 空态与加载失败区分。"""
    src = _drawer()
    assert src is not None
    assert 'data-testid="bell-notice-error"' in src
    assert "加载失败，点击重试" in src
    assert 'data-testid="bell-notice-empty"' in src
    assert "暂无系统通知" in src


# ──── F3：类型图标 / 未读高亮 ────

def test_b_drawer_notice_type_icons_and_unread_dot():
    """[F3-1/F3-2] 通知按类型带图标分组 + 未读高亮 + 未读红点。"""
    src = _drawer()
    assert src is not None
    assert "NOTICE_TYPE_CONFIG" in src
    # 覆盖系统/健康预警/家人邀请/授权/用药等类型
    for t in ("system", "health_alert", "family_invite", "family_auth_granted", "medication_remind"):
        assert t in src, f"通知类型配置应包含 {t}"
    assert 'data-testid="bell-notice-unread-dot"' in src


# ──── 任务标识 ────

def test_b_prd_marker_present():
    """源码带本次任务标识，便于追溯。"""
    for src in (_ai_home(), _drawer(), _sidebar()):
        assert src is not None
        assert "PRD-MSG-CENTER-UNIFY-V1" in src
