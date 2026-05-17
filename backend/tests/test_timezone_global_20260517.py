"""[BUG_FIX_TIMEZONE_GLOBAL_20260517] 全系统时区根治 - 单元测试

验证：
1. `iso_utc()` 工具函数对各种输入的正确处理。
2. `PriceFormattedJSONResponse` 全局拦截 datetime 输出为 "+00:00" 后缀的 ISO 字符串。
3. naive datetime（来自 `datetime.utcnow()`）会被强制标记为 UTC。
4. aware datetime（带 tzinfo）会被换算成 UTC。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from app.core.price_formatter import PriceFormattedJSONResponse, _strip_trailing_zeros
from app.utils.datetime_utils import iso_utc


def test_iso_utc_none():
    assert iso_utc(None) is None


def test_iso_utc_naive_treated_as_utc():
    # naive datetime（utcnow 风格）应被强制视为 UTC
    dt = datetime(2026, 5, 17, 2, 30, 0)
    out = iso_utc(dt)
    assert out is not None
    assert out.endswith("+00:00") or out.endswith("Z")
    assert "2026-05-17T02:30:00" in out


def test_iso_utc_aware_converted_to_utc():
    # 上海 +8h 的 10:30 = UTC 02:30
    tz_sh = timezone(timedelta(hours=8))
    dt = datetime(2026, 5, 17, 10, 30, 0, tzinfo=tz_sh)
    out = iso_utc(dt)
    assert out is not None
    assert "2026-05-17T02:30:00" in out
    assert out.endswith("+00:00")


def test_iso_utc_already_utc():
    dt = datetime(2026, 5, 17, 2, 30, 0, tzinfo=timezone.utc)
    out = iso_utc(dt)
    assert out is not None
    assert out.endswith("+00:00")
    assert "2026-05-17T02:30:00" in out


def test_response_class_renders_naive_datetime_with_utc_suffix():
    """核心验证：API 出口（PriceFormattedJSONResponse）会把 naive datetime 输出为带 UTC 后缀的字符串"""
    resp = PriceFormattedJSONResponse(
        content={
            "id": 1,
            "title": "test",
            "updated_at": datetime(2026, 5, 17, 2, 30, 0),  # naive
            "created_at": datetime(2026, 5, 17, 1, 0, 0),
        }
    )
    body = resp.body.decode("utf-8")
    data = json.loads(body)
    assert data["updated_at"].endswith("+00:00") or data["updated_at"].endswith("Z")
    assert data["created_at"].endswith("+00:00") or data["created_at"].endswith("Z")
    assert "2026-05-17T02:30:00" in data["updated_at"]


def test_response_class_renders_aware_datetime_converted_to_utc():
    tz_sh = timezone(timedelta(hours=8))
    resp = PriceFormattedJSONResponse(
        content={"t": datetime(2026, 5, 17, 10, 30, 0, tzinfo=tz_sh)}
    )
    data = json.loads(resp.body.decode("utf-8"))
    # +08 的 10:30 = UTC 02:30
    assert "2026-05-17T02:30:00" in data["t"]
    assert data["t"].endswith("+00:00")


def test_response_class_renders_nested_datetime():
    """嵌套结构里的 datetime 也必须被处理"""
    resp = PriceFormattedJSONResponse(
        content={
            "list": [
                {"id": 1, "created_at": datetime(2026, 5, 17, 2, 30, 0)},
                {"id": 2, "created_at": datetime(2026, 5, 17, 3, 0, 0)},
            ],
            "meta": {"server_time": datetime(2026, 5, 17, 4, 0, 0)},
        }
    )
    data = json.loads(resp.body.decode("utf-8"))
    assert data["list"][0]["created_at"].endswith("+00:00")
    assert data["list"][1]["created_at"].endswith("+00:00")
    assert data["meta"]["server_time"].endswith("+00:00")


def test_response_class_renders_date_unchanged():
    """date（仅日期）应原样输出 YYYY-MM-DD，不附时区"""
    resp = PriceFormattedJSONResponse(content={"d": date(2026, 5, 17)})
    data = json.loads(resp.body.decode("utf-8"))
    assert data["d"] == "2026-05-17"


def test_strip_trailing_zeros_still_works():
    """确保新增的 datetime 处理不影响原有的 float 末尾零处理"""
    out = _strip_trailing_zeros({"price": 10.0, "rate": 0.10})
    assert out["price"] == 10
    assert out["rate"] == 0.1


def test_response_class_handles_none_datetime():
    resp = PriceFormattedJSONResponse(content={"updated_at": None})
    data = json.loads(resp.body.decode("utf-8"))
    assert data["updated_at"] is None
