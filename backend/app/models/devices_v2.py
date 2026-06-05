"""[PRD-MY-DEVICES-V1 2026-05-21] 「我的设备」V2 数据模型。

新增两张表：

- `device_catalog`：品牌设备目录（启动时按 SEED_CATALOG 幂等 seed）。
- `device_user_bindings`：用户绑定关系，支持软删除 + 同 SN 多账户共享。

不复用旧表 `device_bindings`（PRD-469 M9），是为了避免破坏存量数据 & 字段语义。
旧 `/api/prd469/device/list` 与 `/api/devices/list` 仍保留兼容，本模块只对外暴露新版
`/api/devices/*` 接口。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import mapped_column

from app.core.database import Base


class DeviceCatalog(Base):
    """支持设备目录。

    主键：(brand_code, device_name) 在应用层视为业务唯一键（seed 时按此匹配）。
    数据库层使用自增 id 主键，便于外键引用。

    [PRD-HEALTH-ARCHIVE-CO-MANAGE 2026-06-05] 新增 scene_group_id / jump_url / icon_url 字段，
    icon 字段扩展为 500 字符以支持图片 URL。
    """

    __tablename__ = "device_catalog"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_code = mapped_column(String(32), nullable=False, index=True)
    brand_name = mapped_column(String(64), nullable=False)
    category_code = mapped_column(String(64), nullable=False, index=True)
    device_name = mapped_column(String(128), nullable=False)
    icon = mapped_column(String(500), nullable=True)
    scene_group_id = mapped_column(Integer, ForeignKey("device_scene_group.id"), nullable=True, index=True)
    jump_url = mapped_column(String(500), nullable=True)
    icon_url = mapped_column(String(500), nullable=True)
    is_active = mapped_column(Boolean, default=False, nullable=False)
    is_unique = mapped_column(Boolean, default=True, nullable=False)
    sort_order = mapped_column(Integer, default=0, nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class DeviceUserBinding(Base):
    """用户设备绑定关系（V2，支持同 SN 多账户、软删除、可多绑）。"""

    __tablename__ = "device_user_bindings"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    catalog_id = mapped_column(Integer, ForeignKey("device_catalog.id"), nullable=False, index=True)
    sn = mapped_column(String(128), nullable=False, index=True)
    alias = mapped_column(String(64), nullable=True)
    member_id = mapped_column(Integer, ForeignKey("family_members.id"), nullable=True, index=True)
    bound_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    unbound_at = mapped_column(DateTime, nullable=True)
    is_active = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
