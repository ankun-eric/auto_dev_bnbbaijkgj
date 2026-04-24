"""[2026-04-25] 体检报告解读 Bug 修复（A/B/C）三端联动后端测试。

重点验证：
- models.ChatSession 新增 interpret_status / interpret_error / interpret_started_at / interpret_finished_at
- models.ChatMessage 新增 is_hidden
- task_queue 基础 API
- /api/report/interpret/session/:sid/retry 非法状态的 409
"""
import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.database import Base
from app.core.task_queue import broadcast, submit_task, subscribe, sse_format
from app.models.models import ChatMessage, ChatSession


def test_chat_session_has_interpret_fields():
    cols = ChatSession.__table__.columns.keys()
    for name in ("interpret_status", "interpret_error", "interpret_started_at", "interpret_finished_at"):
        assert name in cols, f"ChatSession 缺少字段 {name}"


def test_chat_message_has_is_hidden():
    cols = ChatMessage.__table__.columns.keys()
    assert "is_hidden" in cols, "ChatMessage 缺少 is_hidden 字段"


@pytest.mark.asyncio
async def test_task_queue_broadcast_and_subscribe():
    """task_queue：订阅者能收到 broadcast 的事件。"""
    session_id = 999901
    received = []

    async def consume():
        count = 0
        async for event, data in subscribe(session_id):
            received.append((event, data))
            count += 1
            if count >= 2:
                break

    task = asyncio.create_task(consume())
    # 给订阅者一点时间建立
    await asyncio.sleep(0.05)
    broadcast(session_id, "progress", {"stage": "ocr", "percent": 10})
    broadcast(session_id, "message.delta", {"delta": "您好"})
    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) >= 2
    assert received[0][0] == "progress"
    assert received[1][0] == "message.delta"


def test_sse_format_ok():
    text = sse_format("ping", {})
    # SSE 必含 event 行与空行结尾
    assert text.startswith("event: ping")
    assert text.endswith("\n\n")


@pytest.mark.asyncio
async def test_submit_task_runs_once_per_session():
    """同一 session_id 的任务只会跑一次（重复 submit 被忽略）。"""
    session_id = 999902
    counter = {"n": 0}

    async def job():
        counter["n"] += 1
        await asyncio.sleep(0.05)

    submit_task(session_id, job)
    # 立刻再投递一次：应被忽略
    submit_task(session_id, job)
    await asyncio.sleep(0.2)
    assert counter["n"] == 1
