"""[BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517] 时区规范工具

背景：
后端写入时统一使用 `datetime.utcnow()`（不带 tzinfo），但接口返回时直接
`dt.isoformat()` 会得到无时区标识的字符串（如 "2026-05-16T16:58:29"），
前端 JS 的 `new Date(...)` 会按本地时区解析，导致：
 - 美国服务器（UTC-8）下"刚刚发生的会话"被前端误以为是 8 小时前；
 - 中国服务器（UTC+8）下偏差 8 小时。

修复策略：
所有 ORM 时间字段在 API 返回时，统一通过 `iso_utc()` 包装，输出
"+00:00" 或 "Z" 后缀，让前端 `new Date(...)` 能正确识别为 UTC 时间，
再 `.toLocaleString` 或相对时间组件自动转换为用户本地时区。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def iso_utc(dt: Optional[datetime]) -> Optional[str]:
    """把数据库里 naive UTC 的 datetime 序列化为带 UTC 时区标识的 ISO 字符串。

    - 若 ``dt`` 为 ``None``，返回 ``None``。
    - 若 ``dt`` 没有 tzinfo（naive，来自 ``datetime.utcnow()``），强制视为 UTC。
    - 若 ``dt`` 已带 tzinfo，转换为 UTC 后再序列化（避免不同环境串位）。

    输出示例：``"2026-05-17T01:23:45+00:00"``，前端可直接
    ``new Date("2026-05-17T01:23:45+00:00")`` 得到正确的本地时间。
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


__all__ = ["iso_utc"]
