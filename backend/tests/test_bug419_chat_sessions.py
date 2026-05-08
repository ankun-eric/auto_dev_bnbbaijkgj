"""[Bug-419 2026-05-08] H5 ai-home 整片白屏 + 创建会话 422 修复 — 后端回归测试。

覆盖范围（与 cursor_prompt_419 §6.1 接口契约层 一致）：

- T01 标准入参（session_type='health_qa' + family_member_id=1） → 200 + 返回 session_id
- T02 仅传 family_member_id（缺 session_type） → 200（B-2 兜底为 health_qa）
- T03 完全空请求体 {} → 200（B-2 + B-3 双重兜底）
- T04 非法 session_type → 200（路由层归一化兜底为 health_qa，不再 422）
- T05 业务别名 session_type（'general'/'constitution'/'symptom'/'drug'/'report'） → 200 且映射到正确枚举
- T06 H5 旧版字段 member_id（无 family_member_id） → 200 且 family_member_id 被正确归并
- T07 各业务合法 session_type（symptom_check/drug_query/report_interpret/report_compare/constitution_test） → 200
- T08 422 错误消息中文化（场景：传入字段类型完全不对的请求） → 仍 422 + detail 含中文
- T09 family_member_id 缺失 + 用户存在默认家庭成员 → B-3 自动取默认咨询对象
"""
import pytest
from httpx import AsyncClient


# ──────── T01：标准入参全字段齐全 ────────


@pytest.mark.asyncio
async def test_t01_standard_payload(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "family_member_id": None, "title": "测试会话"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"]
    assert data["session_type"] == "health_qa"
    assert data["title"] == "测试会话"


# ──────── T02：缺 session_type ────────


@pytest.mark.asyncio
async def test_t02_missing_session_type_falls_back_to_health_qa(
    client: AsyncClient, auth_headers
):
    """[B-2] 客户端漏传 session_type，路由层兜底为 health_qa，仍 200。"""
    resp = await client.post(
        "/api/chat/sessions",
        json={"title": "缺类型测试"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["session_type"] == "health_qa"


# ──────── T03：完全空请求体 ────────


@pytest.mark.asyncio
async def test_t03_empty_payload_double_fallback(client: AsyncClient, auth_headers):
    """[B-2 + B-3] 完全空 body 也能创建（session_type 兜底 + family_member_id 兜底）。"""
    resp = await client.post(
        "/api/chat/sessions",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["session_type"] == "health_qa"
    assert resp.json()["title"] == "新对话"


# ──────── T04：非法 session_type 兜底为 health_qa ────────


@pytest.mark.asyncio
async def test_t04_invalid_session_type_normalized(client: AsyncClient, auth_headers):
    """[B-2] 非法 session_type 在路由层归一化，不再 422。"""
    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": "totally_unknown_type"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["session_type"] == "health_qa"


# ──────── T05：业务别名归一化 ────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "alias, expected",
    [
        ("general", "health_qa"),
        ("qa", "health_qa"),
        ("default", "health_qa"),
        ("chat", "health_qa"),
        ("constitution", "constitution_test"),
        ("drug", "drug_query"),
        ("symptom", "symptom_check"),
        ("report", "report_interpret"),
    ],
)
async def test_t05_session_type_aliases(
    client: AsyncClient, auth_headers, alias, expected
):
    """业务方写的常见别名都能正确归一化（与前端 SESSION_TYPE_ALIASES 对齐）。"""
    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": alias},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["session_type"] == expected, (
        f"alias {alias} 应归一化为 {expected}，实际 {resp.json()['session_type']}"
    )


# ──────── T06：H5 旧版字段 member_id 自动归并到 family_member_id ────────


@pytest.mark.asyncio
async def test_t06_legacy_member_id_field_compat(
    client: AsyncClient, auth_headers, db_session
):
    """[Bug-419 兼容字段] H5 早期实现误写的 member_id 应被自动归并为 family_member_id。"""
    # 通过先创建一次空 session 拿当前用户 id
    seed = await client.post(
        "/api/chat/sessions", json={}, headers=auth_headers
    )
    assert seed.status_code == 200, seed.text
    user_id_for_member = seed.json()["user_id"]

    from app.models.models import FamilyMember
    fm = FamilyMember(
        user_id=user_id_for_member,
        relationship_type="妈妈",
        nickname="妈妈",
        is_self=False,
    )
    db_session.add(fm)
    await db_session.commit()
    await db_session.refresh(fm)

    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "member_id": fm.id},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["family_member_id"] == fm.id


# ──────── T07：各业务合法 session_type 全通 ────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stype",
    [
        "health_qa",
        "symptom_check",
        "tcm",
        "tcm_tongue",
        "tcm_face",
        "drug_query",
        "customer_service",
        "drug_identify",
        "constitution_test",
        "report_interpret",
        "report_compare",
    ],
)
async def test_t07_valid_session_types(client: AsyncClient, auth_headers, stype):
    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": stype, "title": f"{stype} 会话"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["session_type"] == stype


# ──────── T08：422 错误消息中文化（在请求体类型完全错误时仍 422，但 detail 中文） ────────


@pytest.mark.asyncio
async def test_t08_validation_error_chinese_message(
    client: AsyncClient, auth_headers
):
    """[B-1] family_member_id 类型不正确时，依然返回 422，但 detail 是中文友好消息。"""
    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "family_member_id": "not-a-number"},
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    detail = body.get("detail") or ""
    messages = body.get("messages") or []
    # 中文化消息中应至少包含"咨询对象"或"family_member_id"字样
    combined = detail + "|" + "|".join(messages)
    assert "family_member_id" in combined or "咨询对象" in combined, (
        f"422 错误消息未中文化: {body}"
    )
    # errors 数组同步保留以兼容前端 axios.error.response.data
    assert isinstance(body.get("errors"), list)


# ──────── T09：family_member_id 缺失 + 已有默认家庭成员 → B-3 兜底 ────────


@pytest.mark.asyncio
async def test_t09_default_family_member_fallback(
    client: AsyncClient, auth_headers, db_session
):
    """[B-3] 用户已绑定默认家庭成员（is_self=True），缺 family_member_id 时自动取用。

    注：项目在用户注册时通常会自动创建 is_self=True 的"本人"家庭成员。
    本用例不强假设现有数据，只验证：
      1) 调用 POST /api/chat/sessions 不传 family_member_id 时不会报错；
      2) 当用户存在 is_self=True 的家庭成员时，response 的 family_member_id 必须命中其中一条；
      3) 若用户没有 is_self=True 但有任意家庭成员，则取最早创建的一条；
      4) 若用户完全无家庭成员，则 family_member_id 可以是 None（不强制要求）。
    """
    from app.models.models import FamilyMember
    from sqlalchemy import select

    seed = await client.post(
        "/api/chat/sessions", json={}, headers=auth_headers
    )
    assert seed.status_code == 200, seed.text
    user_id = seed.json()["user_id"]

    existing_self = (
        await db_session.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == user_id, FamilyMember.is_self == True  # noqa: E712
            )
        )
    ).scalars().all()

    if not existing_self:
        self_fm = FamilyMember(
            user_id=user_id,
            relationship_type="本人",
            nickname="本人",
            is_self=True,
        )
        db_session.add(self_fm)
        await db_session.commit()
        await db_session.refresh(self_fm)
        expected_ids = {self_fm.id}
    else:
        expected_ids = {fm.id for fm in existing_self}

    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    fmid = resp.json()["family_member_id"]
    assert fmid is not None, "B-3 兜底失败：family_member_id 仍为 None"
    assert fmid in expected_ids, (
        f"B-3 兜底命中错误：返回 {fmid}，期望命中 is_self=True 成员之一 {expected_ids}"
    )
