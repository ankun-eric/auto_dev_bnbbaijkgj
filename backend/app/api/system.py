"""[BUG-FIX-RESCHEDULE-V2 2026-05-07] 系统级公共接口。

提供前端拉取权威服务器时间的入口，用于改约弹窗按服务器时间过滤过去时段，
避免依赖客户端本地时间被人为调快/调慢绕过过滤。

设计要点：
- 无鉴权（任何端任何用户可调用）
- 响应极简，10ms 内返回
- 同时返回 ISO8601 字符串、毫秒级 unix 时间戳、时区，便于前端按需使用
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/server-time")
async def get_server_time() -> Dict[str, Any]:
    """获取服务器当前时间。

    返回字段：
    - now_iso: 北京时间字符串 "YYYY-MM-DD HH:mm:ss"
    - now_unix_ms: 毫秒级时间戳
    - timezone: 服务器时区标识

    用途：
    - 前端各端调用获取服务器时间，用于时间校准和显示
    """
    now = datetime.now()
    return {
        "now_iso": now.strftime("%Y-%m-%d %H:%M:%S"),
        "now_unix_ms": int(time.time() * 1000),
        "timezone": "Asia/Shanghai",
    }
