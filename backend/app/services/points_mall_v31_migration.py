"""v3.1 积分商城迁移（PRD v2 合并发版）.

执行内容（全部幂等）：
1. ``points_mall_items`` 表增加字段：
   - ``detail_html`` TEXT NULL — 富文本详情
   - ``ref_coupon_id`` INT NULL — 关联 coupons.id（type=coupon）
   - ``ref_service_id`` INT NULL — 关联 products.id（type=service）
   - ``limit_per_user`` INT NOT NULL DEFAULT 0 — 每人限兑次数
2. ``points_mall_items.type`` 列若为 ENUM 类型，改为 VARCHAR(30)，避免追加 coupon 时因 ENUM 缺值 400 报错
   （配合代码 side enum 扩展，彻底修 Bug1）
3. 一次性反解老商品 ``description`` 里的 ``ref_coupon_id=xx``、``ref_service_id=xx``、
   ``ref_service_type=xx`` 字符串，搬到新独立字段；保留纯描述文本。
4. 打上 SystemConfig.points_mall_v31_migrated = "1" 防止重复执行。

全程 try/except，**不阻塞启动**。
"""
from __future__ import annotations

import logging
import re

_logger = logging.getLogger(__name__)


async def migrate_points_mall_v31() -> None:
    from sqlalchemy import select as _sel, text

    from app.core.database import async_session
    from app.models.models import PointsMallItem, SystemConfig

    try:
        async with async_session() as db:
            # 0. 如果已迁移过就跳过
            mark = (
                await db.execute(
                    _sel(SystemConfig).where(
                        SystemConfig.config_key == "points_mall_v31_migrated"
                    )
                )
            ).scalar_one_or_none()
            if mark and mark.config_value == "1":
                return

            # 1. 加列（幂等）
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
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加列 %s.%s 跳过：%s", table, column, e)

            await _add_col(
                "points_mall_items", "detail_html", "detail_html TEXT NULL"
            )
            await _add_col(
                "points_mall_items", "ref_coupon_id", "ref_coupon_id INT NULL"
            )
            await _add_col(
                "points_mall_items", "ref_service_id", "ref_service_id INT NULL"
            )
            await _add_col(
                "points_mall_items",
                "limit_per_user",
                "limit_per_user INT NOT NULL DEFAULT 0",
            )

            # 2. 把 type 列从 ENUM 改成 VARCHAR(30)（Bug1 — 老 ENUM 不含 coupon 会 400）
            try:
                await db.execute(
                    text(
                        "ALTER TABLE points_mall_items MODIFY COLUMN type VARCHAR(30) NOT NULL DEFAULT 'virtual'"
                    )
                )
                _logger.info("points_mall_items.type 列已改为 VARCHAR(30)")
            except Exception as e:  # noqa: BLE001
                _logger.debug("type 列 MODIFY 跳过：%s", e)

            # 3. 反解老商品 description，迁移到独立字段
            items = (await db.execute(_sel(PointsMallItem))).scalars().all()
            pat_coupon = re.compile(r"ref_coupon_id\s*=\s*(\d+)")
            pat_sid = re.compile(r"ref_service_id\s*=\s*(\d+)")
            pat_stype = re.compile(r"ref_service_type\s*=\s*([A-Za-z_]+)")
            migrated = 0
            for it in items:
                desc = it.description or ""
                touched = False
                m1 = pat_coupon.search(desc)
                if m1 and not getattr(it, "ref_coupon_id", None):
                    try:
                        it.ref_coupon_id = int(m1.group(1))
                        touched = True
                    except Exception:
                        pass
                m2 = pat_sid.search(desc)
                if m2 and not getattr(it, "ref_service_id", None):
                    try:
                        it.ref_service_id = int(m2.group(1))
                        touched = True
                    except Exception:
                        pass
                # ref_service_type 不再保留（体验服务统一用 products 表），仅剥离
                if touched or pat_stype.search(desc):
                    # 剥离所有 ref_xxx=xx 片段；清理多余分隔符
                    cleaned = desc
                    cleaned = pat_coupon.sub("", cleaned)
                    cleaned = pat_sid.sub("", cleaned)
                    cleaned = pat_stype.sub("", cleaned)
                    cleaned = re.sub(r";;+", ";", cleaned)
                    cleaned = cleaned.strip().strip(";").strip()
                    it.description = cleaned
                    migrated += 1
                    _logger.info(
                        "points_mall_v31: 迁移商品 id=%s name=%s -> ref_coupon_id=%s ref_service_id=%s",
                        it.id,
                        it.name,
                        it.ref_coupon_id,
                        it.ref_service_id,
                    )

            # 4. 写标记
            if mark:
                mark.config_value = "1"
            else:
                db.add(
                    SystemConfig(
                        config_key="points_mall_v31_migrated",
                        config_value="1",
                        config_type="points",
                        description="v3.1 积分商城字段迁移（detail_html/ref_*/limit_per_user + description 反解）",
                    )
                )
            await db.commit()
            _logger.info("v3.1 积分商城迁移完成，共迁移 %s 条商品", migrated)
    except Exception as e:  # noqa: BLE001
        _logger.error("v3.1 积分商城迁移异常（不影响启动）：%s", e)
