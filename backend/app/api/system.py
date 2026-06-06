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
    - now_iso: ISO8601 UTC 字符串（含 Z 后缀，便于前端 new Date 直接解析）
    - now_unix_ms: 毫秒级时间戳
    - timezone: 服务器时区标识（默认 UTC；如部署在 +08 时区且系统时区已配置，可返回 Asia/Shanghai）

    用途：
    - H5 / 微信小程序 / Flutter 三端在改约弹窗打开时调用，记录与本地的偏移
    - 之后所有"是否为今天 / 时段是否已过"判断均使用 (本地时间 - offset) 推算
    - 即便客户端时间被调快 1 天，前端仍按服务器时间过滤
    """
    utc_now = datetime.now()
    return {
        "now_iso": utc_now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc_now.microsecond // 1000:03d}Z",
        "now_unix_ms": int(time.time() * 1000),
        "timezone": "UTC",
    }
