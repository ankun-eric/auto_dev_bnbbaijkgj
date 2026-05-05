"""
[PRD-01 全平台固定时段切片体系 v1.0] 全平台 9 段固定切片统一定义。

本模块是 PRD-01 落地的「底座」工具，所有按时段管理能力（看板、改期、统计、
客户端时段选择器、订单 time_slot 字段）必须从这里取一致的切片定义，
**不再读取门店营业时间动态生成时段**。

切片规则
========
- 每段固定 2 小时，最早 06:00 起，最晚 24:00 结束，共 9 段
- 凌晨 00:00-06:00 不开放
- 段号 → 时段：
    1: 06:00-08:00
    2: 08:00-10:00
    3: 10:00-12:00
    4: 12:00-14:00
    5: 14:00-16:00
    6: 16:00-18:00
    7: 18:00-20:00
    8: 20:00-22:00
    9: 22:00-24:00

复杂度
======
- 全部纯计算 O(1)，无 IO，可在请求热路径中安全调用。

兼容性
======
- 历史 `merchant_dashboard.py` 中已有相同实现，迁移后通过 `from app.utils.time_slots import *`
  方式让 `merchant_dashboard.SLOT_HOURS` / `slot_label` / `appointment_to_slot` /
  `slot_window` 行为完全保持一致，不破坏 v1.0 看板功能。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple


# ─────────── 常量：9 段切片 ───────────

SLOT_HOURS: List[Tuple[int, int]] = [
    (6, 8),   # slot 1
    (8, 10),  # slot 2
    (10, 12), # slot 3
    (12, 14), # slot 4
    (14, 16), # slot 5
    (16, 18), # slot 6
    (18, 20), # slot 7
    (20, 22), # slot 8
    (22, 24), # slot 9
]

SLOT_COUNT: int = 9


# ─────────── 函数：段号 ↔ 时间窗 ───────────

def slot_label(slot_no: int) -> str:
    """段号 1-9 → "06:00-08:00" 形式标签。无效段号返回空串。"""
    if not 1 <= slot_no <= SLOT_COUNT:
        return ""
    h_start, h_end = SLOT_HOURS[slot_no - 1]
    end_str = "24:00" if h_end == 24 else f"{h_end:02d}:00"
    return f"{h_start:02d}:00-{end_str}"


def slot_start_str(slot_no: int) -> str:
    """段号 1-9 → 起始 "HH:MM" 字符串"""
    if not 1 <= slot_no <= SLOT_COUNT:
        return ""
    return f"{SLOT_HOURS[slot_no - 1][0]:02d}:00"


def slot_end_str(slot_no: int) -> str:
    """段号 1-9 → 结束 "HH:MM" 字符串（22:00-24:00 段返回 "24:00"）"""
    if not 1 <= slot_no <= SLOT_COUNT:
        return ""
    h_end = SLOT_HOURS[slot_no - 1][1]
    return "24:00" if h_end == 24 else f"{h_end:02d}:00"


def appointment_to_slot(dt: Optional[datetime]) -> Optional[int]:
    """
    [F-01-2 时段映射函数] 输入预约时间 → 输出段号 1-9。

    规则
    ----
    - dt 为 None / 凌晨 00:00-06:00 → 返回 None（凌晨段不归入 9 宫格）
    - 22:00 及之后 → 第 9 段
    - 跨日订单（如 22:00-次日 00:00）按 PRD R-01-03，按起始 dt 归段，
      因此 dt.hour=22 直接归 9，dt.hour=23 也归 9
    """
    if dt is None:
        return None
    h = dt.hour
    if h < 6:
        return None
    for idx, (start, end) in enumerate(SLOT_HOURS, start=1):
        if start <= h < end:
            return idx
    return SLOT_COUNT


def slot_window(target_date: date, slot_no: int) -> Tuple[datetime, datetime]:
    """
    段号 → 该日的 [start, end) datetime 半开区间。

    第 9 段 (22:00-24:00) 的 end 取次日 00:00 以避免跨日丢点。
    无效段号抛 ValueError。
    """
    if not 1 <= slot_no <= SLOT_COUNT:
        raise ValueError(f"slot_no 必须在 1-{SLOT_COUNT} 之间，收到 {slot_no!r}")
    h_start, h_end = SLOT_HOURS[slot_no - 1]
    start_dt = datetime.combine(target_date, time(h_start, 0))
    if h_end == 24:
        end_dt = datetime.combine(target_date + timedelta(days=1), time(0, 0))
    else:
        end_dt = datetime.combine(target_date, time(h_end, 0))
    return start_dt, end_dt


def slots_config_payload() -> dict:
    """
    [F-01-4] 返回 `/api/common/time-slots` 接口标准响应体。

    严格遵循 PRD §2.3 接口设计：
    {
      "slots": [
        {"slot_no": 1, "start": "06:00", "end": "08:00"},
        ...
        {"slot_no": 9, "start": "22:00", "end": "24:00"}
      ]
    }

    同时附带 `rule` 字段供前端直接展示规则说明。
    """
    return {
        "slots": [
            {
                "slot_no": idx,
                "start": slot_start_str(idx),
                "end": slot_end_str(idx),
            }
            for idx in range(1, SLOT_COUNT + 1)
        ],
        "rule": (
            "全平台固定 9 段时段（每段 2 小时，最早 06:00，最晚 24:00），"
            "凌晨 00:00-06:00 不开放预约"
        ),
    }


__all__ = [
    "SLOT_HOURS",
    "SLOT_COUNT",
    "slot_label",
    "slot_start_str",
    "slot_end_str",
    "appointment_to_slot",
    "slot_window",
    "slots_config_payload",
]
