import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.api import (
    account_security,
    addresses,
    addresses_v2,
    admin,
    order_enhancement,
    admin_health_plan,
    admin_merchant,
    admin_messages,
    admin_news,
    admin_search,
    ai_center,
    app_settings,
    appointment_form_admin,
    audit,
    auth,
    bottom_nav,
    cards,
    cards_admin,
    chat,
    chat_history,
    chat_share,
    city,
    constitution,
    content,
    cos,
    coupons,
    coupons_admin,
    customer_service,
    drug,
    drug_chat,
    drug_identify_share,
    email_notify,
    expert,
    family,
    family_management,
    favorites,
    feedback,
    font_setting,
    function_button,
    h5_checkout,
    health_plan_v2,
    health_profile,
    home_config,
    knowledge,
    maps,
    member_qr,
    messages,
    notice,
    notification,
    ocr,
    ocr_details,
    order,
    payment_config,
    payment_methods,
    plan,
    points,
    points_admin,
    points_exchange,
    merchant,
    merchant_v1,
    product_admin,
    products,
    prompt_templates,
    referral,
    report,
    report_interpret,
    checkup_api_v2,
    scan,
    search,
    service,
    sms,
    tcm,
    tcm_config,
    third_party_openapi,
    tts,
    unified_orders,
    upload,
    user_health_profile,
    users,
    video_consult_config,
    wechat_bindding,
    wechat_push,
)
from app.core.database import Base, engine
from app.core.price_formatter import PriceFormattedJSONResponse
from app.services.bottom_nav_migration import migrate_bottom_nav_order_path
from app.services.points_mall_v31_migration import migrate_points_mall_v31
from app.services.points_mall_v11_migration import migrate_points_mall_v11
from app.services.schema_sync import sync_register_schema
from app.services.user_no_migration import migrate_existing_users_user_no


async def _migrate_points_enums_and_config():
    """确保 PointsType 枚举包含 checkin/completeProfile，迁移打卡积分配置到新字段"""
    import logging
    _logger = logging.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text
            try:
                await db.execute(text(
                    "ALTER TABLE points_records MODIFY COLUMN type "
                    "ENUM('signin','task','invite','purchase','redeem','checkin','deduct','completeProfile') "
                    "NOT NULL"
                ))
                await db.commit()
                _logger.info("PointsType ENUM 列已同步")
            except Exception as e:
                await db.rollback()
                _logger.debug(f"PointsType ENUM 同步跳过（可能已是最新）: {e}")

            from app.models.models import SystemConfig
            from sqlalchemy import select as sa_select
            result = await db.execute(sa_select(SystemConfig).where(SystemConfig.config_key == "healthCheckIn"))
            if not result.scalar_one_or_none():
                old_result = await db.execute(
                    sa_select(SystemConfig).where(SystemConfig.config_key == "checkin_points_per_action")
                )
                old_config = old_result.scalar_one_or_none()
                if old_config and old_config.config_value and old_config.config_value != "0":
                    db.add(SystemConfig(config_key="healthCheckIn", config_value=old_config.config_value, config_type="points"))
                    _logger.info(f"已迁移 checkin_points_per_action -> healthCheckIn: {old_config.config_value}")

            result2 = await db.execute(sa_select(SystemConfig).where(SystemConfig.config_key == "healthCheckInDailyLimit"))
            if not result2.scalar_one_or_none():
                old_result2 = await db.execute(
                    sa_select(SystemConfig).where(SystemConfig.config_key == "checkin_points_daily_limit")
                )
                old_config2 = old_result2.scalar_one_or_none()
                if old_config2 and old_config2.config_value:
                    db.add(SystemConfig(config_key="healthCheckInDailyLimit", config_value=old_config2.config_value, config_type="points"))
                    _logger.info(f"已迁移 checkin_points_daily_limit -> healthCheckInDailyLimit: {old_config2.config_value}")

            # 到店签到积分键迁移：checkin_points_per_visit -> storeCheckIn（保留旧键）
            result3 = await db.execute(sa_select(SystemConfig).where(SystemConfig.config_key == "storeCheckIn"))
            if not result3.scalar_one_or_none():
                old_result3 = await db.execute(
                    sa_select(SystemConfig).where(SystemConfig.config_key == "checkin_points_per_visit")
                )
                old_cfg3 = old_result3.scalar_one_or_none()
                if old_cfg3 and old_cfg3.config_value:
                    db.add(SystemConfig(config_key="storeCheckIn", config_value=old_cfg3.config_value, config_type="points"))
                    _logger.info(f"已迁移 checkin_points_per_visit -> storeCheckIn: {old_cfg3.config_value}")
                else:
                    db.add(SystemConfig(config_key="storeCheckIn", config_value="5", config_type="points"))
            for k, default in [("storeCheckInDailyTimes", "0"), ("storeCheckInDailyLimit", "0")]:
                exist = await db.execute(sa_select(SystemConfig).where(SystemConfig.config_key == k))
                if not exist.scalar_one_or_none():
                    db.add(SystemConfig(config_key=k, config_value=default, config_type="points"))

            await db.commit()
    except Exception as e:
        _logger.error(f"积分枚举/配置迁移异常（不影响启动）: {e}")


async def _migrate_coupons_v2():
    """v2 优惠券有效期重构：增加 validity_days 字段 + TRUNCATE 旧券。"""
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text
            try:
                await db.execute(text(
                    "ALTER TABLE coupons ADD COLUMN IF NOT EXISTS validity_days INT NOT NULL DEFAULT 30"
                ))
            except Exception:
                # MySQL 5.7 不支持 IF NOT EXISTS；用 information_schema 检查
                try:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = 'coupons' AND column_name = 'validity_days'"
                    ))
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text("ALTER TABLE coupons ADD COLUMN validity_days INT NOT NULL DEFAULT 30"))
                except Exception as e:
                    _logger.debug("validity_days 列添加跳过: %s", e)
            try:
                chk2 = await db.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'user_coupons' AND column_name = 'expire_at'"
                ))
                if (chk2.scalar() or 0) == 0:
                    await db.execute(text("ALTER TABLE user_coupons ADD COLUMN expire_at DATETIME NULL"))
                chk3 = await db.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'user_coupons' AND column_name = 'source'"
                ))
                if (chk3.scalar() or 0) == 0:
                    await db.execute(text("ALTER TABLE user_coupons ADD COLUMN source VARCHAR(30) DEFAULT 'self'"))
                chk4 = await db.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'user_coupons' AND column_name = 'grant_id'"
                ))
                if (chk4.scalar() or 0) == 0:
                    await db.execute(text("ALTER TABLE user_coupons ADD COLUMN grant_id INT NULL"))
            except Exception as e:
                _logger.debug("user_coupons 字段添加跳过: %s", e)

            # 迁移标记键：仅首次启动 v2 时 TRUNCATE 旧券
            from app.models.models import SystemConfig as _SC
            from sqlalchemy import select as _sel
            mark = (await db.execute(_sel(_SC).where(_SC.config_key == "coupons_v2_truncated"))).scalar_one_or_none()
            if not mark:
                try:
                    await db.execute(text("DELETE FROM user_coupons"))
                    await db.execute(text("DELETE FROM coupons"))
                    db.add(_SC(config_key="coupons_v2_truncated", config_value="1", config_type="coupon"))
                    _logger.info("v2 优惠券：旧券与已领取记录已 TRUNCATE")
                except Exception as e:
                    _logger.error("旧优惠券 TRUNCATE 失败: %s", e)

            await db.commit()
    except Exception as e:
        _logger.error("优惠券 v2 迁移异常（不影响启动）: %s", e)


async def _migrate_coupons_v2_1():
    """V2.1 优惠券：禁删除（下架）+ 兑换码批次/明细 + 积分兑换次数预留。

    - coupons: 加列 is_offline / offline_reason / offline_at / offline_by / points_exchange_limit
    - coupon_code_batches: 加列 batch_no / claim_limit / expire_at / voided_at / voided_by / void_reason
        + 历史一次性唯一码批次回填 claim_limit = total_count
        + 历史一码通用批次回填 claim_limit = 9999（兜底）
        + 历史批次回填 batch_no = BATCH-{yyyymmdd}-{id:04d}
    - coupon_redeem_codes: 加列 voided_at / voided_by / void_reason
    - 新建 coupon_op_logs 表（由 metadata.create_all 自动建）
    - SystemConfig.coupons_v2_1_migrated 控制不重复执行
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text
            from app.models.models import SystemConfig as _SC
            from sqlalchemy import select as _sel

            mark = (await db.execute(_sel(_SC).where(_SC.config_key == "coupons_v2_1_migrated"))).scalar_one_or_none()
            if mark and mark.config_value == "1":
                return

            async def _add_col(table: str, column: str, ddl: str):
                try:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
                    ), {"t": table, "c": column})
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                except Exception as e:
                    _logger.debug("加列 %s.%s 跳过: %s", table, column, e)

            # coupons 表
            await _add_col("coupons", "is_offline", "is_offline TINYINT(1) NOT NULL DEFAULT 0")
            await _add_col("coupons", "offline_reason", "offline_reason VARCHAR(255) NULL")
            await _add_col("coupons", "offline_at", "offline_at DATETIME NULL")
            await _add_col("coupons", "offline_by", "offline_by INT NULL")
            await _add_col("coupons", "points_exchange_limit", "points_exchange_limit INT NULL")
            try:
                await db.execute(text("CREATE INDEX idx_coupons_offline ON coupons(is_offline)"))
            except Exception:
                pass

            # coupon_code_batches 表
            await _add_col("coupon_code_batches", "batch_no", "batch_no VARCHAR(64) NULL")
            await _add_col("coupon_code_batches", "claim_limit", "claim_limit INT NULL")
            await _add_col("coupon_code_batches", "expire_at", "expire_at DATETIME NULL")
            await _add_col("coupon_code_batches", "voided_at", "voided_at DATETIME NULL")
            await _add_col("coupon_code_batches", "voided_by", "voided_by INT NULL")
            await _add_col("coupon_code_batches", "void_reason", "void_reason VARCHAR(255) NULL")
            try:
                await db.execute(text("CREATE UNIQUE INDEX idx_batch_no ON coupon_code_batches(batch_no)"))
            except Exception:
                pass

            # coupon_redeem_codes 表
            await _add_col("coupon_redeem_codes", "voided_at", "voided_at DATETIME NULL")
            await _add_col("coupon_redeem_codes", "voided_by", "voided_by INT NULL")
            await _add_col("coupon_redeem_codes", "void_reason", "void_reason VARCHAR(255) NULL")

            # 历史回填 claim_limit + batch_no
            try:
                # 一次性唯一码：claim_limit = total_count
                await db.execute(text(
                    "UPDATE coupon_code_batches SET claim_limit = total_count "
                    "WHERE code_type = 'unique' AND (claim_limit IS NULL OR claim_limit = 0)"
                ))
                # 一码通用：兜底 9999
                await db.execute(text(
                    "UPDATE coupon_code_batches SET claim_limit = 9999 "
                    "WHERE code_type = 'universal' AND (claim_limit IS NULL OR claim_limit = 0)"
                ))
                # batch_no 回填（历史批次）
                await db.execute(text(
                    "UPDATE coupon_code_batches "
                    "SET batch_no = CONCAT('BATCH-', DATE_FORMAT(created_at, '%Y%m%d'), '-', LPAD(id, 4, '0')) "
                    "WHERE batch_no IS NULL OR batch_no = ''"
                ))
            except Exception as e:
                _logger.debug("批次历史回填跳过: %s", e)

            # 标记完成
            if mark:
                mark.config_value = "1"
            else:
                db.add(_SC(config_key="coupons_v2_1_migrated", config_value="1", config_type="coupon"))
            await db.commit()
            _logger.info("V2.1 优惠券迁移完成")
    except Exception as e:
        _logger.error("V2.1 优惠券迁移异常（不影响启动）: %s", e)


async def _migrate_coupons_scope_v2_2():
    """V2.2 优惠券适用范围 & 类型说明优化（PRD v1）：

    - coupons 表加列 exclude_ids JSON NULL（最多 50 个）
    - SystemConfig 写入 coupon_scope_max_products=100、coupon_exclude_max_products=50
      （已存在则不覆盖，保留运营手动调整后的值）
    - SystemConfig.coupons_v2_2_migrated 标记完成，避免重复执行
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text, select as _sel
            from app.models.models import SystemConfig as _SC

            mark = (await db.execute(
                _sel(_SC).where(_SC.config_key == "coupons_v2_2_migrated")
            )).scalar_one_or_none()
            if mark and mark.config_value == "1":
                return

            # exclude_ids 列：MySQL 5.7 兼容（不依赖 IF NOT EXISTS）
            try:
                chk = await db.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'coupons' AND column_name = 'exclude_ids'"
                ))
                if (chk.scalar() or 0) == 0:
                    await db.execute(text(
                        "ALTER TABLE coupons ADD COLUMN exclude_ids JSON NULL "
                        "COMMENT '排除商品ID列表（仅 scope=all/category 生效，最多 50 个）'"
                    ))
                    _logger.info("V2.2：coupons 表 exclude_ids 列已添加")
            except Exception as e:
                _logger.debug("coupons.exclude_ids 加列跳过: %s", e)

            # 系统配置默认值（不覆盖现有值）
            for key, val in [
                ("coupon_scope_max_products", "100"),
                ("coupon_exclude_max_products", "50"),
            ]:
                exists = (await db.execute(
                    _sel(_SC).where(_SC.config_key == key)
                )).scalar_one_or_none()
                if not exists:
                    db.add(_SC(
                        config_key=key, config_value=val, config_type="coupon",
                        description="优惠券适用范围/排除商品上限（v2.2）",
                    ))

            if mark:
                mark.config_value = "1"
            else:
                db.add(_SC(
                    config_key="coupons_v2_2_migrated",
                    config_value="1",
                    config_type="coupon",
                ))
            await db.commit()
            _logger.info("V2.2 优惠券适用范围迁移完成")
    except Exception as e:
        _logger.error("V2.2 优惠券适用范围迁移异常（不影响启动）: %s", e)


async def _migrate_product_categories_hierarchy():
    """BUG ⑤修复：本期 N — 修正商品分类「适老化改造」被错置为一级分类的问题。

    步骤：
    1. 查询 `product_categories` 表，输出所有 parent_id IS NULL 但名称看起来是子分类的异常清单。
    2. 对名为「适老化改造」的分类，将其 parent_id 设置为「居家服务」分类的 id（按需创建）。
    3. 顺手将 level 字段统一为 parent_id NULL → 1，否则 → 2。
    4. 通过 SystemConfig.product_category_hierarchy_fixed_v1 控制不重复执行。
    """
    import logging
    _logger = logging.getLogger(__name__)
    from app.core.database import async_session as _async_session
    from sqlalchemy import select as _sel
    from app.models.models import SystemConfig as _SC, ProductCategory as _PC
    try:
        async with _async_session() as db:
            mark = (await db.execute(
                _sel(_SC).where(_SC.config_key == "product_category_hierarchy_fixed_v1")
            )).scalar_one_or_none()
            if mark and mark.config_value == "1":
                return

            # ── 1. 查询是否存在「居家服务」一级分类，没有则创建 ──
            home_cat = (await db.execute(
                _sel(_PC).where(_PC.name == "居家服务", _PC.parent_id.is_(None))
            )).scalar_one_or_none()
            if not home_cat:
                home_cat = _PC(name="居家服务", parent_id=None, sort_order=99, level=1)
                db.add(home_cat)
                await db.flush()
                _logger.info("BUG⑤：补建一级分类「居家服务」id=%s", home_cat.id)

            # ── 2. 修正「适老化改造」的父级 ──
            elderly_cats = (await db.execute(
                _sel(_PC).where(_PC.name == "适老化改造")
            )).scalar_one_or_none()
            if elderly_cats:
                if elderly_cats.parent_id != home_cat.id:
                    _logger.info(
                        "BUG⑤：修正「适老化改造」parent_id %s → %s（居家服务）",
                        elderly_cats.parent_id, home_cat.id,
                    )
                    elderly_cats.parent_id = home_cat.id
                    elderly_cats.level = 2

            # ── 3. 全量统一 level 字段，避免前端按 level 渲染时出错 ──
            all_cats = (await db.execute(_sel(_PC))).scalars().all()
            for c in all_cats:
                expected_level = 1 if c.parent_id is None else 2
                if c.level != expected_level:
                    c.level = expected_level

            # ── 4. 标记完成（一次性）──
            if mark:
                mark.config_value = "1"
            else:
                db.add(_SC(
                    config_key="product_category_hierarchy_fixed_v1",
                    config_value="1",
                    config_type="product",
                ))
            await db.commit()
            _logger.info("BUG⑤：商品分类层级修复完成")
    except Exception as e:  # noqa: BLE001
        _logger.error("BUG⑤分类层级迁移异常（不影响启动）：%s", e)


async def _migrate_v7_search_placeholder():
    """v7 / v7.2 修复：将首页搜索栏 placeholder 旧值/乱码统一改为新文案。

    升级为 placeholder_v7_2_normalized 标志位——之前虽然已写过一次（旧标志位已存在），
    但后续运营/脏数据又把值改回"搜索健康服务/商品"等变体，这里再强制覆盖一次。
    升级后再次部署重启 backend 即可生效，仍然保持幂等（只会修正一次）。
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    try:
        from app.core.database import async_session
        from app.models.models import SystemConfig
        from sqlalchemy import select as _select

        async with async_session() as db:
            flag_res = await db.execute(
                _select(SystemConfig).where(SystemConfig.config_key == "placeholder_v7_2_normalized")
            )
            if flag_res.scalar_one_or_none():
                return
            new_text = "搜索您想要的健康服务"
            res = await db.execute(
                _select(SystemConfig).where(SystemConfig.config_key == "home_search_placeholder")
            )
            row = res.scalar_one_or_none()
            if row is None:
                db.add(SystemConfig(
                    config_key="home_search_placeholder",
                    config_value=new_text,
                    config_type="home",
                    description="首页搜索栏占位文本",
                ))
            else:
                row.config_value = new_text
            db.add(SystemConfig(
                config_key="placeholder_v7_2_normalized",
                config_value="1",
                config_type="system",
                description="v7.2 placeholder 文案规范化标记（强制覆盖一次）",
            ))
            await db.commit()
            _logger.info("v7.2：首页搜索栏 placeholder 已强制规范化")
    except Exception as e:  # noqa: BLE001
        _logger.error("v7.2 placeholder 迁移异常（不影响启动）：%s", e)


async def _migrate_v8_content():
    """v8：文章富文本化 + 资讯模块新增。

    - articles 表加列：content_html / author_name / comment_count / is_top / published_at
    - UserRole 枚举追加 content_editor
    - articles MODIFY content → NULL 允许（因为资讯/富文本文章可能只有 content_html）
    - 首次启动时初始化默认 article_categories
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text
            from app.models.models import SystemConfig as _SC, ArticleCategory as _AC
            from sqlalchemy import select as _sel

            async def _add_col(table: str, column: str, ddl: str):
                try:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
                    ), {"t": table, "c": column})
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                except Exception as e:
                    _logger.debug("加列 %s.%s 跳过: %s", table, column, e)

            # articles 表新增列
            await _add_col("articles", "content_html", "content_html MEDIUMTEXT NULL")
            await _add_col("articles", "author_name", "author_name VARCHAR(100) NULL")
            await _add_col("articles", "comment_count", "comment_count INT NOT NULL DEFAULT 0")
            await _add_col("articles", "is_top", "is_top TINYINT(1) NOT NULL DEFAULT 0")
            await _add_col("articles", "published_at", "published_at DATETIME NULL")
            # 允许 content NULL
            try:
                await db.execute(text("ALTER TABLE articles MODIFY content TEXT NULL"))
            except Exception as e:
                _logger.debug("articles.content NULL 修改跳过: %s", e)

            # 物理删除视频表与相关互动数据（v8 去除视频管理模块）
            try:
                await db.execute(text("DELETE FROM comments WHERE content_type='video'"))
                await db.execute(text("DELETE FROM favorites WHERE content_type='video'"))
                await db.execute(text("DROP TABLE IF EXISTS videos"))
                _logger.info("v8：已清理 videos 表与相关 comments/favorites 记录")
            except Exception as e:
                _logger.debug("videos 清理跳过: %s", e)

            # UserRole 枚举增加 content_editor
            try:
                await db.execute(text(
                    "ALTER TABLE users MODIFY COLUMN role "
                    "ENUM('user','admin','doctor','merchant','content_editor') NOT NULL DEFAULT 'user'"
                ))
            except Exception as e:
                _logger.debug("UserRole enum 迁移跳过: %s", e)

            # 初始化默认分类（仅首次）
            from sqlalchemy import func as _func
            mark = (await db.execute(_sel(_SC).where(_SC.config_key == "v8_content_initialized"))).scalar_one_or_none()
            if not mark:
                exist_cnt = (await db.execute(_sel(_func.count(_AC.id)))).scalar() or 0
                if exist_cnt == 0:
                    default_cats = [
                        ("健康科普", 1),
                        ("营养饮食", 2),
                        ("运动健身", 3),
                        ("心理健康", 4),
                        ("中医养生", 5),
                        ("疾病预防", 6),
                    ]
                    for name, order in default_cats:
                        db.add(_AC(name=name, sort_order=order, is_enabled=True))
                db.add(_SC(
                    config_key="v8_content_initialized",
                    config_value="1",
                    config_type="content",
                    description="v8 内容管理初始化标记（文章分类默认数据）",
                ))
            await db.commit()
            _logger.info("v8 内容管理迁移完成")
    except Exception as e:
        _l.getLogger(__name__).error("v8 内容管理迁移异常（不影响启动）: %s", e)


async def _migrate_merchant_role_unify_v1():
    """[2026-04-26 PRD v1.0 §R1] 商家角色统一治理：
    将 merchant_store_memberships.role_code 中的历史值归一化为 4 角色之一：
        verifier -> clerk
        staff    -> clerk
        owner    -> boss
        manager  -> store_manager
    并对 role_code 为空的行按 member_role 物理枚举回填。
    幂等可重入。失败不阻塞启动。
    """
    import logging as _l
    log = _l.getLogger(__name__)
    try:
        from sqlalchemy import text
        async with engine.begin() as conn:
            # 1) 历史别名 → 4 角色
            mapping = [
                ("verifier", "clerk"),
                ("staff", "clerk"),
                ("owner", "boss"),
                ("manager", "store_manager"),
            ]
            total = 0
            for old, new in mapping:
                res = await conn.execute(
                    text("UPDATE merchant_store_memberships SET role_code=:n WHERE role_code=:o"),
                    {"n": new, "o": old},
                )
                cnt = res.rowcount or 0
                total += cnt
                if cnt:
                    log.info("[R1] role_code %s -> %s : %d 条", old, new, cnt)
            # 2) role_code 为空 → 按 member_role 回填
            backfill = [
                ("owner", "boss"),
                ("store_manager", "store_manager"),
                ("finance", "finance"),
                ("verifier", "clerk"),
                ("staff", "clerk"),
            ]
            for mr, rc in backfill:
                res = await conn.execute(
                    text(
                        "UPDATE merchant_store_memberships "
                        "SET role_code=:rc "
                        "WHERE (role_code IS NULL OR role_code='') AND member_role=:mr"
                    ),
                    {"rc": rc, "mr": mr},
                )
                cnt = res.rowcount or 0
                total += cnt
                if cnt:
                    log.info("[R1] backfill role_code from member_role=%s -> %s : %d 条", mr, rc, cnt)
            log.info("[R1] 商家角色统一迁移完成，影响 %d 行", total)
    except Exception as _e:  # noqa: BLE001
        log.error("[R1] merchant_role_unify_v1 迁移异常（不影响启动）: %s", _e)


async def _migrate_user_addresses_v2():
    """[2026-05-05 用户地址改造 PRD v1.0] user_addresses 表加列：
    consignee_name / consignee_phone / province_code / city_code / district_code
    / detail / longitude / latitude / tag / is_deleted；并放宽旧字段 nullable。
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text

            async def _add_col(column: str, ddl: str):
                try:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = 'user_addresses' AND column_name = :c"
                    ), {"c": column})
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(f"ALTER TABLE user_addresses ADD COLUMN {ddl}"))
                        _logger.info("[address_v2] user_addresses.%s 列已添加", column)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加列 user_addresses.%s 跳过: %s", column, e)

            await _add_col("consignee_name", "consignee_name VARCHAR(20) NULL")
            await _add_col("consignee_phone", "consignee_phone VARCHAR(11) NULL")
            await _add_col("province_code", "province_code VARCHAR(6) NULL")
            await _add_col("city_code", "city_code VARCHAR(6) NULL")
            await _add_col("district_code", "district_code VARCHAR(6) NULL")
            await _add_col("detail", "detail VARCHAR(120) NULL")
            await _add_col("longitude", "longitude DECIMAL(10,7) NULL")
            await _add_col("latitude", "latitude DECIMAL(10,7) NULL")
            await _add_col("tag", "tag VARCHAR(12) NULL")
            await _add_col("is_deleted", "is_deleted TINYINT(1) NOT NULL DEFAULT 0")

            # 放宽旧字段（v1 表里可能 NOT NULL）；忽略错误
            for ddl in (
                "ALTER TABLE user_addresses MODIFY COLUMN name VARCHAR(100) NULL",
                "ALTER TABLE user_addresses MODIFY COLUMN phone VARCHAR(20) NULL",
                "ALTER TABLE user_addresses MODIFY COLUMN street VARCHAR(255) NULL",
                "ALTER TABLE user_addresses MODIFY COLUMN province VARCHAR(50) NULL",
                "ALTER TABLE user_addresses MODIFY COLUMN city VARCHAR(50) NULL",
                "ALTER TABLE user_addresses MODIFY COLUMN district VARCHAR(50) NULL",
            ):
                try:
                    await db.execute(text(ddl))
                except Exception as e:  # noqa: BLE001
                    _logger.debug("放宽 nullable 跳过: %s -- %s", ddl, e)

            await db.commit()
            _logger.info("[address_v2] user_addresses 迁移完成")
    except Exception as e:  # noqa: BLE001
        _logger.error("[address_v2] user_addresses 迁移异常（不影响启动）: %s", e)


async def _migrate_business_config_unify_v1():
    """[2026-05-05 营业管理入口收敛 PRD v1.0] DB 迁移：

    1. merchant_stores 加列：advance_days INT NULL、booking_cutoff_minutes INT NULL
    2. products 加列：booking_cutoff_minutes INT NULL
    全程幂等。
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text

            async def _add_col(table: str, column: str, ddl: str):
                try:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
                    ), {"t": table, "c": column})
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                        _logger.info("[business_config_unify_v1] %s.%s 列已添加", table, column)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加列 %s.%s 跳过: %s", table, column, e)

            await _add_col("merchant_stores", "advance_days",
                           "advance_days INT NULL COMMENT '门店级最早可提前 N 天预约'")
            await _add_col("merchant_stores", "booking_cutoff_minutes",
                           "booking_cutoff_minutes INT NULL COMMENT '门店级当日最晚提前 N 分钟截止'")
            await _add_col("products", "booking_cutoff_minutes",
                           "booking_cutoff_minutes INT NULL COMMENT '商品级当日最晚提前 N 分钟截止；NULL=继承门店级'")
            await db.commit()
            _logger.info("[business_config_unify_v1] 营业管理入口收敛 v1.0 迁移完成")
    except Exception as e:  # noqa: BLE001
        _logger.error("[business_config_unify_v1] 迁移异常（不影响启动）: %s", e)


async def _migrate_order_enhancement_v1():
    """[订单系统增强 PRD v1.0] 数据库迁移：

    1. notifications 表加列：order_id / event_type / read_at；created_at 加索引
    2. order_attachments 表加列：mime_type / thumbnail_url / deleted_at
    3. products 表加列：max_concurrent_override / service_duration_minutes
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text

            async def _add_col(table: str, column: str, ddl: str):
                try:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
                    ), {"t": table, "c": column})
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                        _logger.info("[order_enh] %s.%s 列已添加", table, column)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加列 %s.%s 跳过: %s", table, column, e)

            # notifications 表
            await _add_col("notifications", "order_id", "order_id INT NULL")
            await _add_col("notifications", "event_type", "event_type VARCHAR(64) NULL")
            await _add_col("notifications", "read_at", "read_at DATETIME NULL")
            try:
                await db.execute(text(
                    "CREATE INDEX idx_notifications_order_id ON notifications(order_id)"
                ))
            except Exception:  # noqa: BLE001
                pass
            try:
                await db.execute(text(
                    "CREATE INDEX idx_notifications_event_type ON notifications(event_type)"
                ))
            except Exception:  # noqa: BLE001
                pass

            # order_attachments 表
            await _add_col("order_attachments", "mime_type", "mime_type VARCHAR(64) NULL")
            await _add_col("order_attachments", "thumbnail_url", "thumbnail_url VARCHAR(500) NULL")
            await _add_col("order_attachments", "deleted_at", "deleted_at DATETIME NULL")

            # products 表
            await _add_col("products", "max_concurrent_override", "max_concurrent_override INT NULL")
            await _add_col("products", "service_duration_minutes", "service_duration_minutes INT NULL")

            await db.commit()
            _logger.info("[order_enh] 订单系统增强 v1.0 迁移完成")
    except Exception as e:  # noqa: BLE001
        _logger.error("[order_enh] 订单系统增强 v1.0 迁移异常（不影响启动）: %s", e)


async def _migrate_product_original_price_nullable():
    """[2026-04-27] 修复 original_price 不允许 NULL 的问题：
    1. ALTER products.original_price 为 NULLABLE
    2. 将历史 original_price = 0 的记录更新为 NULL
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text
            from app.models.models import SystemConfig as _SC
            from sqlalchemy import select as _sel

            mark = (await db.execute(
                _sel(_SC).where(_SC.config_key == "product_original_price_nullable_v1")
            )).scalar_one_or_none()
            if mark and mark.config_value == "1":
                return

            try:
                await db.execute(text(
                    "ALTER TABLE products MODIFY COLUMN original_price DECIMAL(10,2) NULL"
                ))
            except Exception as e:
                _logger.debug("products.original_price nullable 修改跳过: %s", e)

            result = await db.execute(text(
                "UPDATE products SET original_price = NULL WHERE original_price = 0"
            ))
            cleaned = result.rowcount or 0

            if mark:
                mark.config_value = "1"
            else:
                db.add(_SC(
                    config_key="product_original_price_nullable_v1",
                    config_value="1",
                    config_type="product",
                    description="商品原价字段 nullable 修复 + 历史数据清洗标记",
                ))
            await db.commit()
            _logger.info("商品原价 nullable 迁移完成，清洗了 %d 条 original_price=0 的记录", cleaned)
    except Exception as e:
        _logger.error("商品原价 nullable 迁移异常（不影响启动）: %s", e)


def _scan_route_conflicts(app: "FastAPI") -> list[dict]:
    """[2026-04-26 PRD v1.0 §B1] 扫描所有 (path, method) 重复的路由，输出报告。
    返回列表，每项: {path, method, endpoints: [name, ...]}
    """
    import logging as _l
    log = _l.getLogger(__name__)
    bucket: dict[tuple[str, str], list[str]] = {}
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None) or set()
        endpoint = getattr(r, "endpoint", None)
        if not path or endpoint is None:
            continue
        ep_name = f"{getattr(endpoint, '__module__', '?')}.{getattr(endpoint, '__name__', '?')}"
        for m in methods:
            key = (path, m.upper())
            bucket.setdefault(key, []).append(ep_name)
    conflicts = [
        {"path": p, "method": m, "endpoints": eps}
        for (p, m), eps in bucket.items()
        if len(eps) > 1
    ]
    if conflicts:
        log.warning("[B1] 检测到 %d 个路由冲突 (path,method 重复)：", len(conflicts))
        for c in conflicts:
            log.warning("[B1] %s %s -> %s", c["method"], c["path"], c["endpoints"])
    else:
        log.info("[B1] 路由冲突扫描通过：未发现 (path,method) 重复")
    return conflicts


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await sync_register_schema(conn)
    await _migrate_points_enums_and_config()
    await _migrate_coupons_v2()
    await _migrate_coupons_v2_1()
    await _migrate_coupons_scope_v2_2()
    await _migrate_product_categories_hierarchy()
    await _migrate_v7_search_placeholder()
    await _migrate_v8_content()
    # [2026-04-23] 报告解读/对比对话化
    try:
        from app.services.report_interpret_migration import migrate_report_interpret
        await migrate_report_interpret()
    except Exception as _e:
        import logging as _l
        _l.getLogger(__name__).error("report_interpret migration 异常（不影响启动）: %s", _e)
    await migrate_bottom_nav_order_path()
    await migrate_points_mall_v31()
    await migrate_points_mall_v11()
    await migrate_existing_users_user_no()
    # [2026-04-27] 商品原价字段修复：nullable + 历史数据清洗
    await _migrate_product_original_price_nullable()
    # [2026-05-04 订单系统增强 PRD v1.0] notifications/order_attachments/products 加列迁移
    await _migrate_order_enhancement_v1()
    # [2026-05-05 用户地址改造 PRD v1.0] user_addresses 加列迁移（v2 接口）
    await _migrate_user_addresses_v2()
    # [2026-04-26 PRD v1.0 §R1] 商家角色统一治理数据迁移
    await _migrate_merchant_role_unify_v1()
    # [2026-05-05 营业管理入口收敛 PRD v1.0] merchant_stores 加列 advance_days/booking_cutoff_minutes；
    # products 加列 booking_cutoff_minutes
    await _migrate_business_config_unify_v1()
    from app.init_data import init_default_data
    await init_default_data()
    from app.init_cities import init_cities
    from app.core.database import async_session
    async with async_session() as db:
        await init_cities(db)
        await db.commit()
    from app.services.notification_scheduler import init_scheduler, shutdown_scheduler
    init_scheduler()
    # [2026-04-25] 启动时恢复孤儿报告解读任务
    try:
        from app.api.report_interpret import recover_pending_sessions
        await recover_pending_sessions()
    except Exception as _e:  # noqa: BLE001
        import logging as _l
        _l.getLogger(__name__).error("recover_pending_sessions 异常（不影响启动）: %s", _e)
    yield
    shutdown_scheduler()


app = FastAPI(
    title="宾尼小康 AI健康管家",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    default_response_class=PriceFormattedJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(font_setting.router)
app.include_router(health_profile.router)
app.include_router(chat.router)
app.include_router(chat_history.router)
app.include_router(tcm.router)
app.include_router(constitution.router)
app.include_router(service.router)
# [2026-04-21] 老订单接口 /api/orders/* 已下线，统一走 /api/orders/unified
# app.include_router(order.router)
app.include_router(expert.router)
app.include_router(points.router)
app.include_router(points_admin.router)
app.include_router(points_exchange.router)
app.include_router(plan.router)
app.include_router(family.router)
app.include_router(family_management.router)
app.include_router(content.router)
app.include_router(notification.router)
app.include_router(customer_service.router)
app.include_router(drug.router)
app.include_router(upload.router)
app.include_router(admin.router)
app.include_router(admin.settings_router)
app.include_router(admin_merchant.router)
app.include_router(admin_news.router)
app.include_router(merchant.router)
# [核销订单过期+改期规则优化 v1.0] 门店联系信息（供订单卡片「联系商家」弹窗使用）
from app.api import stores_public  # noqa: E402
app.include_router(stores_public.router)

# [支付宝 H5 正式支付链路接入 v1.0] 异步通知接口（独立挂载，避免与 /api/orders 冲突）
from app.api import alipay_notify  # noqa: E402
app.include_router(alipay_notify.router)
app.include_router(merchant_v1.router)
app.include_router(merchant_v1.admin_router)
app.include_router(account_security.router)  # [PRD V1.0] 账号安全：图形验证码 / 个人信息 / 修改密码 / 员工 / 重置密码
app.include_router(sms.router)
app.include_router(email_notify.router)
app.include_router(wechat_push.router)
app.include_router(knowledge.router)
app.include_router(cos.router)
app.include_router(ai_center.router)
app.include_router(report.router)
app.include_router(report.admin_router)
app.include_router(report_interpret.router)
app.include_router(checkup_api_v2.router)
app.include_router(ocr.router)
app.include_router(ocr.admin_router)
app.include_router(ocr_details.router)
app.include_router(ocr_details.user_router)
app.include_router(prompt_templates.router)
app.include_router(drug_identify_share.router)
app.include_router(drug_chat.router)  # [2026-04-23 v1.2] 用药对话首条消息 + 重新生成
app.include_router(home_config.router)
app.include_router(home_config.admin_router)
app.include_router(notice.router)
app.include_router(notice.admin_router)
app.include_router(bottom_nav.router)
app.include_router(bottom_nav.admin_router)
app.include_router(search.router)
app.include_router(admin_search.router)
app.include_router(health_plan_v2.router)
app.include_router(admin_health_plan.router)
app.include_router(city.router)
app.include_router(city.admin_router)
app.include_router(function_button.router)
app.include_router(function_button.admin_router)
app.include_router(messages.router)
app.include_router(admin_messages.router)
app.include_router(referral.router)
app.include_router(scan.router)
app.include_router(tts.router)
app.include_router(tts.admin_router)
app.include_router(chat_share.router)
app.include_router(chat_share.admin_router)
app.include_router(products.router)
from app.api import services_filter as _services_filter  # OPT-1
app.include_router(_services_filter.router)
app.include_router(tcm_config.router)
app.include_router(tcm_config.admin_router)
app.include_router(unified_orders.router)
app.include_router(member_qr.router)
app.include_router(favorites.router)
app.include_router(coupons.router)
app.include_router(coupons_admin.router)
app.include_router(coupons_admin.partner_router)
app.include_router(coupons_admin.new_user_router)
app.include_router(audit.audit_phone_router)
app.include_router(audit.audit_router)
app.include_router(third_party_openapi.router)
app.include_router(addresses.router)
# [2026-05-05 用户地址改造 PRD v1.0] v2 接口：省市县三级 + 经纬度 + 标签 + 软删除 + 行政区划 + 版本检查
app.include_router(addresses_v2.router)
app.include_router(product_admin.router)
app.include_router(wechat_bindding.router)
app.include_router(appointment_form_admin.router)
app.include_router(users.router)
app.include_router(video_consult_config.router)
app.include_router(feedback.router)
app.include_router(app_settings.router)
app.include_router(user_health_profile.router)
# [2026-05-01 门店地图能力 PRD v1.0] 地图代理（逆地理编码/POI 搜索/静态地图）
app.include_router(maps.router)
# [2026-05-02 H5 下单流程优化 PRD v1.0] 支付页统一选择
app.include_router(h5_checkout.router)
# [2026-05-03 支付配置 PRD v1.0] 多端支付通道管理
app.include_router(payment_config.router)
app.include_router(payment_methods.router)
# [2026-05-04 订单系统增强 PRD v1.0] 营业时间/并发上限/时段切片/红点/列表附件元信息
app.include_router(order_enhancement.router)

# [2026-05-05 SDK 健康看板] 后台 SDK 健康检查接口
from app.api import admin_sdk_health as _admin_sdk_health  # noqa: E402
app.include_router(_admin_sdk_health.router)


# [2026-05-05 SDK 健康看板] 启动期 SDK 分级自检：核心缺失 → 容器退出；可选缺失 → CRITICAL 告警
@app.on_event("startup")
async def _sdk_health_startup_check() -> None:
    from app.core.sdk_health import run_startup_sdk_check
    run_startup_sdk_check()


# [Bug 修复] 启动期自检：路由挂载 + 加密密钥环境变量
@app.on_event("startup")
async def _payment_config_startup_self_check() -> None:
    _self_check_logger = logging.getLogger("app.payment_config")
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    if "/api/admin/payment-channels" not in paths:
        _self_check_logger.error(
            "[支付配置] /api/admin/payment-channels 路由未挂载！请检查 main.py。"
        )
    else:
        _self_check_logger.info("[支付配置] /api/admin/payment-channels 路由已正确挂载")
    enc_key = os.environ.get("PAYMENT_CONFIG_ENCRYPTION_KEY", "").strip()
    if not enc_key:
        _self_check_logger.warning(
            "[支付配置] 环境变量 PAYMENT_CONFIG_ENCRYPTION_KEY 未配置，"
            "已使用项目内置 fallback 32 字节密钥（仅适用于开发/测试环境）。"
            "生产环境请通过 docker-compose environment 注入此变量。"
        )
    else:
        _self_check_logger.info(
            "[支付配置] 检测到 PAYMENT_CONFIG_ENCRYPTION_KEY 环境变量"
        )
# [2026-05-03 卡管理 v2.0 第 2~5 期] 购卡下单/动态核销码/退款/续卡/拆单/省钱提示/可续卡列表
# 先注册 v2 路由（精确路径优先），避免被 cards.router 的 /me/{user_card_id} 拦截 /me/renewable
from app.api import cards_v2 as _cards_v2  # noqa: E402
from app.api import cards_admin_v2 as _cards_admin_v2  # noqa: E402
app.include_router(_cards_v2.router)
app.include_router(_cards_v2.staff_router)
app.include_router(_cards_v2.order_card_router)
app.include_router(_cards_v2.product_card_router)
app.include_router(_cards_admin_v2.router)
app.include_router(_cards_admin_v2.poster_router)
# [2026-05-02 卡功能 PRD v1.1 第 1 期] C 端卡 API + Admin 卡管理（含动态路径，需在 v2 之后注册）
app.include_router(cards.router)
app.include_router(cards_admin.router)

# [门店预约看板与改期能力升级 v1.0] 门店端 9 宫格看板聚合接口（日/周/月/抽屉）
from app.api import merchant_dashboard as _merchant_dashboard  # noqa: E402
app.include_router(_merchant_dashboard.router)

# [PRD-01 全平台固定时段切片体系 v1.0] 全平台公共接口（含 /api/common/time-slots）
from app.api import common as _common_api  # noqa: E402
app.include_router(_common_api.router)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ───────────────── 全局异常处理器（BUG-PRODUCT-APPT-001）─────────────────
# 目的：将底层 SQLAlchemy / Python 异常转成 400 并附明确 detail，
# 彻底告别前端孤立的"操作失败"。
_exception_logger = logging.getLogger("app.exception")


@app.exception_handler(LookupError)
async def _lookup_error_handler(request: Request, exc: LookupError):
    _exception_logger.warning("LookupError at %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=400,
        content={"detail": f"枚举值不合法：{exc}"},
    )


@app.exception_handler(IntegrityError)
async def _integrity_error_handler(request: Request, exc: IntegrityError):
    _exception_logger.warning("IntegrityError at %s: %s", request.url.path, exc)
    msg = "数据约束冲突，请检查必填字段与唯一性"
    orig = getattr(exc, "orig", None)
    if orig is not None:
        text = str(orig)
        if "foreign key" in text.lower():
            msg = "关联数据不存在，请检查所绑定的表单/分类是否有效"
        elif "duplicate" in text.lower():
            msg = "数据重复，请检查唯一字段"
    return JSONResponse(status_code=400, content={"detail": msg})


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "bini-health-api"}
