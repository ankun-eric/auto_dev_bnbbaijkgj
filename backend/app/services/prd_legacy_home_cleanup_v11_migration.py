"""
[PRD-LEGACY-HOME-CLEANUP-V1.1 2026-05-19] 管理后台「首页配置」遗留菜单下线清理

执行内容（一次性，幂等）：
  1) 清 app_settings.page_style 一条 KV（page_style 切换 UI 已物理下线）
  2) 清 system_config 表 home_* KV（保留 home_font_* 字段，仅清旧 /home 专用字段）
  3) 物理删表：home_menus（首页菜单管理已下线）
     （注意：仅删除业务表本身，model 类仍保留供小程序/Flutter 用户端 GET 接口继续读取）
     ⚠️ 由于用户端 GET /api/home-menus 仍需返回数据，本次实际**不 DROP** home_menus 表，
        只是后台不再写入；DROP 操作改为放到 v1.2（小程序/Flutter 改造完成后）。
        本迁移仅清旧 KV + Banner link_url 治理，避免线上小程序/Flutter 老首页菜单全空。
  4) 一次性 banner link_url 数据治理：
       - link_url='/home' → '/ai-home'
       - link_url LIKE '/home/menu/%' 或 '/menu-mode/%' → is_visible=FALSE（自动下架）
  5) 把上述 banner 治理写入临时审计表 banner_migration_log_20260519，方便事后回查

幂等性：
  通过 app_settings 中 `_migration_done.prd_legacy_home_cleanup_v11` 标志，
  迁移完成后不再重复执行（每次重启幂等）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import text


_logger = logging.getLogger("app.prd_legacy_home_cleanup_v11")

_FLAG_KEY = "_migration_done.prd_legacy_home_cleanup_v11"


async def run_migration_with_session(async_session_factory) -> Dict[str, Any]:
    """对外入口：执行 PRD v1.1 遗留菜单下线清理迁移。"""
    stats: Dict[str, Any] = {
        "page_style_deleted": 0,
        "home_config_kv_deleted": 0,
        "banner_link_url_migrated": 0,
        "banner_hidden_for_legacy_path": 0,
        "audit_rows_inserted": 0,
        "skipped": False,
    }

    async with async_session_factory() as db:
        try:
            res_flag = await db.execute(
                text("SELECT `value` FROM app_settings WHERE `key` = :k LIMIT 1"),
                {"k": _FLAG_KEY},
            )
            done = res_flag.scalar_one_or_none()
            if done == "done":
                stats["skipped"] = True
                _logger.info("已迁移过，跳过 (%s=done)", _FLAG_KEY)
                return stats
        except Exception as e:
            _logger.warning("读取迁移标志失败（首次执行属正常）: %s", e)

        try:
            # 1) 清 app_settings.page_style
            r1 = await db.execute(
                text("DELETE FROM app_settings WHERE `key` = 'page_style'")
            )
            stats["page_style_deleted"] = r1.rowcount or 0

            # 2) 清 system_configs 表 home_* KV（保留 home_font_*）
            # 注意：实际表名是 system_configs（复数）—— PRD 中误写为 system_config。
            r2 = await db.execute(
                text(
                    """
                    DELETE FROM system_configs
                    WHERE `config_key` LIKE 'home_%%'
                      AND `config_key` NOT LIKE 'home_font_%%'
                    """
                )
            )
            stats["home_config_kv_deleted"] = r2.rowcount or 0

            # 4-a) 建审计表（IF NOT EXISTS 幂等）
            await db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS banner_migration_log_20260519 (
                        id INT NOT NULL,
                        old_link_url VARCHAR(500) NULL,
                        new_link_url VARCHAR(500) NULL,
                        new_is_visible BOOLEAN NULL,
                        migrated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id, migrated_at)
                    )
                    """
                )
            )

            # 4-b) 先写审计（在做实际更新之前快照旧值）
            r_audit = await db.execute(
                text(
                    """
                    INSERT INTO banner_migration_log_20260519 (
                        id, old_link_url, new_link_url, new_is_visible
                    )
                    SELECT id,
                           link_url AS old_link_url,
                           CASE WHEN link_url = '/home' THEN '/ai-home'
                                ELSE link_url END AS new_link_url,
                           CASE WHEN link_url LIKE '/home/menu/%%'
                                  OR link_url LIKE '/menu-mode/%%'
                                THEN FALSE ELSE TRUE END AS new_is_visible
                    FROM home_banners
                    WHERE link_url = '/home'
                       OR link_url LIKE '/home/menu/%%'
                       OR link_url LIKE '/menu-mode/%%'
                    """
                )
            )
            stats["audit_rows_inserted"] = r_audit.rowcount or 0

            # 4-c) banner /home → /ai-home
            r3 = await db.execute(
                text(
                    """
                    UPDATE home_banners
                    SET link_url = '/ai-home', updated_at = NOW()
                    WHERE link_url = '/home'
                    """
                )
            )
            stats["banner_link_url_migrated"] = r3.rowcount or 0

            # 4-d) 指向旧菜单子页的 banner 自动下架
            r4 = await db.execute(
                text(
                    """
                    UPDATE home_banners
                    SET is_visible = FALSE, updated_at = NOW()
                    WHERE link_url LIKE '/home/menu/%%'
                       OR link_url LIKE '/menu-mode/%%'
                    """
                )
            )
            stats["banner_hidden_for_legacy_path"] = r4.rowcount or 0

            # 写迁移完成标志
            await db.execute(
                text(
                    """
                    INSERT INTO app_settings (`key`, `value`, `description`)
                    VALUES (:k, 'done', 'PRD-LEGACY-HOME-CLEANUP-V1.1 迁移完成标志')
                    ON DUPLICATE KEY UPDATE `value`='done'
                    """
                ),
                {"k": _FLAG_KEY},
            )

            await db.commit()
            _logger.info("PRD-LEGACY-HOME-CLEANUP-V1.1 迁移完成 stats=%s", stats)
        except Exception as e:
            await db.rollback()
            _logger.error("PRD-LEGACY-HOME-CLEANUP-V1.1 迁移失败: %s", e)
            raise

    return stats
