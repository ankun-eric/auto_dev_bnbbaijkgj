"""[PRD-HEALTH-ARCHIVE-V5-20260521] 健康档案与就医资料优化迁移脚本。

新增表：
1. `health_alerts`          —— 健康预警条目（体检/用药/设备/手动 4 类来源）
2. `medical_records`        —— 就医资料（4 分组：病例单/体检报告/药物/其他）
3. `medical_record_files`   —— 单份资料的文件附件（图片/PDF），1 份资料 ≤ 9 文件

设计原则（极度保守）：
- 幂等：可重复执行；通过 INFORMATION_SCHEMA 检查表/列是否已存在
- 不影响主启动流程：任何步骤失败仅记录日志、不抛错
- 删除走软删除（is_deleted + deleted_at），物理删除由回收站 30 天 cron 处理
"""
from __future__ import annotations

import logging
from typing import Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)

_PHASE = "health_archive_v5"


async def _table_exists(db: AsyncSession, table_name: str) -> bool:
    try:
        res = await db.execute(
            text(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
            ),
            {"t": table_name},
        )
        return (res.scalar() or 0) > 0
    except Exception as e:  # noqa: BLE001
        _logger.warning("[%s] _table_exists(%s) failed: %s", _PHASE, table_name, e)
        return False


async def _create_health_alerts(db: AsyncSession) -> bool:
    if await _table_exists(db, "health_alerts"):
        return False
    await db.execute(
        text(
            """
            CREATE TABLE health_alerts (
              id INT NOT NULL AUTO_INCREMENT,
              user_id INT NOT NULL COMMENT '账号 owner（登录用户）',
              member_id INT NULL COMMENT '家庭成员 ID，NULL 表示本人',
              alert_type VARCHAR(16) NOT NULL COMMENT 'checkup/medication/device/manual',
              indicator VARCHAR(64) NOT NULL COMMENT '具体指标项（血压/血糖/漏服等）',
              title VARCHAR(255) NOT NULL,
              detail TEXT NULL,
              severity VARCHAR(8) NOT NULL DEFAULT 'medium' COMMENT 'high/medium/low',
              source_label VARCHAR(128) NULL COMMENT '来源标签（设备名 / 报告标题）',
              advice TEXT NULL COMMENT '简要建议（模板优先 + AI 缓存）',
              raw_payload JSON NULL COMMENT '抽屉「关联原始数据」展示用',
              ref_record_id INT NULL COMMENT '关联就医资料 id',
              ref_plan_id INT NULL COMMENT '关联用药计划 id',
              ref_device_id INT NULL COMMENT '关联设备绑定 id',
              merged_count INT NOT NULL DEFAULT 1 COMMENT '24h 窗口内合并次数',
              last_occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              status VARCHAR(8) NOT NULL DEFAULT 'open' COMMENT 'open/done',
              resolved_at DATETIME NULL,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                         ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_ha_user_member (user_id, member_id),
              KEY idx_ha_status (status),
              KEY idx_ha_type (alert_type),
              KEY idx_ha_merge (user_id, member_id, alert_type, indicator, status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    await db.commit()
    return True


async def _create_medical_records(db: AsyncSession) -> bool:
    if await _table_exists(db, "medical_records"):
        return False
    await db.execute(
        text(
            """
            CREATE TABLE medical_records (
              id INT NOT NULL AUTO_INCREMENT,
              user_id INT NOT NULL,
              member_id INT NULL COMMENT '家庭成员 ID，NULL=本人',
              category VARCHAR(16) NOT NULL COMMENT 'case_note/checkup_report/drug/other',
              title VARCHAR(255) NOT NULL,
              record_date DATE NULL COMMENT '资料对应日期（用户填写）',
              source VARCHAR(16) NOT NULL DEFAULT 'manual'
                COMMENT 'ai_checkup/ai_drug/manual',
              ai_interpretation JSON NULL COMMENT 'AI 解读结构化结果',
              remark TEXT NULL COMMENT '用户备注',
              is_deleted TINYINT(1) NOT NULL DEFAULT 0
                COMMENT '0 正常 / 1 进入回收站',
              deleted_at DATETIME NULL COMMENT '回收站到期 = deleted_at + 30 天',
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                         ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_mr_user_member (user_id, member_id),
              KEY idx_mr_category (category),
              KEY idx_mr_deleted (is_deleted),
              KEY idx_mr_date (record_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    await db.commit()
    return True


async def _create_medical_record_files(db: AsyncSession) -> bool:
    if await _table_exists(db, "medical_record_files"):
        return False
    await db.execute(
        text(
            """
            CREATE TABLE medical_record_files (
              id INT NOT NULL AUTO_INCREMENT,
              record_id INT NOT NULL,
              file_url VARCHAR(512) NOT NULL,
              file_name VARCHAR(255) NOT NULL,
              file_type VARCHAR(16) NOT NULL DEFAULT 'image'
                COMMENT 'image/pdf',
              file_size INT NULL,
              sort_order INT NOT NULL DEFAULT 0,
              created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (id),
              KEY idx_mrf_record (record_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    await db.commit()
    return True


async def run_migration_with_session(db: AsyncSession) -> Dict[str, int]:
    """主入口：创建 3 张表（幂等）。"""
    stats = {"health_alerts": 0, "medical_records": 0, "medical_record_files": 0}
    try:
        if await _create_health_alerts(db):
            stats["health_alerts"] = 1
        if await _create_medical_records(db):
            stats["medical_records"] = 1
        if await _create_medical_record_files(db):
            stats["medical_record_files"] = 1
    except Exception as e:  # noqa: BLE001
        _logger.error("[%s] migration failed: %s", _PHASE, e)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
    return stats
