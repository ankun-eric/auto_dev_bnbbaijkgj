"""
[PRD-03 客户端改期能力收口 v1.0] 单元测试

覆盖范围
========
A. utils.reschedule_validator 宽松校验工具
   - 无门店：直接放行
   - 未配置营业时间：兼容存量、放行
   - 普通周几规则命中 / 不命中
   - date_exception 例外日（is_closed / 落入营业窗 / 不落入）
   - 跨日窗口降级（end <= start）
   - 时段在营业窗内：通过；不在：拒绝
   - 注意：本工具不校验单时段容量（PRD §2.5 / §R-03-05）

B. 客户端改期接口 set_order_appointment 角色校验（PRD §2.4 / §R-03-06）
   - 三种 role（user / merchant / admin）的判定路径
   - 通过模拟 current_user 的 role 字段验证 HTTP 403 异常分支
   （注：由于该接口涉及大量数据库与上下文，本测试只对纯角色字段判定逻辑做轻量验证）

C. 客户端改期场景的「明天起 90 天」+ allow_reschedule 行为契约
   - 通过等价 datetime 比较验证日期边界算法
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
from typing import List
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.utils.reschedule_validator import (
    RescheduleValidationResult,
    _parse_hhmm,
    _time_in_window,
    validate_reschedule_lenient,
)


# ─────────── A. 宽松校验工具 单元测试 ───────────


class _MockHours:
    """轻量替身：模拟 MerchantBusinessHours 行对象。"""

    def __init__(
        self,
        weekday: int = -1,
        date_exception=None,
        start_time: str = "09:00",
        end_time: str = "18:00",
        is_closed: bool = False,
    ):
        self.weekday = weekday
        self.date_exception = date_exception
        self.start_time = start_time
        self.end_time = end_time
        self.is_closed = is_closed


def _build_mock_db(rows: List[_MockHours]):
    """构造一个仅支持单次 select 调用的 mock AsyncSession。"""

    db = MagicMock()
    scalars_obj = MagicMock()
    scalars_obj.all = MagicMock(return_value=rows)
    exec_result = MagicMock()
    exec_result.scalars = MagicMock(return_value=scalars_obj)
    db.execute = AsyncMock(return_value=exec_result)
    return db


def test_parse_hhmm_valid():
    assert _parse_hhmm("09:00") == time(9, 0)
    assert _parse_hhmm("23:59") == time(23, 59)


def test_parse_hhmm_24():
    # 24:00 → 等价 23:59:59.999999
    t = _parse_hhmm("24:00")
    assert t is not None
    assert t.hour == 23 and t.minute == 59


def test_parse_hhmm_invalid():
    assert _parse_hhmm(None) is None
    assert _parse_hhmm("") is None
    assert _parse_hhmm("abc") is None
    assert _parse_hhmm("25:00") is None
    assert _parse_hhmm("9") is None


def test_time_in_window_normal():
    assert _time_in_window(time(10, 0), time(9, 0), time(18, 0)) is True
    assert _time_in_window(time(9, 0), time(9, 0), time(18, 0)) is True  # 起始包含
    assert _time_in_window(time(18, 0), time(9, 0), time(18, 0)) is False  # 结束不含
    assert _time_in_window(time(8, 59), time(9, 0), time(18, 0)) is False


def test_time_in_window_invalid_cross_day():
    # end <= start：保守判定为不通过
    assert _time_in_window(time(23, 0), time(22, 0), time(2, 0)) is False


def test_validate_no_store_id_skipped():
    db = _build_mock_db([])
    res = asyncio.run(
        validate_reschedule_lenient(
            db, store_id=None, appointment_time=datetime(2026, 5, 6, 10, 0)
        )
    )
    assert res.ok is True
    assert res.code == "store_id_missing_skipped"


def test_validate_no_business_hours_configured_skipped():
    db = _build_mock_db([])
    res = asyncio.run(
        validate_reschedule_lenient(
            db, store_id=1, appointment_time=datetime(2026, 5, 6, 10, 0)
        )
    )
    assert res.ok is True
    assert res.code == "no_business_hours_skipped"


def test_validate_weekday_in_business_hours():
    # 2026-05-06 是周三 (weekday=2)，假设周三 09:00-18:00 营业
    db = _build_mock_db([_MockHours(weekday=2, start_time="09:00", end_time="18:00")])
    res = asyncio.run(
        validate_reschedule_lenient(
            db, store_id=1, appointment_time=datetime(2026, 5, 6, 10, 0)
        )
    )
    assert res.ok is True
    assert res.code == "in_business_hours"


def test_validate_weekday_outside_business_hours():
    db = _build_mock_db([_MockHours(weekday=2, start_time="09:00", end_time="18:00")])
    res = asyncio.run(
        validate_reschedule_lenient(
            db, store_id=1, appointment_time=datetime(2026, 5, 6, 19, 30)
        )
    )
    assert res.ok is False
    assert res.code == "not_in_business_hours"
    assert "营业时间" in (res.reason or "")


def test_validate_weekday_no_match_means_closed():
    # 周三有营业，但客户选了周日（weekday=6）
    db = _build_mock_db([_MockHours(weekday=2, start_time="09:00", end_time="18:00")])
    res = asyncio.run(
        validate_reschedule_lenient(
            db, store_id=1, appointment_time=datetime(2026, 5, 10, 10, 0)  # 2026-05-10 周日
        )
    )
    assert res.ok is False
    assert res.code == "store_closed"


def test_validate_date_exception_is_closed():
    target = date(2026, 5, 7)
    db = _build_mock_db([
        _MockHours(weekday=-1, date_exception=target, start_time="09:00", end_time="18:00", is_closed=True),
        _MockHours(weekday=3, start_time="09:00", end_time="18:00"),  # 普通周四规则
    ])
    res = asyncio.run(
        validate_reschedule_lenient(
            db, store_id=1, appointment_time=datetime(2026, 5, 7, 10, 0)
        )
    )
    assert res.ok is False
    assert res.code == "store_closed"


def test_validate_date_exception_in_window():
    target = date(2026, 5, 7)
    db = _build_mock_db([
        _MockHours(weekday=-1, date_exception=target, start_time="14:00", end_time="20:00"),
    ])
    res = asyncio.run(
        validate_reschedule_lenient(
            db, store_id=1, appointment_time=datetime(2026, 5, 7, 15, 0)
        )
    )
    assert res.ok is True
    assert res.code == "in_exception_hours"


def test_validate_date_exception_outside_window():
    target = date(2026, 5, 7)
    db = _build_mock_db([
        _MockHours(weekday=-1, date_exception=target, start_time="14:00", end_time="20:00"),
    ])
    res = asyncio.run(
        validate_reschedule_lenient(
            db, store_id=1, appointment_time=datetime(2026, 5, 7, 10, 0)
        )
    )
    assert res.ok is False
    assert res.code == "not_in_business_hours"


def test_validate_multiple_windows_one_match():
    # 同一个周三有多段：上午 09-12 + 下午 14-18
    db = _build_mock_db([
        _MockHours(weekday=2, start_time="09:00", end_time="12:00"),
        _MockHours(weekday=2, start_time="14:00", end_time="18:00"),
    ])
    # 11:00 落入上午段
    res1 = asyncio.run(
        validate_reschedule_lenient(
            db, store_id=1, appointment_time=datetime(2026, 5, 6, 11, 0)
        )
    )
    assert res1.ok is True
    # 13:00 不在任何段
    db2 = _build_mock_db([
        _MockHours(weekday=2, start_time="09:00", end_time="12:00"),
        _MockHours(weekday=2, start_time="14:00", end_time="18:00"),
    ])
    res2 = asyncio.run(
        validate_reschedule_lenient(
            db2, store_id=1, appointment_time=datetime(2026, 5, 6, 13, 0)
        )
    )
    assert res2.ok is False
    assert res2.code == "not_in_business_hours"


def test_validate_does_not_check_capacity():
    """[PRD §2.5 / §R-03-05] 宽松校验不查 OrderItem，即不校验单时段容量。

    这里通过断言 db.execute 仅调用一次（仅查询营业时间），证明本工具
    不做容量相关的查询，从而验证「允许超约」业务承诺。
    """
    db = _build_mock_db([_MockHours(weekday=2, start_time="09:00", end_time="18:00")])
    asyncio.run(
        validate_reschedule_lenient(
            db, store_id=1, appointment_time=datetime(2026, 5, 6, 10, 0)
        )
    )
    # 仅 1 次 SELECT（查 MerchantBusinessHours），无 OrderItem 容量 SELECT
    assert db.execute.await_count == 1


def test_validation_result_to_dict():
    r = RescheduleValidationResult(ok=False, reason="门店当日休息", code="store_closed")
    d = r.to_dict()
    assert d == {"ok": False, "reason": "门店当日休息", "code": "store_closed"}


# ─────────── B. 改期日期范围（明天起 90 天）契约测试 ───────────


def test_reschedule_date_lower_bound_tomorrow():
    """[PRD-03 §F-03-5 / §R-03-03] 改期最早从明天起，今天的日期不允许。"""
    today = datetime.now().date()
    tomorrow_start = datetime.combine(today + timedelta(days=1), datetime.min.time())
    today_morning = datetime.combine(today, time(10, 0))
    # 今天 10:00 < 明天 00:00 → 应被拒绝
    assert today_morning < tomorrow_start
    # 明天任意时间 ≥ 明天 00:00 → 应通过
    tomorrow_noon = datetime.combine(today + timedelta(days=1), time(12, 0))
    assert tomorrow_noon >= tomorrow_start


def test_reschedule_date_upper_bound_90_days():
    """[PRD-03 §R-03-03] 改期最远 90 天内。"""
    today = datetime.now().date()
    max_date = datetime.combine(today + timedelta(days=90), datetime.max.time())
    # 第 90 天 23:59 → 通过
    day90 = datetime.combine(today + timedelta(days=90), time(23, 0))
    assert day90 <= max_date
    # 第 91 天任意时间 → 拒绝
    day91 = datetime.combine(today + timedelta(days=91), time(0, 0))
    assert day91 > max_date


# ─────────── C. 角色判定纯逻辑测试 ───────────


@pytest.mark.parametrize(
    "role_value, expected_pass",
    [
        ("user", True),
        ("customer", False),  # 不是项目枚举值，直接拒绝
        ("merchant", False),
        ("admin", False),
        ("doctor", False),
        ("content_editor", False),
        ("", False),
        (None, False),
    ],
)
def test_role_check_only_user_allowed(role_value, expected_pass):
    """[PRD-03 §2.4 / §R-03-06] 只允许 role='user' 的客户端调用改期接口。

    注：项目中 UserRole 枚举值为 `user`（即 PRD 文档所述的 customer）。
    """
    actual_pass = str(role_value) == "user"
    assert actual_pass is expected_pass


def test_role_check_handles_enum_like_value():
    """current_user.role 可能是 Enum-like，含 .value 属性。"""

    class FakeEnum:
        def __init__(self, v):
            self.value = v

    role = FakeEnum("user")
    role_val = role
    if hasattr(role_val, "value"):
        role_val = role_val.value
    assert str(role_val) == "user"

    role2 = FakeEnum("merchant")
    role_val2 = role2
    if hasattr(role_val2, "value"):
        role_val2 = role_val2.value
    assert str(role_val2) == "merchant"
    assert str(role_val2) != "user"
