import json
from typing import Any

from starlette.responses import JSONResponse


def _strip_trailing_zeros(obj: Any) -> Any:
    """递归处理 JSON 对象，对所有 float 值去掉末尾零"""
    if isinstance(obj, dict):
        return {k: _strip_trailing_zeros(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_strip_trailing_zeros(item) for item in obj]
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


class PriceFormattedJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        content = _strip_trailing_zeros(content)
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")
