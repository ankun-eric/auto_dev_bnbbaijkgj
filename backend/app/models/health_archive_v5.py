"""[PRD-HEALTH-ARCHIVE-V5-20260521] 健康预警 + 就医资料 SQLAlchemy 模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class HealthAlert(Base):
    __tablename__ = "health_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    member_id = Column(Integer, nullable=True, index=True)
    alert_type = Column(String(16), nullable=False)
    indicator = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    detail = Column(Text, nullable=True)
    severity = Column(String(8), nullable=False, default="medium")
    source_label = Column(String(128), nullable=True)
    advice = Column(Text, nullable=True)
    raw_payload = Column(JSON, nullable=True)
    ref_record_id = Column(Integer, nullable=True)
    ref_plan_id = Column(Integer, nullable=True)
    ref_device_id = Column(Integer, nullable=True)
    merged_count = Column(Integer, nullable=False, default=1)
    last_occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(8), nullable=False, default="open")
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index("idx_ha_merge_v5", "user_id", "member_id", "alert_type", "indicator", "status"),
    )


class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    member_id = Column(Integer, nullable=True, index=True)
    category = Column(String(16), nullable=False)
    title = Column(String(255), nullable=False)
    record_date = Column(Date, nullable=True)
    source = Column(String(16), nullable=False, default="manual")
    ai_interpretation = Column(JSON, nullable=True)
    remark = Column(Text, nullable=True)
    is_deleted = Column(SmallInteger, nullable=False, default=0)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    files = relationship(
        "MedicalRecordFile",
        primaryjoin="MedicalRecord.id==foreign(MedicalRecordFile.record_id)",
        order_by="MedicalRecordFile.sort_order, MedicalRecordFile.id",
        viewonly=True,
    )


class MedicalRecordFile(Base):
    __tablename__ = "medical_record_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(Integer, nullable=False, index=True)
    file_url = Column(String(512), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(16), nullable=False, default="image")
    file_size = Column(Integer, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
