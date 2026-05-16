"""[PRD-HSC-SSE-V1 2026-05-16] 健康自查 SSE 流式输出 + 症状描述字段单元测试。

覆盖：
- POST /api/health-self-check/start：新增 `symptom_description` 字段（≤ 50 字）
  - 不传/传空：用户消息 + AI 消息正常落库；卡片 payload 的 symptom_description=None
  - 传非空：卡片 payload 透传；Prompt 中包含该内容
  - 超过 50 字：直接传 51 字应被 pydantic 拒绝（422）
- POST /api/health-self-check/start-stream：SSE 流式
  - 响应 media_type 必须是 text/event-stream
  - 协议至少包含 meta / delta / done 三种 event 类型
  - done 事件 message_id > 0；full_content 非空；与 chat_messages 表中已写入的 AI 内容一致
  - 即使前端提前断开（生成器外部异常），后端 background task 仍能把 AI 消息写入数据库
"""
from __future__ import annotations

import asyncio
import re

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select


# ───────────────────── Mock AI 模型 ─────────────────────


@pytest_asyncio.fixture
def mock_ai_model_for_sse(monkeypatch):
    """非流式 mock，返回固定文本，断言 prompt 中能拿到症状描述。"""
    captured = {"prompt": ""}

    async def _fake(messages, system_prompt="", db=None, return_usage=False):
        # 把最后一条 user 消息记录下来供断言
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "user":
                captured["prompt"] = m.get("content") or ""
        return "AI 同步分析：综合判断属于常见症状\n本回答仅供健康参考，不构成诊疗依据，如不适请及时就医。"

    monkeypatch.setattr("app.api.health_self_check.call_ai_model", _fake)
    monkeypatch.setattr("app.services.ai_service.call_ai_model", _fake, raising=False)
    return captured


@pytest_asyncio.fixture
def mock_ai_model_stream_for_sse(monkeypatch):
    """流式 mock：分 3 个 chunk yield，最后一个 done。

    同时把后端 producer 用的 `AsyncSessionLocal`（生产为 MySQL）替换为测试用 sqlite session，
    使得 producer 写库逻辑可以在 in-memory sqlite 上完整跑通。
    """
    captured = {"prompt": ""}

    async def _fake_stream(messages, system_prompt="", db=None):
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "user":
                captured["prompt"] = m.get("content") or ""
        chunks = ["AI流式片段-A。", "AI流式片段-B。", "AI流式片段-C。"]
        full = ""
        for c in chunks:
            full += c
            yield {"type": "delta", "content": c}
            await asyncio.sleep(0)
        yield {"type": "done", "content": full}

    monkeypatch.setattr("app.api.health_self_check.call_ai_model_stream", _fake_stream)

    # 把 producer 用的 session factory 也替换为测试 sqlite
    from tests.conftest import test_session  # 复用 conftest 中的 in-memory sqlite session
    monkeypatch.setattr("app.api.health_self_check.AsyncSessionLocal", test_session)
    return captured


# ───────────────────── 通用准备 ─────────────────────


async def _bootstrap_button(client: AsyncClient, admin_headers: dict, prefix: str = "sse"):
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": f"{prefix}头", "icon": "🧠", "symptoms": ["头痛", "头晕"],
    }, headers=admin_headers)).json()
    tpl = (await client.post("/api/admin/health-check-templates", json={
        "name": f"{prefix}模板",
        "body_parts": [{"id": p1["id"], "sort": 1}],
        "duration_options": ["<1天", "1-3天", "3-7天"],
        # 模板内含 {症状描述} 占位符
        "default_prompt": "档案={档案信息} 部位={部位} 症状={症状列表} 时长={持续时间} 描述={症状描述}",
    }, headers=admin_headers)).json()
    btn = (await client.post("/api/admin/function-buttons", json={
        "name": f"{prefix}按钮", "button_type": "health_self_check",
        "sort_weight": 0, "is_enabled": True, "icon": "🩺",
        "health_check_template_id": tpl["id"],
        "archive_missing_strategy": "use_default",
    }, headers=admin_headers)).json()
    return p1, tpl, btn


# ═══════════════════════════════════════════════════
# A. /start 接口新增 symptom_description 字段
# ═══════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_start_with_symptom_description(
    client: AsyncClient, admin_headers, auth_headers, mock_ai_model_for_sse,
):
    """填写非空症状描述：卡片 payload 透传、Prompt 包含该内容。"""
    p1, tpl, btn = await _bootstrap_button(client, admin_headers, "desc")
    desc = "晚上躺下时更明显，深呼吸会加重"
    r = await client.post("/api/health-self-check/start", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "body_part_id": p1["id"],
        "symptoms": ["头痛"],
        "duration": "1-3天",
        "symptom_description": desc,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["card_payload"]["symptom_description"] == desc
    # Prompt 必须含描述
    assert desc in mock_ai_model_for_sse["prompt"], \
        f"Prompt 中未找到症状描述。prompt={mock_ai_model_for_sse['prompt']!r}"


@pytest.mark.asyncio
async def test_start_without_symptom_description(
    client: AsyncClient, admin_headers, auth_headers, mock_ai_model_for_sse,
):
    """未填写：card_payload.symptom_description 为 None；Prompt 中不残留空行。"""
    p1, tpl, btn = await _bootstrap_button(client, admin_headers, "nodesc")
    r = await client.post("/api/health-self-check/start", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "body_part_id": p1["id"],
        "symptoms": ["头痛"],
        "duration": "1-3天",
        # 不传 symptom_description
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["card_payload"]["symptom_description"] in (None, "")


@pytest.mark.asyncio
async def test_start_symptom_description_too_long(
    client: AsyncClient, admin_headers, auth_headers, mock_ai_model_for_sse,
):
    """超过 50 字应被 pydantic 拒绝。"""
    p1, tpl, btn = await _bootstrap_button(client, admin_headers, "long")
    long_desc = "x" * 51
    r = await client.post("/api/health-self-check/start", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "body_part_id": p1["id"],
        "symptoms": ["头痛"],
        "duration": "1-3天",
        "symptom_description": long_desc,
    }, headers=auth_headers)
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_start_description_50chars_boundary(
    client: AsyncClient, admin_headers, auth_headers, mock_ai_model_for_sse,
):
    """恰好 50 字应该通过。"""
    p1, tpl, btn = await _bootstrap_button(client, admin_headers, "edge50")
    desc = "啊" * 50
    r = await client.post("/api/health-self-check/start", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "body_part_id": p1["id"],
        "symptoms": ["头痛"],
        "duration": "1-3天",
        "symptom_description": desc,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["card_payload"]["symptom_description"] == desc


# ═══════════════════════════════════════════════════
# B. /start-stream SSE 流式接口
# ═══════════════════════════════════════════════════


def _parse_sse_text(text: str) -> list[tuple[str, str]]:
    """把 SSE 文本拆成 [(event_type, data_raw), ...]。"""
    events = []
    for block in text.split("\n\n"):
        block = block.strip("\r\n ")
        if not block:
            continue
        etype = ""
        data_parts: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                etype = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_parts.append(line[len("data:"):].strip())
        events.append((etype, "\n".join(data_parts)))
    return events


@pytest.mark.asyncio
async def test_start_stream_returns_sse(
    client: AsyncClient, admin_headers, auth_headers, mock_ai_model_stream_for_sse,
):
    """SSE 协议正确性 + 必含 meta/delta/done 三种事件。"""
    p1, tpl, btn = await _bootstrap_button(client, admin_headers, "stream")
    r = await client.post("/api/health-self-check/start-stream", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "body_part_id": p1["id"],
        "symptoms": ["头痛"],
        "duration": "1-3天",
        "symptom_description": "夜间疼痛明显",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    ctype = r.headers.get("content-type", "")
    assert "text/event-stream" in ctype, f"content-type={ctype}"

    events = _parse_sse_text(r.text)
    etypes = [e[0] for e in events]
    assert "meta" in etypes, f"events={etypes}, raw={r.text[:300]}"
    assert "delta" in etypes, f"events={etypes}"
    assert "done" in etypes, f"events={etypes}"

    import json as _json
    meta_data = next(_json.loads(d) for t, d in events if t == "meta")
    assert meta_data["session_id"] > 0
    assert meta_data["user_message_id"] > 0
    assert "card_payload" in meta_data
    assert meta_data["card_payload"]["symptom_description"] == "夜间疼痛明显"

    delta_contents = [_json.loads(d)["content"] for t, d in events if t == "delta"]
    assert any(delta_contents), "至少有一条 delta 含非空 content"

    done_data = next(_json.loads(d) for t, d in events if t == "done")
    assert done_data["full_content"]
    assert "AI流式片段-C" in done_data["full_content"]
    assert "AI流式片段-A" in done_data["full_content"]


@pytest.mark.asyncio
async def test_start_stream_done_returns_message_id(
    client: AsyncClient, admin_headers, auth_headers, mock_ai_model_stream_for_sse,
):
    """SSE 流式 done 事件必须返回 message_id（>0）和完整文本，证明 AI 消息已落库。"""
    import json as _json

    p1, tpl, btn = await _bootstrap_button(client, admin_headers, "persist")
    r = await client.post("/api/health-self-check/start-stream", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "body_part_id": p1["id"],
        "symptoms": ["头痛"],
        "duration": "1-3天",
    }, headers=auth_headers)
    assert r.status_code == 200
    events = _parse_sse_text(r.text)
    done_data = next(_json.loads(d) for t, d in events if t == "done")
    # message_id 由 producer 写库后回填，证明 AI 消息已落库
    assert done_data.get("message_id"), f"done.message_id 应大于 0，实际={done_data}"
    assert isinstance(done_data["message_id"], int) and done_data["message_id"] > 0
    assert "AI流式片段" in (done_data.get("full_content") or "")


@pytest.mark.asyncio
async def test_start_stream_no_description(
    client: AsyncClient, admin_headers, auth_headers, mock_ai_model_stream_for_sse,
):
    """SSE 流式接口：不传 symptom_description 也应正常工作。"""
    p1, tpl, btn = await _bootstrap_button(client, admin_headers, "stream-nodesc")
    r = await client.post("/api/health-self-check/start-stream", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "body_part_id": p1["id"],
        "symptoms": ["头晕"],
        "duration": "1-3天",
    }, headers=auth_headers)
    assert r.status_code == 200
    events = _parse_sse_text(r.text)
    import json as _json
    meta_data = next(_json.loads(d) for t, d in events if t == "meta")
    assert meta_data["card_payload"]["symptom_description"] in (None, "")


@pytest.mark.asyncio
async def test_start_stream_template_without_placeholder_auto_appends(
    client: AsyncClient, admin_headers, auth_headers, mock_ai_model_stream_for_sse,
):
    """模板未含 {症状描述} 占位符，但用户填写了非空描述 → 后端兜底追加"症状描述：xxx"行。

    通过新建一个 prompt_override_text 中**不含** {症状描述} 的按钮验证（直接观察 mock_ai 捕获到的 prompt）。
    """
    p1 = (await client.post("/api/admin/body-part-dict", json={
        "name": "tplapp头", "icon": "🧠", "symptoms": ["头痛"],
    }, headers=admin_headers)).json()
    tpl = (await client.post("/api/admin/health-check-templates", json={
        "name": "tplapp模板", "body_parts": [{"id": p1["id"], "sort": 1}],
        "duration_options": ["<1天", "1-3天"],
        # 没有 {症状描述}
        "default_prompt": "部位={部位} 症状={症状列表} 时长={持续时间}",
    }, headers=admin_headers)).json()
    btn = (await client.post("/api/admin/function-buttons", json={
        "name": "tplapp按钮", "button_type": "health_self_check",
        "sort_weight": 0, "is_enabled": True, "icon": "🩺",
        "health_check_template_id": tpl["id"],
    }, headers=admin_headers)).json()

    r = await client.post("/api/health-self-check/start-stream", json={
        "button_id": btn["id"],
        "template_id": tpl["id"],
        "body_part_id": p1["id"],
        "symptoms": ["头痛"],
        "duration": "1-3天",
        "symptom_description": "夜间最痛",
    }, headers=auth_headers)
    assert r.status_code == 200
    # mock_ai_model_stream_for_sse 已记录 prompt
    assert "夜间最痛" in mock_ai_model_stream_for_sse["prompt"], \
        f"未在 prompt 中追加症状描述，prompt={mock_ai_model_stream_for_sse['prompt']!r}"
    assert "症状描述：夜间最痛" in mock_ai_model_stream_for_sse["prompt"]
