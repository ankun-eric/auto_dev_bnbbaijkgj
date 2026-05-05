"""
[PRD-03 客户端改期能力收口 v1.0] 改期容量校验工具（宽松校验）。

校验策略（PRD §2.5 / §R-03-05）：
========================================
- ✅ 校验「目标日期门店是否营业」：当天为休息日（is_closed=True 的 date_exception
  或所在周几无任何营业时间窗）→ 拒绝改期。
- ✅ 校验「目标时段是否在门店任一营业时间窗内」：以预约 datetime 的 hour:minute
  落入某个 (start_time, end_time) 内即算通过；若未落入任何窗口 → 拒绝改期。
- ❌ **不校验**「目标时段单时段容量」：即使该时段已经满员（已超过 capacity）
  也允许客户改期到该时段，由门店人工协调（PRD §2.5 业务理由）。

复杂度
======
- 一次 SELECT 查询所有营业时段（按 store_id），O(n)，n = 该门店时段条数（通常 < 30）
- 内存判断 datetime 是否落入时段窗口，O(n)
- 不查 OrderItem / capacity，避免「明明门店还能挤一挤却被系统挡住」的死板体验

约束
====
- 若门店尚未配置任何营业时间（merchant_business_hours 表无该 store_id 记录）→
  视为「未配置营业时间」，**不阻塞改期**（兼容存量门店未来再补营业时间）。
- 凌晨 00:00-06:00 不在 9 段切片内，前端时段选择器本身屏蔽，
  此处营业时间窗口校验作为后端兜底，假如客户端绕过仍会被拦下。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import MerchantBusinessHours


@dataclass
class RescheduleValidationResult:
    """改期容量校验结果。"""

    ok: bool
    reason: Optional[str] = None  # 失败原因（中文，可直接抛给前端）
    code: Optional[str] = None  # 失败错误码（store_closed / not_in_business_hours / no_business_hours_skipped）

    def to_dict(self) -> dict:
        return {"ok": self.ok, "reason": self.reason, "code": self.code}


def _parse_hhmm(s: Optional[str]) -> Optional[time]:
    """安全解析 'HH:MM' 字符串，失败返回 None。"""
    if not s:
        return None
    try:
        parts = s.strip().split(":")
        if len(parts) != 2:
            return None
        h = int(parts[0])
        m = int(parts[1])
        if not (0 <= h <= 24 and 0 <= m <= 59):
            return None
        # 24:00 特殊处理 → 视作当日 23:59:59.999999 的等价上界
        if h == 24:
            return time(23, 59, 59, 999999)
        return time(h, m)
    except (ValueError, AttributeError):
        return None


def _time_in_window(target: time, start: time, end: time) -> bool:
    """判断 target 是否落在 [start, end) 区间内。

    - end 早于 start 视为跨日（如 22:00-02:00），但本项目营业时间窗均不跨日，
      若收到跨日数据按「不重叠」处理，避免误判。
    """
    if end <= start:
        # 跨日或无效配置：保守按未通过处理
        return False
    return start <= target < end


async def validate_reschedule_lenient(
    db: AsyncSession,
    *,
    store_id: Optional[int],
    appointment_time: datetime,
) -> RescheduleValidationResult:
    """[PRD-03 §2.5] 宽松改期容量校验。

    Parameters
    ----------
    db : AsyncSession
        数据库会话
    store_id : Optional[int]
        门店 id；为 None 时直接放行（订单未关联门店）
    appointment_time : datetime
        目标预约时间（已转换为本地时间戳，无时区或 UTC 均可，本函数仅取 hour:minute）

    Returns
    -------
    RescheduleValidationResult
        ok=True 表示通过；ok=False 时附带 reason / code 供调用方使用。
    """
    if store_id is None:
        # 订单未挂门店（如纯电商订单）→ 不卡改期
        return RescheduleValidationResult(ok=True, code="store_id_missing_skipped")

    # 1. 取出该门店的所有营业时间窗
    rows = await db.execute(
        select(MerchantBusinessHours).where(
            MerchantBusinessHours.store_id == store_id
        )
    )
    hours_list: List[MerchantBusinessHours] = list(rows.scalars().all())

    # 2. 若完全未配置营业时间 → 兼容存量门店，跳过校验（不阻塞改期）
    if not hours_list:
        return RescheduleValidationResult(
            ok=True, code="no_business_hours_skipped"
        )

    target_date: date = appointment_time.date()
    target_hhmm: time = appointment_time.time()
    # weekday: Python Monday=0...Sunday=6，与 MerchantBusinessHours.weekday 定义一致
    target_weekday: int = appointment_time.weekday()

    # 3. 优先检查 date_exception 例外日（同日命中 → 该规则覆盖周几规则）
    exception_rows = [h for h in hours_list if h.date_exception == target_date]
    if exception_rows:
        # 例外日：若任一记录 is_closed=True → 当日休息
        if any(getattr(h, "is_closed", False) for h in exception_rows):
            return RescheduleValidationResult(
                ok=False,
                reason="门店当日休息",
                code="store_closed",
            )
        # 例外日营业窗：在任一窗口内即通过
        for h in exception_rows:
            start_t = _parse_hhmm(h.start_time)
            end_t = _parse_hhmm(h.end_time)
            if start_t and end_t and _time_in_window(target_hhmm, start_t, end_t):
                return RescheduleValidationResult(ok=True, code="in_exception_hours")
        # 例外日有窗口但未落入
        return RescheduleValidationResult(
            ok=False,
            reason="所选时段超出门店营业时间",
            code="not_in_business_hours",
        )

    # 4. 普通周几规则：weekday 匹配 + 非例外日（weekday >=0 即非例外）
    weekly_rows = [
        h for h in hours_list
        if h.weekday is not None and h.weekday == target_weekday
    ]
    if not weekly_rows:
        # 该周几没有任何营业窗口 → 视作休息
        return RescheduleValidationResult(
            ok=False,
            reason="门店当日休息",
            code="store_closed",
        )

    for h in weekly_rows:
        start_t = _parse_hhmm(h.start_time)
        end_t = _parse_hhmm(h.end_time)
        if start_t and end_t and _time_in_window(target_hhmm, start_t, end_t):
            return RescheduleValidationResult(ok=True, code="in_business_hours")

    # 周几匹配但所有窗口都未命中
    return RescheduleValidationResult(
        ok=False,
        reason="所选时段超出门店营业时间",
        code="not_in_business_hours",
    )


__all__ = [
    "RescheduleValidationResult",
    "validate_reschedule_lenient",
]
