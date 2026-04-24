"""[2026-04-25] 轻量异步任务 + SSE 事件总线。

- asyncio 进程内事件循环投递
- 每个 session_id 维护一个 asyncio.Queue，允许多个 /stream 订阅者 fan-out
- 提供 broadcast(session_id, event, data) / subscribe(session_id) API
- 进程重启后内存丢失，由 interpret_status='pending' 扫描逻辑兜底重投

不引入 Celery / Redis，仅满足 PRD 中"秒回 + 后台流式"的最小集。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)


class _SessionBus:
    """每个 session 的事件总线，支持多订阅者。"""

    def __init__(self, session_id: int) -> None:
        self.session_id = session_id
        self._queues: Set[asyncio.Queue] = set()
        # 历史缓冲，允许迟到订阅者回放
        self._history: list[tuple[str, dict]] = []
        self._closed = False

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1024)
        # 先回放历史
        for ev, data in self._history:
            try:
                q.put_nowait((ev, data))
            except asyncio.QueueFull:
                pass
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    def broadcast(self, event: str, data: dict) -> None:
        self._history.append((event, data))
        # 限制历史长度防止内存泄漏（解读完成 / 失败后会自动清空）
        if len(self._history) > 2000:
            self._history = self._history[-1000:]
        for q in list(self._queues):
            try:
                q.put_nowait((event, data))
            except asyncio.QueueFull:
                logger.warning("SSE queue full for session %s, dropping event", self.session_id)

    def close(self) -> None:
        self._closed = True
        for q in list(self._queues):
            try:
                q.put_nowait(("__close__", {}))
            except Exception:
                pass

    def clear_history(self) -> None:
        self._history.clear()


_buses: Dict[int, _SessionBus] = {}
_bus_lock = asyncio.Lock()

# 正在运行的异步任务句柄
_running_tasks: Dict[int, asyncio.Task] = {}


def _get_or_create_bus(session_id: int) -> _SessionBus:
    bus = _buses.get(session_id)
    if bus is None:
        bus = _SessionBus(session_id)
        _buses[session_id] = bus
    return bus


def broadcast(session_id: int, event: str, data: Any) -> None:
    """向 session_id 的所有订阅者广播一条事件。"""
    bus = _get_or_create_bus(session_id)
    payload = data if isinstance(data, dict) else {"value": data}
    bus.broadcast(event, payload)


async def subscribe(session_id: int) -> AsyncIterator[tuple[str, dict]]:
    """订阅某个 session 的事件流。异步迭代器。"""
    bus = _get_or_create_bus(session_id)
    q = bus.subscribe()
    try:
        while True:
            ev, data = await q.get()
            if ev == "__close__":
                break
            yield ev, data
    finally:
        bus.unsubscribe(q)


def is_running(session_id: int) -> bool:
    t = _running_tasks.get(session_id)
    return t is not None and not t.done()


def submit_task(session_id: int, coro_factory: Callable[[], Awaitable[Any]]) -> bool:
    """投递异步任务。若已有同 session_id 任务在跑则忽略。返回是否成功投递。"""
    if is_running(session_id):
        logger.info("task already running for session %s, skip", session_id)
        return False

    async def _runner():
        try:
            await coro_factory()
        except Exception as e:  # noqa: BLE001
            logger.error("async task error session=%s: %s", session_id, e)
            broadcast(session_id, "error", {"code": "INTERNAL_ERROR", "message": str(e), "retryable": False})
        finally:
            _running_tasks.pop(session_id, None)

    task = asyncio.create_task(_runner())
    _running_tasks[session_id] = task
    return True


def close_session(session_id: int) -> None:
    """解读已完成/失败后关闭总线（仍保留历史回放 30 分钟级别靠进程自然 GC）。"""
    bus = _buses.get(session_id)
    if bus is not None:
        bus.close()


def cleanup_session(session_id: int) -> None:
    _buses.pop(session_id, None)
    _running_tasks.pop(session_id, None)


def sse_format(event: str, data: dict) -> str:
    """格式化为 SSE text/event-stream 字符串。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
