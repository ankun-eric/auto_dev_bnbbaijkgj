"""底部导航 `订单` 路径迁移：/orders -> /unified-orders.

背景：2026-04-21 发现「后台底部导航配置」中"订单"项默认 path 仍为 `/orders`，
但 H5 和小程序端的订单页实际路由已升级为 `/unified-orders`，导致用户点击跳 404。

本迁移将存量的 `bottom_nav_config` 表中 `path='/orders'` 且 `name` 属于订单相关命名
（订单/我的订单/Orders）的记录统一改为 `/unified-orders`。

特性：
- 幂等：没有匹配记录时直接跳过；重复执行不会产生副作用
- 精确匹配：同时按 path + name 匹配，避免误伤自定义菜单
- 详细日志：每条被修改的记录都打印 id / name / 原 path / 新 path，
  便于出问题时人工 SQL 恢复
- 异常隔离：失败时记 ERROR 日志但不抛出，保证应用启动不被阻塞
"""
import logging

from sqlalchemy import select, update

from app.core.database import async_session as _async_session
from app.models.models import BottomNavConfig

logger = logging.getLogger(__name__)

_ORDER_NAMES = ("订单", "我的订单", "Orders")
_OLD_PATH = "/orders"
_NEW_PATH = "/unified-orders"


async def migrate_bottom_nav_order_path() -> None:
    """将 bottom_nav_config 中订单项的老路径 /orders 改为 /unified-orders（幂等）。"""
    try:
        async with _async_session() as db:
            result = await db.execute(
                select(BottomNavConfig).where(
                    BottomNavConfig.path == _OLD_PATH,
                    BottomNavConfig.name.in_(_ORDER_NAMES),
                )
            )
            rows = result.scalars().all()

            if not rows:
                logger.info("[bottom_nav_migration] 无需迁移，跳过（未发现 path=/orders 的订单项）")
                return

            for row in rows:
                logger.warning(
                    "[bottom_nav_migration] 迁移记录 id=%s name=%s old_path=%s -> new_path=%s",
                    row.id,
                    row.name,
                    row.path,
                    _NEW_PATH,
                )

            await db.execute(
                update(BottomNavConfig)
                .where(
                    BottomNavConfig.path == _OLD_PATH,
                    BottomNavConfig.name.in_(_ORDER_NAMES),
                )
                .values(path=_NEW_PATH)
            )
            await db.commit()

            logger.info(
                "[bottom_nav_migration] 迁移完成，共更新 %d 条记录 %s -> %s",
                len(rows),
                _OLD_PATH,
                _NEW_PATH,
            )
    except Exception as e:  # noqa: BLE001
        logger.error("[bottom_nav_migration] 迁移异常（不影响启动）：%s", e)
