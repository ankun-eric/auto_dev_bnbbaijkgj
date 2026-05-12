"""[PRD-468 2026-05-12] 健康档案改版 v3：新增表模型。

新增表：
- `health_metric_record`（健康指标记录表）
- `device_binding`（设备绑定表）

幂等建表通过 `_migrate_prd468_health_v3` 完成（main.py lifespan）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import mapped_column

from app.core.database import Base


class HealthMetricRecord(Base):
    """[PRD-468] 健康指标记录：血压/血糖/心率/睡眠/血氧。

    value_json 结构因 metric_type 不同而异：
    - blood_pressure: {"systolic": 128, "diastolic": 82, "period": "morning"}
    - blood_glucose:  {"value": 6.5, "period": "fasting"}
    - heart_rate:     {"value": 72, "activity": "resting"}
    - sleep:          {"duration_h": 7.5, "deep_h": 2.0, "sleep_at": "23:00", "wake_at": "06:30"}
    - spo2:           {"value": 97, "period": "morning"}
    """

    __tablename__ = "health_metric_record"

    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id = mapped_column(BigInteger, nullable=False, index=True, comment="健康档案 health_profiles.id")
    metric_type = mapped_column(String(32), nullable=False, comment="blood_pressure/blood_glucose/heart_rate/sleep/spo2")
    value_json = mapped_column(JSON, nullable=False)
    source = mapped_column(
        String(32), nullable=False, default="manual",
        comment="manual/huawei_watch/xiaomi_band/glucometer/bp_meter/scale",
    )
    measured_at = mapped_column(DateTime, nullable=False, comment="测量时间")
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = mapped_column(BigInteger, nullable=False, comment="录入用户ID")

    __table_args__ = (
        Index("idx_profile_metric_time", "profile_id", "metric_type", "measured_at"),
        Index("idx_source", "source"),
    )


class DeviceBinding(Base):
    """[PRD-468] 设备绑定（手环/手表/血糖仪等）。"""

    __tablename__ = "device_binding"

    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id = mapped_column(BigInteger, nullable=False, index=True)
    device_type = mapped_column(
        String(32), nullable=False,
        comment="huawei_watch/xiaomi_band/glucometer/bp_meter/scale",
    )
    device_id = mapped_column(String(128), nullable=False, comment="设备唯一标识（OAuth subject 或 MAC）")
    access_token = mapped_column(Text, nullable=True, comment="OAuth access token（本期占位明文，后续接入 KMS）")
    refresh_token = mapped_column(Text, nullable=True)
    token_expires_at = mapped_column(DateTime, nullable=True)
    status = mapped_column(String(16), nullable=False, default="active", comment="active/expired/unbound")
    bound_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_sync_at = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "device_type", name="uk_user_device"),
        Index("idx_status_devbind", "status"),
    )
