import json
from datetime import date, datetime, timezone
from typing import Any

from starlette.responses import JSONResponse


def _normalize_datetime_to_utc_iso(obj: Any) -> Any:
    """[BUG_FIX_TIMEZONE_GLOBAL_20260517] 把所有 datetime 统一为 "带 UTC 后缀" 的 ISO 字符串。

    - naive datetime（由 ``datetime.now()`` 产生）→ 强制标记为 UTC，再 isoformat
    - aware datetime → 先 astimezone(UTC)，再 isoformat
    - date（无时间部分）→ 直接 isoformat（仍保持 "YYYY-MM-DD"）
    """
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        else:
            obj = obj.astimezone(timezone.utc)
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def _strip_trailing_zeros(obj: Any) -> Any:
    """递归处理 JSON 对象：
    1) 对所有 float 值去掉末尾零；
    2) [BUG_FIX_TIMEZONE_GLOBAL_20260517] 对所有 datetime 强制按 UTC 输出
       （根治全系统时间字段裸 ``.isoformat()`` 丢失时区导致前端 +8h 偏差的问题）。
    """
    if isinstance(obj, dict):
        return {k: _strip_trailing_zeros(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_strip_trailing_zeros(item) for item in obj]
    elif isinstance(obj, datetime):
        return _normalize_datetime_to_utc_iso(obj)
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, float):
        if obj != obj:  # NaN
            return None
        if obj == float('inf') or obj == float('-inf'):
            return None
        int_val = int(obj)
        if obj == int_val:
            return int_val
        formatted = f"{obj:.10g}"
        if '.' not in formatted:
            return int(formatted)
        return float(formatted)
    return obj


def _json_default(obj: Any) -> Any:
    """[BUG_FIX_TIMEZONE_GLOBAL_20260517] json.dumps 的兜底 default。

    `_strip_trailing_zeros` 已递归把 datetime/date 转成字符串了，理论上不会再走这里；
    但仍提供 default 以防 starlette 内部对 jsonable_encoder 的输出绕过我们的递归处理。
    """
    if isinstance(obj, datetime):
        return _normalize_datetime_to_utc_iso(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class PriceFormattedJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        content = _strip_trailing_zeros(content)
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=_json_default,
        ).encode("utf-8")
