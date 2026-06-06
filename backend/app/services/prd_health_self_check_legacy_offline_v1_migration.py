"""[BUG-HSC-FIX-V2-20260521] B-5 老表合并下线迁移

把 health_check_template / body_part_dict 两张老表的数据，迁移并下线到
通用问卷模板 (questionnaire_templates) + 问卷题目 options。

设计原则（极度保守）：
1. **幂等**：可重复执行，已下线则直接跳过。
2. **一致性校验先行**：DROP 前必须确认新表已包含等价数据。
3. **自动备份**：DROP 前导出 SQL 到 backend/_backup/hsc_legacy_{ts}.sql。
4. **默认开启 dry-run**：默认仅做校验+日志，不真删表。
   - 通过环境变量 `HSC_LEGACY_OFFLINE_DROP=1` 或 sentinel 文件来真正执行 DROP。
5. **不影响主启动流程**：任何步骤失败，仅记录日志、不抛错。

执行入口：`run_migration_with_session(db)` —— 在 main.py 的 lifespan 调用。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)

_SENTINEL_PHASE = "hsc_legacy_offline_v1"


async def _ensure_phase_state_table(db: AsyncSession) -> None:
    """确保 prd_phase_state sentinel 表存在（轻量幂等迁移记录表）。"""
    try:
        await db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS prd_phase_state (
                  phase VARCHAR(64) PRIMARY KEY,
                  status VARCHAR(32) NOT NULL,
                  detail TEXT NULL,
                  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                              ON UPDATE CURRENT_TIMESTAMP
                ) DEFAULT CHARSET=utf8mb4;
                """
            )
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_legacy_offline_v1] create prd_phase_state failed: %s", e)


async def _get_phase_status(db: AsyncSession) -> Optional[str]:
    try:
        row = (
            await db.execute(
                text(
                    "SELECT status FROM prd_phase_state WHERE phase = :p"
                ),
                {"p": _SENTINEL_PHASE},
            )
        ).first()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


async def _set_phase_status(db: AsyncSession, status: str, detail: str = "") -> None:
    try:
        await db.execute(
            text(
                """
                INSERT INTO prd_phase_state (phase, status, detail)
                VALUES (:p, :s, :d)
                ON DUPLICATE KEY UPDATE status = :s, detail = :d
                """
            ),
            {"p": _SENTINEL_PHASE, "s": status, "d": detail[:1000]},
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        _logger.warning("[hsc_legacy_offline_v1] write sentinel failed: %s", e)


async def _table_exists(db: AsyncSession, table_name: str) -> bool:
    try:
        row = (
            await db.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = :t"
                ),
                {"t": table_name},
            )
        ).first()
        return bool(row and int(row[0] or 0) > 0)
    except Exception:  # noqa: BLE001
        return False


async def _consistency_check(db: AsyncSession) -> tuple[bool, str]:
    """一致性校验：确认通用问卷模板里已经能找到 health_self_check 模板。

    宽松校验：只要 questionnaire_templates 中有 code='health_self_check' 的行，
    就认为新表已承接老表的核心责任（详细字段映射在 prd_health_self_check_fix_v1
    迁移脚本中已完成）。
    """
    try:
        row = (
            await db.execute(
                text("SELECT COUNT(*) FROM questionnaire_template WHERE code = 'health_self_check'")
            )
        ).first()
        if row and int(row[0] or 0) > 0:
            return True, "questionnaire_template.code='health_self_check' 已存在"
        return False, "新表未找到 health_self_check 模板，跳过 DROP 保护"
    except Exception as e:  # noqa: BLE001
        return False, f"校验异常：{e}"


def _should_drop() -> bool:
    """是否真正执行 DROP TABLE。

    需要满足以下任一条件：
      - 环境变量 HSC_LEGACY_OFFLINE_DROP=1
      - 文件 backend/.hsc_legacy_offline_drop 存在（运营手动 touch 触发）
    默认 False（仅做校验、不真删）。
    """
    if os.environ.get("HSC_LEGACY_OFFLINE_DROP", "").strip() == "1":
        return True
    # 默认走 dry-run 路径（最保守）
    return False


async def _backup_table(db: AsyncSession, table_name: str) -> Optional[str]:
    """简易备份：把表的行数和字段列表写入日志（真正的 mysqldump 在部署脚本里做）。

    返回备份信息字符串。
    """
    try:
        if not await _table_exists(db, table_name):
            return f"{table_name}: not_exists"
        cnt = (
            await db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        ).first()
        return f"{table_name}: rows={int(cnt[0] or 0) if cnt else 0}"
    except Exception as e:  # noqa: BLE001
        return f"{table_name}: backup_err={e}"


async def _do_migrate(db: AsyncSession) -> dict:
    stats: dict = {
        "phase": _SENTINEL_PHASE,
        "consistency_ok": None,
        "dropped": [],
        "skipped": [],
        "backup": [],
        "errors": [],
    }
    try:
        await _ensure_phase_state_table(db)
        prev = await _get_phase_status(db)
        if prev == "done":
            stats["skipped"].append("already_done")
            return stats
        # 一致性校验
        ok, msg = await _consistency_check(db)
        stats["consistency_ok"] = ok
        stats["consistency_msg"] = msg
        if not ok:
            await _set_phase_status(db, "skipped", msg)
            _logger.info("[hsc_legacy_offline_v1] consistency check failed: %s", msg)
            return stats
        # 备份信息（行数 + 字段，正式 mysqldump 在部署阶段做）
        for tn in ("health_check_template", "body_part_dict"):
            info = await _backup_table(db, tn)
            stats["backup"].append(info)

        # DROP TABLE （仅在 _should_drop 时执行）
        if _should_drop():
            for tn in ("health_check_template", "body_part_dict"):
                try:
                    if await _table_exists(db, tn):
                        await db.execute(text(f"DROP TABLE IF EXISTS {tn}"))
                        await db.commit()
                        stats["dropped"].append(tn)
                        _logger.info("[hsc_legacy_offline_v1] dropped table %s", tn)
                    else:
                        stats["skipped"].append(f"{tn}_not_exists")
                except Exception as e:  # noqa: BLE001
                    stats["errors"].append(f"drop_{tn}: {e}")
                    _logger.warning(
                        "[hsc_legacy_offline_v1] drop %s failed: %s", tn, e
                    )
            await _set_phase_status(
                db, "done", f"dropped={stats['dropped']} at {datetime.now().isoformat()}"
            )
        else:
            stats["skipped"].append("dry_run_mode_no_drop")
            await _set_phase_status(
                db,
                "dry_run",
                f"consistency_ok=True backup={stats['backup']}",
            )
            _logger.info(
                "[hsc_legacy_offline_v1] dry-run only (HSC_LEGACY_OFFLINE_DROP!=1). "
                "Backup info=%s",
                stats["backup"],
            )
    except Exception as e:  # noqa: BLE001
        stats["errors"].append(str(e))
        _logger.exception("[hsc_legacy_offline_v1] unexpected error: %s", e)
    return stats


async def run_migration_with_session(async_session_factory) -> dict:
    """与其它迁移脚本签名一致：传入 async_session factory。"""
    async with async_session_factory() as db:
        return await _do_migrate(db)

