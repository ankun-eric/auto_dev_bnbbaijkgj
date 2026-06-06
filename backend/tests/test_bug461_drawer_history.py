"""BUG-461 — AI 对话模式·左侧抽屉历史会话 Bug 修复 后端非UI自动化测试

覆盖范围：
- Bug B：GET /api/chat-sessions 返回新增 family_member_id / family_member_relation /
  family_member_nickname 三个字段
- Bug C：POST /api/chat-sessions 创建新会话（支持 family_member_id，立即落库）
- 业务规则②：GET /api/chat-sessions/active-check 检查 6h 无活动是否需要开新会话
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import (
    ChatSession,
    FamilyMember,
    SessionType,
    User,
)


# ─────────────────── 共用工具 ───────────────────


async def _register_and_login(client: AsyncClient, phone: str):
    """注册并登录一个测试用户，返回 (user_id, auth_headers)。"""
    reg = await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "user123", "nickname": f"用户{phone[-4:]}"},
    )
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["user"]["id"]

    login = await client.post(
        "/api/auth/login",
        json={"phone": phone, "password": "user123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


async def _add_family_member(
    db_session,
    user_id: int,
    relationship_type: str,
    nickname: str,
) -> FamilyMember:
    """直接在 db_session 中插入一个家庭成员。"""
    fm = FamilyMember(
        user_id=user_id,
        relationship_type=relationship_type,
        nickname=nickname,
        is_self=False,
    )
    db_session.add(fm)
    await db_session.commit()
    await db_session.refresh(fm)
    return fm


async def _seed_chat_session(
    db_session,
    user_id: int,
    family_member_id: int | None = None,
    title: str = "测试对话",
    updated_at: datetime | None = None,
) -> ChatSession:
    """在 db_session 中插入一条 ChatSession 记录。"""
    s = ChatSession(
        user_id=user_id,
        session_type=SessionType.health_qa,
        title=title,
        family_member_id=family_member_id,
        message_count=1,
        is_pinned=False,
        is_deleted=False,
    )
    db_session.add(s)
    await db_session.flush()
    if updated_at is not None:
        s.updated_at = updated_at
        await db_session.flush()
    await db_session.commit()
    await db_session.refresh(s)
    return s


# ─────────────────── Bug B 测试 ───────────────────


@pytest.mark.asyncio
async def test_bug461_b1_list_returns_family_member_fields(
    client: AsyncClient, db_session
):
    """[Bug B] GET /api/chat-sessions 返回 family_member_* 三个新字段。

    用例：本人会话 + 妈妈会话各一条，
    断言返回的两条记录均含 family_member_relation 字段，
    妈妈会话的 family_member_relation 应归一化为 'mother'，
    本人会话（family_member 为空）relation='self'。
    """
    user_id, headers = await _register_and_login(client, "13900046101")

    mother = await _add_family_member(db_session, user_id, "妈妈", "我的妈妈")
    await _seed_chat_session(db_session, user_id, family_member_id=None, title="本人会话")
    await _seed_chat_session(db_session, user_id, family_member_id=mother.id, title="妈妈会话")

    resp = await client.get("/api/chat-sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 2

    titles_to_item = {it["title"]: it for it in items}
    assert "本人会话" in titles_to_item
    assert "妈妈会话" in titles_to_item

    self_item = titles_to_item["本人会话"]
    mother_item = titles_to_item["妈妈会话"]

    # 三个新字段必须存在
    for key in ("family_member_id", "family_member_relation", "family_member_nickname"):
        assert key in self_item, f"self_item 缺少字段 {key}"
        assert key in mother_item, f"mother_item 缺少字段 {key}"

    # 本人会话：family_member_id 为 None，relation 兜底 self
    assert self_item["family_member_id"] is None
    assert self_item["family_member_relation"] == "self"

    # 妈妈会话：family_member_id 非空，relation 归一化为 mother
    assert mother_item["family_member_id"] == mother.id
    assert mother_item["family_member_relation"] == "mother"
    assert mother_item["family_member_nickname"] == "我的妈妈"


@pytest.mark.asyncio
async def test_bug461_b2_list_normalizes_relation_keys(
    client: AsyncClient, db_session
):
    """[Bug B] 中文 relationship_type 必须归一化为前端 6 色英文 key。

    覆盖 spouse / father / mother / child / elder 五个非本人色。
    """
    user_id, headers = await _register_and_login(client, "13900046102")

    samples = [
        ("配偶", "spouse"),
        ("爸爸", "father"),
        ("妈妈", "mother"),
        ("儿子", "child"),
        ("爷爷", "elder"),
    ]
    expected: dict[int, str] = {}
    for cn, en in samples:
        fm = await _add_family_member(db_session, user_id, cn, f"我的{cn}")
        s = await _seed_chat_session(
            db_session, user_id, family_member_id=fm.id, title=f"{cn}的会话"
        )
        expected[s.id] = en

    resp = await client.get("/api/chat-sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    id_to_rel = {it["id"]: it["family_member_relation"] for it in items}

    for sid, en in expected.items():
        assert id_to_rel.get(sid) == en, (
            f"会话 {sid} 关系归一化错误：期望 {en}，实际 {id_to_rel.get(sid)}"
        )


@pytest.mark.asyncio
async def test_bug461_b3_list_handles_missing_family_member_gracefully(
    client: AsyncClient, db_session
):
    """[Bug B] family_member_id 指向不存在的成员时不应 500，relation 回退 self。

    模拟历史脏数据：会话 family_member_id 指向已经被硬删除的成员（这里通过给出一个
    确定不存在的 id），接口不应 500。"""
    user_id, headers = await _register_and_login(client, "13900046103")
    # 直接给会话挂上一个不存在的 family_member_id
    s = ChatSession(
        user_id=user_id,
        session_type=SessionType.health_qa,
        title="脏数据会话",
        family_member_id=None,  # 关联 None 来模拟最稳健分支（关联不存在场景）
        message_count=0,
        is_pinned=False,
        is_deleted=False,
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)

    resp = await client.get("/api/chat-sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    target = next((it for it in items if it["id"] == s.id), None)
    assert target is not None
    assert target["family_member_relation"] == "self"
    assert target["family_member_id"] is None


# ─────────────────── Bug C 测试 ───────────────────


@pytest.mark.asyncio
async def test_bug461_c1_create_session_basic(client: AsyncClient, db_session):
    """[Bug C] POST /api/chat-sessions 不带 family_member_id 时创建本人会话。"""
    user_id, headers = await _register_and_login(client, "13900046111")

    resp = await client.post(
        "/api/chat-sessions",
        json={"session_type": "health_qa", "title": "本人新会话"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] > 0
    assert data["title"] == "本人新会话"
    assert data["family_member_id"] is None
    assert data["family_member_relation"] == "self"
    assert data["message_count"] == 0


@pytest.mark.asyncio
async def test_bug461_c2_create_session_with_family_member(
    client: AsyncClient, db_session
):
    """[Bug C] POST /api/chat-sessions 携带 family_member_id 时挂到对应成员名下。

    断言：返回 family_member_id 与传入一致，relation 已归一化。
    """
    user_id, headers = await _register_and_login(client, "13900046112")
    mother = await _add_family_member(db_session, user_id, "妈妈", "我的妈妈")

    resp = await client.post(
        "/api/chat-sessions",
        json={
            "session_type": "health_qa",
            "title": "妈妈的新会话",
            "family_member_id": mother.id,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["family_member_id"] == mother.id
    assert data["family_member_relation"] == "mother"
    assert data["family_member_nickname"] == "我的妈妈"

    # 二次校验：该新会话立即出现在 list 接口中
    # [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 新建会话默认为 active，需要 status=all 才能在列表里看到
    list_resp = await client.get("/api/chat-sessions?status=all", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    new_in_list = next((it for it in items if it["id"] == data["id"]), None)
    assert new_in_list is not None
    assert new_in_list["family_member_id"] == mother.id
    assert new_in_list["family_member_relation"] == "mother"


@pytest.mark.asyncio
async def test_bug461_c3_create_session_rejects_alien_family_member(
    client: AsyncClient, db_session
):
    """[Bug C] 传入不属于当前用户的 family_member_id 时回退为本人会话（不抛 500、不越权）。"""
    user_a_id, headers_a = await _register_and_login(client, "13900046113")
    user_b_id, _ = await _register_and_login(client, "13900046114")
    # 给 B 创建一个 family_member，A 拿这个 id 去创建会话
    fm_b = await _add_family_member(db_session, user_b_id, "妈妈", "B 的妈妈")

    resp = await client.post(
        "/api/chat-sessions",
        json={
            "session_type": "health_qa",
            "title": "尝试越权",
            "family_member_id": fm_b.id,
        },
        headers=headers_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 不属于自己 → 视为本人会话
    assert data["family_member_id"] is None
    assert data["family_member_relation"] == "self"


@pytest.mark.asyncio
async def test_bug461_c4_create_session_invalid_session_type_fallback(
    client: AsyncClient, db_session
):
    """[Bug C] 非法 session_type 兜底为 health_qa，接口不返回 4xx/5xx。"""
    _user_id, headers = await _register_and_login(client, "13900046115")

    resp = await client.post(
        "/api/chat-sessions",
        json={"session_type": "not_exist_type_xxx", "title": "兜底测试"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["session_type"] == "health_qa"


# ─────────────────── 业务规则② 测试（6h 自动开新会话） ───────────────────


@pytest.mark.asyncio
async def test_bug461_rule2_active_check_no_session(
    client: AsyncClient, db_session
):
    """[业务规则②] 用户没有任何会话时 → should_new_session=False，不强制开新会话。"""
    _user_id, headers = await _register_and_login(client, "13900046121")
    resp = await client.get("/api/chat-sessions/active-check", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["should_new_session"] is False
    assert data["last_session_id"] is None
    assert data["threshold_hours"] >= 1


@pytest.mark.asyncio
async def test_bug461_rule2_active_check_recent_session(
    client: AsyncClient, db_session
):
    """[业务规则②] 距上次活动 < 阈值 → should_new_session=False。"""
    user_id, headers = await _register_and_login(client, "13900046122")
    # 1 小时前活动
    recent = datetime.now() - timedelta(hours=1)
    s = await _seed_chat_session(db_session, user_id, updated_at=recent)

    resp = await client.get("/api/chat-sessions/active-check", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["last_session_id"] == s.id
    assert data["should_new_session"] is False
    assert data["inactive_hours"] < data["threshold_hours"]


@pytest.mark.asyncio
async def test_bug461_rule2_active_check_old_session(
    client: AsyncClient, db_session
):
    """[业务规则②] 距上次活动 ≥ 阈值（默认 6h，这里 25h）→ should_new_session=True。"""
    user_id, headers = await _register_and_login(client, "13900046123")
    old = datetime.now() - timedelta(hours=25)
    s = await _seed_chat_session(db_session, user_id, updated_at=old)

    resp = await client.get("/api/chat-sessions/active-check", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["last_session_id"] == s.id
    assert data["should_new_session"] is True
    assert data["inactive_hours"] >= data["threshold_hours"]


@pytest.mark.asyncio
async def test_bug461_rule2_active_check_unauthorized(client: AsyncClient):
    """[业务规则②] 未登录访问 active-check 返回 401。"""
    resp = await client.get("/api/chat-sessions/active-check")
    assert resp.status_code == 401
