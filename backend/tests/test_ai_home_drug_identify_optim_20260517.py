"""[BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517] ai-home 用药识别功能优化 — 非UI自动化测试。

对应 PRD 的 4 个 Bug：
  Bug-1：流式输出体验（两段播报型文案）
  Bug-2：识药卡片内容增强（4 模块）+ 个性化风险结论
  Bug-3：对话历史完整保留 + 已加入用药计划状态持久化
  Bug-4：时区规范（接口返回带 UTC 标识，前端"刚刚"不再误显示 8 小时前）

并附加：
  - 会话超时默认值 60 分钟
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import ChatMessage, ChatSession, MessageRole, MessageType, SessionType, User


# ──────────────────────────────────────────────────────────────────────────
# Bug 4 · 时区规范
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bug4_chat_session_isoformat_includes_utc_timezone(
    client: AsyncClient, auth_headers, db_session
):
    """[Bug-4] /api/chat/sessions 列表返回的 created_at / updated_at 必须带 UTC 时区标识，
    否则前端按本地时区误解析会把"刚刚创建"显示为"8 小时前"。
    """
    res = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "title": "时区测试"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text

    list_res = await client.get("/api/chat/sessions", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json().get("items") or []
    assert items, "至少应当有 1 个会话"

    s = items[0]
    assert isinstance(s["created_at"], str)
    assert isinstance(s["updated_at"], str)
    # 必须带 +00:00 或 Z 时区后缀
    assert re.search(r"(\+00:00|Z)$", s["created_at"]), (
        f"created_at 必须带 UTC 时区标识，当前：{s['created_at']}"
    )
    assert re.search(r"(\+00:00|Z)$", s["updated_at"]), (
        f"updated_at 必须带 UTC 时区标识，当前：{s['updated_at']}"
    )


@pytest.mark.asyncio
async def test_bug4_chat_session_detail_isoformat_includes_utc_timezone(
    client: AsyncClient, auth_headers, db_session
):
    """[Bug-4] /api/chat/sessions/{id} 详情接口的 created_at / updated_at 同样要带 UTC 后缀。"""
    res = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "title": "时区详情"},
        headers=auth_headers,
    )
    sid = res.json().get("id") or res.json().get("data", {}).get("id")
    assert sid, f"创建会话未返回 id：{res.text}"

    detail = await client.get(f"/api/chat/sessions/{sid}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert re.search(r"(\+00:00|Z)$", body["created_at"])
    assert re.search(r"(\+00:00|Z)$", body["updated_at"])


@pytest.mark.asyncio
async def test_bug4_recent_session_is_just_now_not_8h_ago(
    client: AsyncClient, auth_headers, db_session
):
    """[Bug-4 关键回归] 创建会话后立即读取，created_at 解析为 UTC 后与当前 UTC 差值必须 < 1 分钟。
    旧实现因 isoformat() 不带时区，前端按本地时区解析会偏移 8 小时（导致显示"8 小时前"）。
    """
    res = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "title": "刚刚"},
        headers=auth_headers,
    )
    sid = res.json().get("id") or res.json().get("data", {}).get("id")
    detail = await client.get(f"/api/chat/sessions/{sid}", headers=auth_headers)
    created = datetime.fromisoformat(detail.json()["created_at"])
    # 与当前 UTC 时间差距应 < 1 分钟（不能是 8 小时）
    now_utc = datetime.now()
    delta_sec = abs((now_utc - created).total_seconds())
    assert delta_sec < 60, f"created_at 与当前时间差距过大：{delta_sec}s，可能存在时区 Bug"


# ──────────────────────────────────────────────────────────────────────────
# Bug 3 · "已加入用药计划"状态持久化
# ──────────────────────────────────────────────────────────────────────────


async def _create_drug_identify_message(db_session, user_id: int) -> int:
    """直接在 DB 里塞一条 drug_identify_card 类型的 assistant 消息，
    模拟用户走完拍照识药流程后的持久化结果。"""
    sess = ChatSession(
        user_id=user_id,
        session_type=SessionType.health_qa,
        title="拍照识药测试",
    )
    db_session.add(sess)
    await db_session.flush()

    msg = ChatMessage(
        session_id=sess.id,
        role=MessageRole.assistant,
        content="正在识别图片中的药品… 已读取药盒文字…",
        message_type=MessageType.text,
        message_metadata={
            "message_type": "drug_identify_card",
            "medicines": [{"name": "瑞舒伐他汀钙片", "brand": "可定"}],
            "family_member_id": None,
            "member_name": "您",
        },
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.commit()
    return msg.id


@pytest.mark.asyncio
async def test_bug3_mark_added_to_plan_persists_to_metadata(
    client: AsyncClient, auth_headers, db_session
):
    """[Bug-3] POST /api/chat/messages/{id}/mark-added-to-plan 应把 added_to_plan=True
    写入 ChatMessage.message_metadata，刷新页面后仍能读回。"""
    user_res = await db_session.execute(select(User).where(User.phone == "13900000001"))
    user = user_res.scalar_one()
    msg_id = await _create_drug_identify_message(db_session, user.id)

    r = await client.post(
        f"/api/chat/messages/{msg_id}/mark-added-to-plan",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["added_to_plan"] is True

    # 复查 DB
    refreshed = await db_session.execute(select(ChatMessage).where(ChatMessage.id == msg_id))
    msg = refreshed.scalar_one()
    assert (msg.message_metadata or {}).get("added_to_plan") is True


@pytest.mark.asyncio
async def test_bug3_mark_added_to_plan_rejects_other_user(
    client: AsyncClient, auth_headers, db_session
):
    """[Bug-3] 跨用户调用 mark-added-to-plan 必须 403"""
    # 创建另一个用户的消息
    other = User(phone="13911112222", nickname="他人")
    db_session.add(other)
    await db_session.flush()
    msg_id = await _create_drug_identify_message(db_session, other.id)

    r = await client.post(
        f"/api/chat/messages/{msg_id}/mark-added-to-plan",
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_bug3_message_metadata_returned_in_list_messages(
    client: AsyncClient, auth_headers, db_session
):
    """[Bug-3] GET /api/chat/sessions/{sid}/messages 必须返回 message_metadata，
    前端 loadSessionMessages 才能还原 drugMeta、跨刷新保留识药卡片。"""
    user_res = await db_session.execute(select(User).where(User.phone == "13900000001"))
    user = user_res.scalar_one()
    msg_id = await _create_drug_identify_message(db_session, user.id)

    # 同会话
    sess_res = await db_session.execute(
        select(ChatSession).where(ChatSession.user_id == user.id)
    )
    sess = sess_res.scalar_one()

    r = await client.get(
        f"/api/chat/sessions/{sess.id}/messages",
        headers=auth_headers,
    )
    assert r.status_code == 200
    items = r.json().get("items") or []
    assert items, "应当至少有 1 条消息"
    item = [x for x in items if int(x["id"]) == msg_id][0]
    assert item.get("message_metadata"), "list_messages 必须返回 message_metadata"
    assert item["message_metadata"].get("message_type") == "drug_identify_card"
    assert isinstance(item["message_metadata"].get("medicines"), list)


# ──────────────────────────────────────────────────────────────────────────
# Bug 1 / Bug 2 · 识药引擎流式 + 个性化风险
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bug1_engine_streams_intro_text_before_vision():
    """[Bug-1] run_drug_identify_stream 必须在视觉识别之前先吐出两段播报型文案：
      ① "正在识别图片中的药品…"
      ② "结合 XX 的健康档案…"
    """
    from app.services import drug_identify_engine as eng

    # mock 掉 OCR + 视觉模型 + 档案构建，避免外部依赖
    # OCR 文本必须包含药品名，否则 consistency_score 会被判为 retake
    async def fake_ocr(urls, db):
        return "瑞舒伐他汀钙片 10mg×7s"

    async def fake_profile(db, uid, fmid):
        return {
            "age_group": "成人",
            "gender": "female",
            "chronic_diseases": [],
            "allergies": [],
            "current_medications": [],
            "tcm_constitution": None,
        }

    async def fake_vision(urls, ocr, prof, db):
        return {
            "recognized": True,
            "confidence": 0.95,
            "medicines": [{"name": "瑞舒伐他汀钙片", "manufacturer": "AstraZeneca"}],
            "next_action": "show_card",
            "summary_markdown": "### 瑞舒伐他汀钙片",
            "disclaimer": "仅供参考",
        }

    async def fake_resolve_name(db, uid, fmid):
        return "小明"

    eng._run_ocr_for_urls = fake_ocr  # type: ignore
    eng.build_user_profile_for_drug_identify = fake_profile  # type: ignore
    eng._run_vision_identify = fake_vision  # type: ignore
    eng._resolve_member_display_name = fake_resolve_name  # type: ignore

    deltas = []
    final_meta = None
    final_content = ""
    async for ev in eng.run_drug_identify_stream(
        image_urls=["http://x/a.jpg"],
        ocr_text_hint=None,
        user_id=1,
        family_member_id=2,
        db=None,  # 因所有依赖已 mock
    ):
        if ev["type"] == "delta":
            deltas.append(ev["content"])
        elif ev["type"] == "done":
            final_meta = ev["meta"]
            final_content = ev["content"]

    joined = "".join(deltas)
    # 第一段：极简播报型文案
    assert "正在识别图片中的药品" in joined
    # 第二段：个性化对话型承接（必须包含解析出的成员姓名"小明"）
    assert "结合 小明 的健康档案" in joined
    # done 卡片必须带 personalized_risk
    assert final_meta is not None
    assert final_meta.get("message_type") == "drug_identify_card"
    assert isinstance(final_meta.get("personalized_risk"), dict)
    assert final_meta["personalized_risk"]["level"] in ("safe", "caution", "danger")
    # 终止文本就是流式累计文本（不再额外推 summary）
    assert "正在识别图片中的药品" in final_content


@pytest.mark.asyncio
async def test_bug2_personalized_risk_levels():
    """[Bug-2] _build_personalized_risk 三种风险等级：danger / caution / safe"""
    from app.services.drug_identify_engine import _build_personalized_risk

    drug = {"name": "阿莫西林胶囊", "ingredients": "阿莫西林"}

    # danger：过敏命中
    r1 = _build_personalized_risk(
        drug,
        {"allergies": [{"name": "阿莫西林", "severity": "重度"}], "current_medications": [], "chronic_diseases": []},
    )
    assert r1["level"] == "danger"
    assert "不建议" in r1["label"] or "禁忌" in r1["label"] or "不建议服用" in r1["label"]

    # caution：在服药物
    r2 = _build_personalized_risk(
        drug,
        {
            "allergies": [],
            "current_medications": [{"name": "二甲双胍"}],
            "chronic_diseases": [],
        },
    )
    assert r2["level"] == "caution"

    # caution：老年人
    r3 = _build_personalized_risk(
        drug,
        {
            "allergies": [],
            "current_medications": [],
            "chronic_diseases": [],
            "age_group": "老年人",
        },
    )
    assert r3["level"] == "caution"

    # safe：无任何风险点
    r4 = _build_personalized_risk(
        drug,
        {
            "allergies": [],
            "current_medications": [],
            "chronic_diseases": [],
            "age_group": "成人",
        },
    )
    assert r4["level"] == "safe"


# ──────────────────────────────────────────────────────────────────────────
# 会话超时默认 60 分钟
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_session_idle_timeout_default_is_60_minutes():
    """[需求 §4] 默认空闲超时 60 分钟（旧值 30）"""
    from app.schemas.ai_home_config import SessionConfig

    sc = SessionConfig()
    assert sc.idle_timeout_minutes == 60
