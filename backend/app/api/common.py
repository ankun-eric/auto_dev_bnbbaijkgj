"""
[PRD-01 全平台固定时段切片体系 v1.0] 全平台公共接口集合

当前提供：
- GET /api/common/time-slots : 全平台固定 9 段时段配置
  · 响应字段严格遵循 PRD §2.3：[{slot_no, start, end}]
  · 公开接口，无需鉴权，供小程序 / APP / H5 / 商家端 PC 共用
  · 复杂度 O(1)，纯计算（PRD §5 非功能性需求 ≤100ms 可达）
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.utils.time_slots import slots_config_payload


router = APIRouter(prefix="/api/common", tags=["公共配置"])


@router.get("/time-slots")
async def get_common_time_slots() -> Dict[str, Any]:
    """
    [F-01-4] 返回全平台固定 9 段时段配置。

    响应示例
    --------
    {
      "slots": [
        {"slot_no": 1, "start": "06:00", "end": "08:00"},
        ...
        {"slot_no": 9, "start": "22:00", "end": "24:00"}
      ],
      "rule": "全平台固定 9 段时段（每段 2 小时，最早 06:00，最晚 24:00），凌晨 00:00-06:00 不开放预约"
    }
    """
    return slots_config_payload()
