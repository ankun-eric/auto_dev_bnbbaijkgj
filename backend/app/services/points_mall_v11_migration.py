"""积分商城 v1.1 迁移（PRD 积分商城商品管理优化 v1.1）.

执行内容（全部幂等）：
1. ``points_mall_items`` 表增加字段：
   - ``goods_status`` VARCHAR(16) NOT NULL DEFAULT 'draft' — 三态：draft/on_sale/off_sale
   - ``replaced_by_goods_id`` INT NULL — 被替代指向
   - ``copied_from_goods_id`` INT NULL — 复制源指向
   - ``sort_weight`` INT NOT NULL DEFAULT 0 — 排序权重
2. 根据现有 ``status`` 字段回填 ``goods_status``：
   - status='active' → goods_status='on_sale'
   - status 其他 → goods_status='off_sale'（保持现状不变为 draft，以免隐藏已上架商品）
3. 新建表 ``points_mall_goods_change_log``（商品修改历史）。
4. 打标记 ``points_mall_v11_migrated=1`` 防止重复。

全程 try/except，不阻塞启动。
"""
from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


async def migrate_points_mall_v11() -> None:
    from sqlalchemy import select as _sel, text
    from app.core.database import async_session
    from app.models.models import SystemConfig

    try:
        async with async_session() as db:
            mark = (
                await db.execute(
                    _sel(SystemConfig).where(
                        SystemConfig.config_key == "points_mall_v11_migrated"
                    )
                )
            ).scalar_one_or_none()
            if mark and mark.config_value == "1":
                return

            async def _add_col(table: str, column: str, ddl: str) -> None:
                try:
                    chk = await db.execute(
                        text(
                            "SELECT COUNT(*) FROM information_schema.columns "
                            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
                        ),
                        {"t": table, "c": column},
                    )
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                        _logger.info("添加列 %s.%s 成功", table, column)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加列 %s.%s 跳过：%s", table, column, e)

            # 1. 加列
            await _add_col(
                "points_mall_items",
                "goods_status",
                "goods_status VARCHAR(16) NOT NULL DEFAULT 'draft'",
            )
            await _add_col(
                "points_mall_items",
                "replaced_by_goods_id",
                "replaced_by_goods_id INT NULL",
            )
            await _add_col(
                "points_mall_items",
                "copied_from_goods_id",
                "copied_from_goods_id INT NULL",
            )
            await _add_col(
                "points_mall_items",
                "sort_weight",
                "sort_weight INT NOT NULL DEFAULT 0",
            )

            # 2. 回填 goods_status
            try:
                await db.execute(
                    text(
                        "UPDATE points_mall_items "
                        "SET goods_status='on_sale' "
                        "WHERE (goods_status IS NULL OR goods_status='draft') AND status='active'"
                    )
                )
                await db.execute(
                    text(
                        "UPDATE points_mall_items "
                        "SET goods_status='off_sale' "
                        "WHERE (goods_status IS NULL OR goods_status='draft') AND (status IS NULL OR status<>'active')"
                    )
                )
            except Exception as e:  # noqa: BLE001
                _logger.debug("回填 goods_status 跳过：%s", e)

            # 3. 新建修改历史表
            try:
                await db.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS points_mall_goods_change_log (
                            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                            goods_id INT NOT NULL,
                            field_key VARCHAR(64) NOT NULL,
                            field_name VARCHAR(64) NOT NULL,
                            old_value TEXT NULL,
                            new_value TEXT NULL,
                            operator_id INT NULL,
                            operator_name VARCHAR(64) NULL,
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            INDEX idx_goods_id (goods_id),
                            INDEX idx_created_at (created_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                        """
                    )
                )
                _logger.info("points_mall_goods_change_log 表已创建/存在")
            except Exception as e:  # noqa: BLE001
                _logger.debug("建表 change_log 跳过：%s", e)

            # 4. 写标记
            if mark:
                mark.config_value = "1"
            else:
                db.add(
                    SystemConfig(
                        config_key="points_mall_v11_migrated",
                        config_value="1",
                        config_type="points",
                        description="v1.1 积分商城商品管理优化迁移（goods_status/replaced_by/copied_from/sort_weight + change_log 表）",
                    )
                )
            await db.commit()
            _logger.info("v1.1 积分商城迁移完成")
    except Exception as e:  # noqa: BLE001
        _logger.error("v1.1 积分商城迁移异常（不影响启动）：%s", e)
