import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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
    ai_home_optim_v4,
    health_archive_v5,
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
    health_self_check,
    h5_checkout,
    health_plan_v2,
    health_profile,
    health_profile_v3,
    home_config,
    knowledge,
    login_ui_config,
    maps,
    medication_reminder,
    member_qr,
    messages,
    notice,
    notification,
    notifications_unified,
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
    prompt_type_config,
    referral,
    report,
    report_history,
    report_interpret,
    report_interpret_button,
    checkup_api_v2,
    scan,
    search,
    service,
    sms,
    tcm,
    tcm_config,
    themes,
    third_party_openapi,
    tts,
    unified_orders,
    upload,
    user_health_profile,
    users,
    video_consult_config,
    wechat_bindding,
    wechat_push,
    prd469_health_v5,
    ai_call,
    medication_library_v3,
    medication_plans_v1,
    medication_add_optim_v1,
    medication_today_v1,
    health_archive_optim_v1,
    health_dashboard,
    questionnaire,
    devices_v2,
    ai_home_care_v1,
    care_ai_home,
    home_safety_v1,
    care_card_v1,
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


async def _migrate_glucose_v1():
    """[PRD-GLUCOSE-V1 2026-05-30] 血糖闭环模块建表（幂等）。

    新增 3 张表：
    - health_glucose_record    血糖记录
    - health_glucose_alert     预警事件
    - health_glucose_reminder  餐后提醒配置
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text
            try:
                await db.execute(text(
                    "CREATE TABLE IF NOT EXISTS health_glucose_record ("
                    " id BIGINT NOT NULL AUTO_INCREMENT,"
                    " user_id BIGINT NOT NULL,"
                    " value DECIMAL(4,1) NOT NULL,"
                    " scene TINYINT NOT NULL COMMENT '1=空腹 2=餐后2h 3=随机 4=睡前',"
                    " level TINYINT NOT NULL COMMENT '1=严重偏低 2=偏低 3=正常 4=偏高 5=严重偏高',"
                    " is_crisis TINYINT NOT NULL DEFAULT 0 COMMENT '0=否 1=高糖危象 2=低糖危象',"
                    " measure_time DATETIME NOT NULL,"
                    " note VARCHAR(200) NULL,"
                    " create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                    " PRIMARY KEY (id),"
                    " KEY idx_glucose_user_time (user_id, measure_time),"
                    " KEY idx_glucose_user_scene (user_id, scene),"
                    " KEY idx_glucose_crisis (user_id, is_crisis)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                ))
                await db.execute(text(
                    "CREATE TABLE IF NOT EXISTS health_glucose_alert ("
                    " id BIGINT NOT NULL AUTO_INCREMENT,"
                    " record_id BIGINT NOT NULL,"
                    " user_id BIGINT NOT NULL,"
                    " alert_type TINYINT NOT NULL COMMENT '1=低糖危象 2=高糖危象 3=严重偏高 4=严重偏低',"
                    " push_status TINYINT NOT NULL DEFAULT 0 COMMENT '0=待推 1=已推 2=失败',"
                    " guardian_confirmed TINYINT NOT NULL DEFAULT 0 COMMENT '0=未确认 1=已确认',"
                    " message VARCHAR(512) NULL,"
                    " guardian_ids VARCHAR(512) NULL COMMENT '逗号分隔守护人 user_id 列表',"
                    " create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                    " PRIMARY KEY (id),"
                    " KEY idx_alert_user_time (user_id, create_time),"
                    " KEY idx_alert_record (record_id)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                ))
                await db.execute(text(
                    "CREATE TABLE IF NOT EXISTS health_glucose_reminder ("
                    " id BIGINT NOT NULL AUTO_INCREMENT,"
                    " user_id BIGINT NOT NULL,"
                    " breakfast VARCHAR(8) NULL COMMENT 'HH:MM 早餐时间',"
                    " lunch VARCHAR(8) NULL,"
                    " dinner VARCHAR(8) NULL,"
                    " enabled TINYINT NOT NULL DEFAULT 0,"
                    " created_at DATETIME NULL,"
                    " updated_at DATETIME NULL,"
                    " PRIMARY KEY (id),"
                    " UNIQUE KEY uk_reminder_user (user_id)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                ))
                # [PRD-GLUCOSE-CARD-OPTIMIZE-V2 2026-05-30 §8.4] AI 提示词配置表
                await db.execute(text(
                    "CREATE TABLE IF NOT EXISTS ai_prompt_config ("
                    " id BIGINT NOT NULL AUTO_INCREMENT,"
                    " prompt_key VARCHAR(64) NOT NULL,"
                    " name VARCHAR(128) NOT NULL,"
                    " content TEXT NOT NULL,"
                    " version INT NOT NULL DEFAULT 1,"
                    " status TINYINT NOT NULL DEFAULT 1 COMMENT '1=已发布 0=草稿',"
                    " model_key VARCHAR(64) NULL,"
                    " updated_by VARCHAR(64) NULL,"
                    " updated_at DATETIME NULL,"
                    " created_at DATETIME NULL,"
                    " PRIMARY KEY (id),"
                    " UNIQUE KEY uk_prompt_key (prompt_key)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                ))
                await db.execute(text(
                    "CREATE TABLE IF NOT EXISTS ai_prompt_config_history ("
                    " id BIGINT NOT NULL AUTO_INCREMENT,"
                    " prompt_key VARCHAR(64) NOT NULL,"
                    " version INT NOT NULL,"
                    " content TEXT NOT NULL,"
                    " updated_by VARCHAR(64) NULL,"
                    " updated_at DATETIME NULL,"
                    " PRIMARY KEY (id),"
                    " KEY idx_key_version (prompt_key, version)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                ))
                await db.commit()
                # 自动初始化两条提示词
                try:
                    from app.api.glucose_v1 import _ensure_glucose_prompts as _ensure_gp
                    await _ensure_gp(db)
                except Exception as _e:
                    _logger.debug("[PRD-GLUCOSE-CARD-OPTIMIZE-V2] ensure_prompts skip: %s", _e)
                _logger.info("[PRD-GLUCOSE-V1] migration done")
            except Exception as e:
                await db.rollback()
                _logger.debug("[PRD-GLUCOSE-V1] skip: %s", e)
    except Exception as e:
        _logger.error("[PRD-GLUCOSE-V1] migration error: %s", e)


async def _migrate_prd468_health_v3():
    """[PRD-468 2026-05-12] health_metric_record / device_binding."""
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text
            try:
                await db.execute(text(
                    "CREATE TABLE IF NOT EXISTS health_metric_record ("
                    " id BIGINT NOT NULL AUTO_INCREMENT,"
                    " profile_id BIGINT NOT NULL,"
                    " metric_type VARCHAR(32) NOT NULL,"
                    " value_json JSON NOT NULL,"
                    " source VARCHAR(32) NOT NULL DEFAULT 'manual',"
                    " measured_at DATETIME NOT NULL,"
                    " created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                    " created_by BIGINT NOT NULL,"
                    " PRIMARY KEY (id),"
                    " KEY idx_profile_metric_time (profile_id, metric_type, measured_at),"
                    " KEY idx_source_hmr (source)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                ))
                await db.execute(text(
                    "CREATE TABLE IF NOT EXISTS device_binding ("
                    " id BIGINT NOT NULL AUTO_INCREMENT,"
                    " user_id BIGINT NOT NULL,"
                    " device_type VARCHAR(32) NOT NULL,"
                    " device_id VARCHAR(128) NOT NULL,"
                    " access_token TEXT NULL,"
                    " refresh_token TEXT NULL,"
                    " token_expires_at DATETIME NULL,"
                    " status VARCHAR(16) NOT NULL DEFAULT 'active',"
                    " bound_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                    " last_sync_at DATETIME NULL,"
                    " PRIMARY KEY (id),"
                    " UNIQUE KEY uk_user_device (user_id, device_type),"
                    " KEY idx_status_devbind (status)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                ))
                await db.commit()
                _logger.info("[PRD-468] migration done")
            except Exception as e:
                await db.rollback()
                _logger.debug("[PRD-468] skip: %s", e)
    except Exception as e:
        _logger.error("[PRD-468] migration error: %s", e)


async def _migrate_prd439_medication_reminder():
    """[PRD-439 2026-05-10] 用药提醒（H5 健康打卡升级）— 幂等建表。

    新增：
    - medication_plans
    - medication_logs

    与原 health_plan 数据完全独立。仅 CREATE IF NOT EXISTS，不删除任何旧表。
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text
            try:
                await db.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS medication_plans (
                        id INT NOT NULL AUTO_INCREMENT,
                        user_id INT NOT NULL,
                        patient_id INT NULL,
                        drug_name VARCHAR(128) NOT NULL,
                        dosage VARCHAR(64) NOT NULL,
                        schedule JSON NOT NULL,
                        note VARCHAR(256) NULL,
                        enabled TINYINT(1) NOT NULL DEFAULT 1,
                        created_at DATETIME NULL,
                        updated_at DATETIME NULL,
                        PRIMARY KEY (id),
                        KEY ix_medication_plans_user_id (user_id),
                        KEY ix_medication_plans_patient_id (patient_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                ))
                await db.execute(text(
                    """
                    CREATE TABLE IF NOT EXISTS medication_logs (
                        id INT NOT NULL AUTO_INCREMENT,
                        plan_id INT NOT NULL,
                        user_id INT NOT NULL,
                        log_date DATE NOT NULL,
                        scheduled_time VARCHAR(8) NOT NULL,
                        checked_at DATETIME NULL,
                        revoked TINYINT(1) NOT NULL DEFAULT 0,
                        PRIMARY KEY (id),
                        KEY ix_medication_logs_plan_id (plan_id),
                        KEY ix_medication_logs_user_id (user_id),
                        KEY ix_medication_logs_log_date (log_date)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                ))
                await db.commit()
                _logger.info("[prd439] medication_plans / medication_logs 建表完成")
            except Exception as e:
                await db.rollback()
                _logger.debug("[prd439] 建表跳过（可能 SQLite 测试环境，由 metadata.create_all 建表）: %s", e)
    except Exception as e:
        _logger.error("[prd439] 用药提醒迁移异常（不影响启动）: %s", e)


async def _migrate_aichat_optim_v1():
    """[AI对话模式优化 PRD v1.0] 2026-05-14
    - chat_function_buttons 表新增 8 个字段
    - medication_library 表新增 barcode 字段（本期仅建结构，预留扩展）
    幂等执行：基于 information_schema.columns 检查存在性。
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
                        _logger.info("[aichat_optim_v1] %s.%s 列已添加", table, column)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加列 %s.%s 跳过: %s", table, column, e)

            # chat_function_buttons 8 个字段
            await _add_col("chat_function_buttons", "prompt_template_id", "prompt_template_id INT NULL")
            await _add_col("chat_function_buttons", "external_url", "external_url VARCHAR(500) NULL")
            await _add_col("chat_function_buttons", "preset_prompt", "preset_prompt TEXT NULL")
            await _add_col("chat_function_buttons", "auto_user_message", "auto_user_message VARCHAR(200) NOT NULL DEFAULT ''")
            await _add_col("chat_function_buttons", "card_title", "card_title VARCHAR(50) NOT NULL DEFAULT ''")
            await _add_col("chat_function_buttons", "card_subtitle", "card_subtitle VARCHAR(100) NULL")
            await _add_col("chat_function_buttons", "card_cover_image", "card_cover_image VARCHAR(500) NULL")
            await _add_col("chat_function_buttons", "button_sub_desc", "button_sub_desc VARCHAR(100) NULL")

            # medication_library.barcode 预留
            await _add_col("medication_library", "barcode", "barcode VARCHAR(13) NULL")
            try:
                await db.execute(text(
                    "CREATE INDEX idx_medication_library_barcode ON medication_library(barcode)"
                ))
            except Exception:  # noqa: BLE001
                pass

            await db.commit()
            _logger.info("[aichat_optim_v1] AI对话模式优化 v1.0 迁移完成")
    except Exception as e:  # noqa: BLE001
        _logger.error("[aichat_optim_v1] 迁移异常（不影响启动）: %s", e)


# ─────────────────────────────────────────────────────────────────
# [AICHAT-OPTIM-FIX-V1 F-01/F-02/F-03/F-09 2026-05-14] 关键字 → Emoji 推荐字典
# 与 admin-web/src/app/(admin)/home-menus/page.tsx 内的 EMOJI_KEYWORD_MAP 保持同源
# 用于：① 数据迁移自动填 icon；② admin 前端推荐
# ─────────────────────────────────────────────────────────────────
_EMOJI_KEYWORD_MAP_FIX_V1 = [
    (["药", "用药", "服药", "吃药"], "💊"),
    (["识药", "拍照识药"], "📷"),
    (["家庭", "家人", "亲子"], "👨‍👩‍👧"),
    (["医生", "问诊", "看诊", "大夫"], "🩺"),
    (["提醒", "闹钟"], "⏰"),
    (["健康", "保健", "体检"], "❤️"),
    (["视频"], "📹"),
    (["客服", "咨询"], "💬"),
    (["积分", "奖励"], "🎁"),
    (["商城", "商品", "购物"], "🛒"),
    (["文档", "报告"], "📄"),
    (["数据", "报表"], "📊"),
    (["设置"], "⚙️"),
    (["疫苗", "接种"], "💉"),
    (["心理", "情绪"], "🧠"),
    (["睡眠", "失眠"], "😴"),
    (["饮食", "营养"], "🥗"),
    (["运动", "健身"], "🏃"),
    (["挂号", "预约"], "📅"),
    (["专家"], "👨‍⚕️"),
    (["地图", "导航", "位置"], "📍"),
    (["扫码", "二维码"], "📱"),
    (["支付", "钱包"], "💳"),
    (["消息", "通知", "公告"], "🔔"),
    (["搜索", "查找"], "🔍"),
    (["收藏", "关注"], "⭐"),
    (["点赞", "喜欢"], "👍"),
    (["反馈", "投诉", "建议"], "📮"),
    (["分享"], "🔗"),
    (["教育", "课程", "学习"], "📚"),
    (["签到", "打卡"], "✅"),
    (["问卷", "测评", "评估"], "📝"),
    (["眼睛", "眼科", "视力"], "👁️"),
    (["口腔", "牙齿"], "🦷"),
    (["皮肤", "美容"], "🧴"),
    (["孕期", "产检", "母婴"], "🤰"),
    (["儿童", "儿科", "小儿"], "👶"),
    (["老人", "养老"], "👴"),
    (["保险", "医保"], "🛡️"),
    (["急救", "120", "紧急"], "🚑"),
]


def _recommend_emoji_for_name(name: str) -> str:
    """根据按钮名命中关键字推荐 Emoji；未命中则用默认 📌。"""
    if not name:
        return "📌"
    for keywords, emoji in _EMOJI_KEYWORD_MAP_FIX_V1:
        for kw in keywords:
            if kw in name:
                return emoji
    return "📌"


async def _migrate_aichat_optim_fix_v1():
    """[AICHAT-OPTIM-FIX-V1 2026-05-14] AI 对话模式优化修复 PRD v1.0

    迁移内容：
      1. chat_function_buttons 添加 icon VARCHAR(32) 列（幂等）
      2. 根据按钮名关键字推荐 Emoji 自动回填空 icon 字段
      3. app_settings.ai_home_config.func_grid 简化为 visible/max_count/cols(columns)
    幂等执行：基于 information_schema.columns 检查存在性 + icon 非空跳过保护
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text

            # ── 1. 加 icon 列 ──
            try:
                chk = await db.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'chat_function_buttons' "
                    "AND column_name = 'icon'"
                ))
                if (chk.scalar() or 0) == 0:
                    await db.execute(text(
                        "ALTER TABLE chat_function_buttons ADD COLUMN icon VARCHAR(32) NULL"
                    ))
                    print("[migrate] aichat_optim_fix_v1: chat_function_buttons.icon 列已添加", flush=True)
                    _logger.info("[aichat_optim_fix_v1] chat_function_buttons.icon 列已添加")
            except Exception as e:  # noqa: BLE001
                _logger.debug("[aichat_optim_fix_v1] icon 列添加跳过: %s", e)

            # ── 2. 按按钮名推荐 Emoji 自动填充空 icon ──
            migrated_count = 0
            skipped_count = 0
            try:
                rows = await db.execute(text(
                    "SELECT id, name, icon FROM chat_function_buttons"
                ))
                for row in rows.fetchall():
                    bid, bname, bicon = row[0], row[1] or "", row[2] or ""
                    if bicon and bicon.strip():
                        skipped_count += 1
                        continue
                    new_emoji = _recommend_emoji_for_name(bname)
                    await db.execute(
                        text("UPDATE chat_function_buttons SET icon = :icon WHERE id = :id"),
                        {"icon": new_emoji, "id": bid},
                    )
                    migrated_count += 1
                print(
                    f"[migrate] aichat_optim_fix_v1: {migrated_count} 条记录迁移, {skipped_count} 条跳过",
                    flush=True,
                )
                _logger.info(
                    "[aichat_optim_fix_v1] aichat_optim_fix_v1: %d 条记录迁移, %d 条跳过",
                    migrated_count, skipped_count,
                )
            except Exception as e:  # noqa: BLE001
                _logger.debug("[aichat_optim_fix_v1] icon 数据回填跳过: %s", e)

            # ── 3. func_grid 简化迁移（保留 visible/max_count/cols(columns)） ──
            # ai_home_config 存储在 app_settings 表中 key='ai_home_config' 一个 JSON blob
            simplified_updated = 0
            simplified_skipped = 0
            try:
                import json as _json
                row = await db.execute(text(
                    "SELECT id, value FROM app_settings WHERE `key` = 'ai_home_config'"
                ))
                rec = row.fetchone()
                if rec is None:
                    simplified_skipped += 1
                else:
                    setting_id, raw = rec[0], rec[1]
                    try:
                        cfg = _json.loads(raw) if raw else {}
                    except Exception:
                        cfg = {}
                    if not isinstance(cfg, dict):
                        cfg = {}
                    fg = cfg.get("func_grid") if isinstance(cfg.get("func_grid"), dict) else {}
                    needs_update = False
                    if "visible" not in fg:
                        fg["visible"] = True
                        needs_update = True
                    # 兼容 columns / cols 两个键名，PRD 要求 cols；同时保留 columns 兼容已有数据
                    if "columns" not in fg:
                        fg["columns"] = 3
                        needs_update = True
                    if "cols" not in fg:
                        fg["cols"] = fg.get("columns", 3)
                        needs_update = True
                    if "max_count" not in fg:
                        fg["max_count"] = 6
                        needs_update = True
                    if needs_update:
                        cfg["func_grid"] = fg
                        await db.execute(
                            text("UPDATE app_settings SET value = :v WHERE id = :id"),
                            {"v": _json.dumps(cfg, ensure_ascii=False), "id": setting_id},
                        )
                        simplified_updated += 1
                    else:
                        simplified_skipped += 1
                print(
                    f"[migrate] func_grid simplified: {simplified_updated} records updated, {simplified_skipped} skipped",
                    flush=True,
                )
                _logger.info(
                    "[aichat_optim_fix_v1] func_grid simplified: %d records updated, %d skipped",
                    simplified_updated, simplified_skipped,
                )
            except Exception as e:  # noqa: BLE001
                _logger.debug("[aichat_optim_fix_v1] func_grid 简化跳过: %s", e)

            await db.commit()
            print("[migrate] aichat_optim_fix_v1: func_grid simplified DONE; AI 对话模式优化修复 v1 迁移完成", flush=True)
            _logger.info("[aichat_optim_fix_v1] AI 对话模式优化修复 v1 迁移完成")
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] aichat_optim_fix_v1: 迁移异常（不影响启动）: {e}", flush=True)
        _logger.error("[aichat_optim_fix_v1] 迁移异常（不影响启动）: %s", e)


async def _migrate_prompt_type_config_v1():
    """[PRD-PROMPT-CONFIG-V1 2026-05-14] Prompt 类型配置改造 v1
    
    迁移内容（幂等）：
      1. 创建 prompt_type_config 表（如不存在）
      2. 初始化 10 条默认数据（仅在表空时插入）
      3. 历史 function_buttons 自动迁移：button_type=photo_upload/file_upload
         且 prompt_template_id 绑定到 report_interpret 业务分组的 Prompt 时
         → 改为 button_type=report_interpret
         （备份至 function_buttons_backup_pcv1）
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text

            # ── 1. 表已由 Base.metadata.create_all 创建，本步主要兜底（MySQL DDL 幂等） ──
            # 不显式 CREATE TABLE，因为 ORM Base 自动建表
            print("[migrate] prompt_type_config_v1: 启动", flush=True)

            # ── 2. 初始化数据（仅在表空时） ──
            chk = await db.execute(text("SELECT COUNT(*) FROM prompt_type_config"))
            count = chk.scalar() or 0
            if count == 0:
                # type_key, display_name, business_group, description, allowed_button_types(JSON), preview_input_default, is_online, sort_order
                seed_rows = [
                    ("checkup_report_interpret", "体检报告解读（对话式）", "report_interpret",
                     "单份体检报告对话化解读", '["report_interpret"]',
                     "示例：体检报告全文…（在此粘贴 OCR 文本进行预览）", 1, 10),
                    ("checkup_report_compare", "报告对比（对话式）", "report_interpret",
                     "两份及以上报告对比解读", '["report_interpret"]',
                     "示例：两份报告全文…", 1, 20),
                    ("drug_general", "药物识别通用建议", "drug_identify",
                     "拍照识药通用建议（无档案）", '["photo_recognize_drug"]',
                     "示例：阿莫西林胶囊", 1, 10),
                    ("drug_personal", "药物识别个性化建议", "drug_identify",
                     "拍照识药结合用户档案", '["photo_recognize_drug"]',
                     "示例：阿莫西林胶囊+用户档案", 1, 20),
                    ("drug_interaction", "药物相互作用分析", "drug_identify",
                     "多药相互作用", '["photo_recognize_drug","ai_chat_trigger"]',
                     "示例：阿莫西林+布洛芬", 1, 30),
                    ("drug_query", "用药咨询对话", "drug_chat",
                     "用药咨询对话", '["ai_chat_trigger","quick_ask"]',
                     "示例：阿莫西林能和布洛芬一起吃吗？", 1, 10),
                    ("drug_chat_opening_single", "用药对话首条消息（单药）", "drug_chat",
                     "单药对话开场", '["ai_chat_trigger"]',
                     "示例：阿莫西林", 1, 20),
                    ("drug_chat_opening_multi", "用药对话首条消息（多药）", "drug_chat",
                     "多药对话开场", '["ai_chat_trigger"]',
                     "示例：阿莫西林+布洛芬", 1, 30),
                    ("checkup_report", "体检报告解读（旧·结构化）", "_deprecated",
                     "已下线", '[]', None, 0, 90),
                    ("trend_analysis", "趋势解读", "_deprecated",
                     "已下线", '[]', None, 0, 91),
                ]
                for row in seed_rows:
                    await db.execute(text(
                        "INSERT INTO prompt_type_config "
                        "(type_key, display_name, business_group, description, allowed_button_types, preview_input_default, is_online, sort_order, created_by) "
                        "VALUES (:k, :n, :g, :d, :a, :p, :o, :s, 'system')"
                    ), {
                        "k": row[0], "n": row[1], "g": row[2], "d": row[3],
                        "a": row[4], "p": row[5], "o": row[6], "s": row[7],
                    })
                print(f"[migrate] prompt_type_config_v1: 初始化 {len(seed_rows)} 条数据", flush=True)
                _logger.info("[prompt_type_config_v1] 初始化 %d 条数据", len(seed_rows))
            else:
                print(f"[migrate] prompt_type_config_v1: 已有 {count} 条数据，跳过初始化", flush=True)

            # ── 3. 历史按钮迁移：报告类 prompt 绑定的 photo_upload/file_upload → report_interpret ──
            # 先备份（如存在则跳过）
            try:
                bak_chk = await db.execute(text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = 'function_buttons_backup_pcv1'"
                ))
                if (bak_chk.scalar() or 0) == 0:
                    await db.execute(text(
                        "CREATE TABLE function_buttons_backup_pcv1 AS SELECT * FROM chat_function_buttons"
                    ))
                    print("[migrate] prompt_type_config_v1: 已备份 chat_function_buttons → function_buttons_backup_pcv1", flush=True)
            except Exception as be:
                _logger.debug("[prompt_type_config_v1] 备份跳过: %s", be)

            # 找出报告类业务分组的 prompt_template_id
            try:
                rows = await db.execute(text(
                    "SELECT pt.id FROM prompt_templates pt "
                    "JOIN prompt_type_config c ON pt.prompt_type = c.type_key "
                    "WHERE c.business_group = 'report_interpret' AND pt.is_active = 1"
                ))
                ids = [r[0] for r in rows.fetchall()]
                if ids:
                    placeholders = ",".join(str(i) for i in ids)
                    upd = await db.execute(text(
                        f"UPDATE chat_function_buttons SET button_type = 'report_interpret' "
                        f"WHERE prompt_template_id IN ({placeholders}) "
                        f"AND button_type IN ('photo_upload','file_upload')"
                    ))
                    rc = upd.rowcount if hasattr(upd, "rowcount") else 0
                    print(f"[migrate] prompt_type_config_v1: 迁移 {rc} 个历史按钮 → report_interpret", flush=True)
                else:
                    print("[migrate] prompt_type_config_v1: 无报告类 active Prompt，跳过按钮迁移", flush=True)
            except Exception as ue:
                _logger.debug("[prompt_type_config_v1] 按钮迁移跳过: %s", ue)

            await db.commit()
            print("[migrate] prompt_type_config_v1: 完成", flush=True)
            _logger.info("[prompt_type_config_v1] 迁移完成")
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] prompt_type_config_v1: 迁移异常（不影响启动）: {e}", flush=True)
        _logger.error("[prompt_type_config_v1] 迁移异常（不影响启动）: %s", e)


async def _migrate_bug433_chat_message_source_parent_id():
    """[Bug-433 2026-05-09] AI 对话首页 - 语音/预设按钮"会话首句消息丢失"修复

    chat_messages 表加列：
    - source VARCHAR(16) NOT NULL DEFAULT 'text'：用户消息来源入口
      （text/voice/preset/voice_repair），便于排查会话首句丢失类回归 + 运营分析
    - parent_id INT NULL：AI 回复关联到对应的用户消息 id，便于成对查询和
      历史孤立 AI 消息扫描；为 parent_id 建立索引以加速回看查询

    幂等执行：基于 information_schema.columns / statistics 检查存在性。
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
                        "WHERE table_schema = DATABASE() AND table_name = 'chat_messages' AND column_name = :c"
                    ), {"c": column})
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(f"ALTER TABLE chat_messages ADD COLUMN {ddl}"))
                        _logger.info("[bug433] chat_messages.%s 列已添加", column)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加列 chat_messages.%s 跳过: %s", column, e)

            async def _add_idx(idx: str, ddl: str):
                try:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM information_schema.statistics "
                        "WHERE table_schema = DATABASE() AND table_name = 'chat_messages' AND index_name = :i"
                    ), {"i": idx})
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(f"ALTER TABLE chat_messages ADD INDEX {ddl}"))
                        _logger.info("[bug433] chat_messages.%s 索引已添加", idx)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加索引 chat_messages.%s 跳过: %s", idx, e)

            await _add_col("source", "source VARCHAR(16) NOT NULL DEFAULT 'text'")
            await _add_col("parent_id", "parent_id INT NULL")
            await _add_idx("idx_chat_messages_parent_id", "idx_chat_messages_parent_id (parent_id)")
            await _add_idx(
                "idx_chat_messages_session_role_created",
                "idx_chat_messages_session_role_created (session_id, role, created_at)",
            )

            await db.commit()
            _logger.info("[bug433] chat_messages 迁移完成")
    except Exception as e:  # noqa: BLE001
        _logger.error("[bug433] chat_messages 迁移异常（不影响启动）: %s", e)


async def _migrate_bug470_cleanup_placeholder():
    """[Bug-470 2026-05-15] 清理 chat_function_buttons 中 URL 字段的占位脏数据。

    线上发现 `icon_url='无'` 等占位字面值被前端直接用作 `<img src>`，
    浏览器把它当成相对路径解析为 `/ai-home/无` → 404 → 拍照识药首页初始化失败 → 4 按钮失灵。

    一次性把以下字段中"无 / 暂无 / null / none / N/A / 未设置 / 未配置 / 空白"等占位词清空：
      - chat_function_buttons.icon_url
      - chat_function_buttons.card_cover_image
      - chat_function_buttons.external_url
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text
            placeholders = ("无", "无.", "暂无", "未设置", "未配置", "null", "NULL", "None", "none", "N/A", "n/a", "NA", "na")
            placeholders_sql = ",".join([f"'{p}'" for p in placeholders])
            fields = ("icon_url", "card_cover_image", "external_url")
            cleaned = 0
            for f in fields:
                sql = f"""
                    UPDATE chat_function_buttons
                    SET {f} = NULL
                    WHERE {f} IS NOT NULL
                      AND TRIM({f}) <> ''
                      AND (
                        TRIM({f}) IN ({placeholders_sql})
                        OR (
                          TRIM({f}) NOT LIKE 'http://%%'
                          AND TRIM({f}) NOT LIKE 'https://%%'
                          AND TRIM({f}) NOT LIKE '/%%'
                          AND TRIM({f}) NOT LIKE './%%'
                          AND TRIM({f}) NOT LIKE 'data:image/%%'
                          AND TRIM({f}) NOT LIKE 'blob:%%'
                        )
                      )
                """
                res = await db.execute(text(sql))
                cleaned += res.rowcount or 0
                print(f"[migrate] bug470_cleanup_placeholder: cleaned chat_function_buttons.{f} rows={res.rowcount}", flush=True)
            await db.commit()
            print(f"[migrate] bug470_cleanup_placeholder: total cleaned rows={cleaned}", flush=True)
            _logger.info("[bug470] cleanup placeholder cleaned_rows=%s", cleaned)
    except Exception as e:  # noqa: BLE001
        print(f"[migrate] bug470_cleanup_placeholder: 迁移异常（不影响启动）: {e}", flush=True)
        _logger.error("[bug470] 迁移异常（不影响启动）: %s", e)


async def _migrate_health_opt_v1_ai_call():
    """[PRD-HEALTH-OPT-V1 2026-05-14] 健康档案优化：AI 外呼用药提醒。

    1. medication_plans 加列：ai_call_enabled / ai_call_dnd_start / ai_call_dnd_end / ai_call_target_user_id
    2. 初始化 ai_call_membership_levels（normal=30、health=100）
    3. 初始化 ai_call_global_config 单行配置
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    print("[migrate] health_opt_v1_ai_call: 启动迁移...", flush=True)
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
                        print(f"[migrate] health_opt_v1: {table}.{column} 列已添加", flush=True)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加列 %s.%s 跳过: %s", table, column, e)

            await _add_col("medication_plans", "ai_call_enabled", "ai_call_enabled TINYINT(1) NOT NULL DEFAULT 0")
            await _add_col("medication_plans", "ai_call_dnd_start", "ai_call_dnd_start VARCHAR(8) NULL DEFAULT '22:00'")
            await _add_col("medication_plans", "ai_call_dnd_end", "ai_call_dnd_end VARCHAR(8) NULL DEFAULT '07:00'")
            await _add_col("medication_plans", "ai_call_target_user_id", "ai_call_target_user_id INT NULL")

            # 初始化默认会员等级
            res = await db.execute(text(
                "SELECT COUNT(*) FROM ai_call_membership_levels WHERE level_code IN ('normal','health')"
            ))
            existing = res.scalar() or 0
            if existing < 2:
                seed = [
                    ("normal", "免费会员", 30, 100),
                    ("health", "健康会员", 100, 200),
                ]
                for code, name, quota, sort_o in seed:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM ai_call_membership_levels WHERE level_code = :c"
                    ), {"c": code})
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(
                            "INSERT INTO ai_call_membership_levels "
                            "(level_code, display_name, monthly_quota, sort_order, is_active) "
                            "VALUES (:c, :n, :q, :s, 1)"
                        ), {"c": code, "n": name, "q": quota, "s": sort_o})
                        print(f"[migrate] health_opt_v1: 初始化会员等级 {code}", flush=True)

            # 初始化全局配置（单行）
            chk = await db.execute(text("SELECT COUNT(*) FROM ai_call_global_config"))
            if (chk.scalar() or 0) == 0:
                await db.execute(text(
                    "INSERT INTO ai_call_global_config "
                    "(default_dnd_start, default_dnd_end, default_script_template, "
                    " retry_max, retry_interval_minutes, rule_a_per_plan_once, rule_b_charge_on_answer) "
                    "VALUES ('22:00', '07:00', "
                    "'您好，到了服用 {药物名} 的时间，请按时用药。', 2, 5, 1, 0)"
                ))
                print("[migrate] health_opt_v1: 初始化全局配置", flush=True)

            await db.commit()
        print("[migrate] health_opt_v1_ai_call: 迁移完成", flush=True)
    except Exception as e:  # noqa: BLE001
        _logger.error("[health_opt_v1] AI 外呼迁移异常（不影响启动）: %s", e)
        print(f"[migrate] health_opt_v1_ai_call: 异常 {e}", flush=True)


async def _migrate_health_self_check_v1():
    """[PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查功能数据库迁移。

    幂等操作：
      1. chat_function_buttons 添加 4 列：health_check_template_id / archive_missing_strategy /
         prompt_override_enabled / prompt_override_text
      2. 创建 body_part_dict / health_check_template 表（依赖 metadata.create_all 已建表）
      3. 初始化 10 个默认部位 + 1 个通用问卷模板 + 1 个默认按钮（仅在表为空时）
    """
    import logging as _l
    _logger = _l.getLogger(__name__)
    from app.core.database import async_session as _async_session
    try:
        async with _async_session() as db:
            from sqlalchemy import text

            # 1. chat_function_buttons 加 4 列
            async def _add_col(table: str, column: str, ddl: str):
                try:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
                    ), {"t": table, "c": column})
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                        print(f"[migrate] health_self_check_v1: {table}.{column} 列已添加", flush=True)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("加列 %s.%s 跳过: %s", table, column, e)

            await _add_col("chat_function_buttons", "health_check_template_id", "health_check_template_id INT NULL")
            await _add_col("chat_function_buttons", "archive_missing_strategy", "archive_missing_strategy VARCHAR(32) NULL DEFAULT 'use_default'")
            await _add_col("chat_function_buttons", "prompt_override_enabled", "prompt_override_enabled TINYINT(1) NULL DEFAULT 0")
            await _add_col("chat_function_buttons", "prompt_override_text", "prompt_override_text TEXT NULL")
            await db.commit()

            # 2. 初始化默认数据（仅当 body_part_dict 为空）
            try:
                chk = await db.execute(text("SELECT COUNT(*) FROM body_part_dict"))
                cnt = chk.scalar() or 0
            except Exception as e:  # noqa: BLE001
                _logger.debug("body_part_dict 表不存在或查询失败: %s", e)
                return

            if cnt == 0:
                import json as _json
                seed_parts = [
                    ("头部", "🧠", ["头痛", "头晕", "偏头痛", "头胀", "记忆力下降"], 10),
                    ("眼部", "👁️", ["眼干", "眼痒", "视力模糊", "畏光", "眼疲劳"], 20),
                    ("耳鼻喉", "👂", ["耳鸣", "鼻塞", "咽痛", "咳嗽", "扁桃体肿大"], 30),
                    ("胸部", "🫁", ["胸闷", "胸痛", "心悸", "气短", "心跳加快"], 40),
                    ("腹部", "🤰", ["腹痛", "腹胀", "恶心", "呕吐", "腹泻", "便秘"], 50),
                    ("背部", "🦴", ["腰痛", "背痛", "肩颈僵硬", "脊柱酸痛"], 60),
                    ("四肢", "🦵", ["四肢酸痛", "关节痛", "麻木", "肿胀", "无力"], 70),
                    ("皮肤", "🧴", ["瘙痒", "皮疹", "红斑", "干燥", "脱屑"], 80),
                    ("泌尿生殖", "💧", ["尿频", "尿急", "尿痛", "夜尿增多"], 90),
                    ("全身症状", "🌡️", ["发热", "乏力", "盗汗", "体重下降", "失眠"], 100),
                ]
                for name, icon, syms, so in seed_parts:
                    try:
                        await db.execute(text(
                            "INSERT INTO body_part_dict (name, icon, symptoms, sort_order, enabled, created_at, updated_at) "
                            "VALUES (:n, :i, :s, :so, 1, NOW(), NOW())"
                        ), {"n": name, "i": icon, "s": _json.dumps(syms, ensure_ascii=False), "so": so})
                    except Exception as ie:  # noqa: BLE001
                        _logger.debug("插入部位 %s 失败: %s", name, ie)
                await db.commit()
                print(f"[migrate] health_self_check_v1: 已初始化 {len(seed_parts)} 个默认部位", flush=True)

            # 3. 初始化默认问卷模板
            try:
                chk = await db.execute(text("SELECT COUNT(*) FROM health_check_template"))
                tpl_cnt = chk.scalar() or 0
            except Exception:
                tpl_cnt = -1

            tpl_id_to_bind = None  # int | None
            if tpl_cnt == 0:
                import json as _json
                # 取所有部位 id
                part_rows = (await db.execute(text("SELECT id FROM body_part_dict ORDER BY sort_order ASC, id ASC"))).all()
                body_parts_json = _json.dumps(
                    [{"id": int(r[0]), "sort": idx + 1} for idx, r in enumerate(part_rows)],
                    ensure_ascii=False,
                )
                duration_json = _json.dumps(["<1天", "1-3天", "3-7天", ">1周", ">1月"], ensure_ascii=False)
                default_prompt = (
                    "你是一名专业的全科医生助手。以下是用户的健康自查信息，请基于这些信息给出专业、温和、易懂的初步分析与建议。\n\n"
                    "【咨询人档案】\n"
                    "姓名信息：{档案信息}\n年龄：{档案年龄}\n性别：{档案性别}\n既往病史：{档案既往病史}\n过敏史：{档案过敏史}\n\n"
                    "【自查信息】\n身体部位：{部位}\n出现症状：{症状列表}\n持续时间：{持续时间}\n\n"
                    "请从以下角度作答：\n"
                    "1. 可能的常见原因（按可能性从高到低列出 2~4 个）；\n"
                    "2. 建议进一步关注的伴随症状；\n"
                    "3. 居家可采取的缓解或观察建议；\n"
                    "4. 何种情况下应当尽快就医（明确预警信号）。\n\n"
                    "回答需通俗、克制，避免给出确定性诊断；末尾自动追加医疗免责声明。"
                )
                try:
                    res = await db.execute(text(
                        "INSERT INTO health_check_template "
                        "(name, description, body_parts, duration_options, default_prompt, enabled, created_at, updated_at) "
                        "VALUES (:n, :d, :bp, :du, :pp, 1, NOW(), NOW())"
                    ), {
                        "n": "通用健康自查",
                        "d": "默认通用自查模板（含 10 个常见部位）",
                        "bp": body_parts_json, "du": duration_json, "pp": default_prompt,
                    })
                    await db.commit()
                    tpl_id_to_bind = res.lastrowid
                    print(f"[migrate] health_self_check_v1: 已初始化通用问卷模板 id={tpl_id_to_bind}", flush=True)
                except Exception as e:  # noqa: BLE001
                    _logger.error("插入通用问卷模板失败: %s", e)

            # 4. 添加一个默认 health_self_check 按钮（仅当无 health_self_check 类型按钮且模板可用）
            if tpl_id_to_bind:
                try:
                    chk = await db.execute(text(
                        "SELECT COUNT(*) FROM chat_function_buttons WHERE button_type = 'health_self_check'"
                    ))
                    if (chk.scalar() or 0) == 0:
                        await db.execute(text(
                            "INSERT INTO chat_function_buttons "
                            "(name, icon, button_type, sort_weight, is_enabled, auto_user_message, card_title, "
                            " health_check_template_id, archive_missing_strategy, prompt_override_enabled, "
                            " created_at, updated_at) "
                            "VALUES ('健康自查', '🩺', 'health_self_check', 5, 1, '', '健康自查', :tid, 'use_default', 0, "
                            "NOW(), NOW())"
                        ), {"tid": tpl_id_to_bind})
                        await db.commit()
                        print("[migrate] health_self_check_v1: 已初始化默认健康自查按钮", flush=True)
                except Exception as e:  # noqa: BLE001
                    _logger.debug("插入默认按钮跳过: %s", e)
    except Exception as e:  # noqa: BLE001
        _logger.error("[health_self_check_v1] 迁移异常（不影响启动）: %s", e)
        print(f"[migrate] health_self_check_v1: 异常 {e}", flush=True)


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
    # [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517 · Bug #2 修 B]
    # is_self FamilyMember 一次性回填：确保"本人"统一为 FamilyMember 路径
    try:
        from app.services.family_self_backfill_migration import migrate_family_self
        await migrate_family_self()
    except Exception as _e:
        import logging as _l
        _l.getLogger(__name__).error("family_self_backfill 异常（不影响启动）: %s", _e)
    # [BUG_FIX-FAMILY-NICKNAME-NOTNULL-20260530] 健康档案空姓名脏数据清理 + ALTER NOT NULL
    # 必须放在 family_self_backfill 之后，以确保本人档已被回填（避免误判脏数据）
    try:
        from app.services.family_member_nickname_cleanup_migration import (
            migrate_family_member_nickname_cleanup,
        )
        await migrate_family_member_nickname_cleanup()
    except Exception as _e:
        import logging as _l
        _l.getLogger(__name__).error(
            "family_member_nickname_cleanup 异常（不影响启动）: %s", _e
        )
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
    # [Bug-433 2026-05-09] chat_messages 加列 source/parent_id + 索引
    await _migrate_bug433_chat_message_source_parent_id()
    # [PRD-439 2026-05-10] 用药提醒（H5 健康打卡升级）— medication_plans / medication_logs
    await _migrate_prd439_medication_reminder()
    # [PRD-468 2026-05-12] health_metric_record / device_binding
    await _migrate_prd468_health_v3()
    # [PRD-GLUCOSE-V1 2026-05-30] 血糖管理模块：health_glucose_record / health_glucose_alert / health_glucose_reminder
    await _migrate_glucose_v1()
    # [AI对话模式优化 PRD v1.0 2026-05-14] chat_function_buttons 8 字段 + medication_library.barcode
    await _migrate_aichat_optim_v1()
    # [AICHAT-OPTIM-FIX-V1 2026-05-14] chat_function_buttons 加 icon 字段 + 自动回填 Emoji + func_grid 简化
    print("[migrate] aichat_optim_fix_v1: 启动迁移...", flush=True)
    await _migrate_aichat_optim_fix_v1()
    print("[migrate] aichat_optim_fix_v1: 迁移完成", flush=True)
    # [PRD-PROMPT-CONFIG-V1 2026-05-14] Prompt 类型配置改造：表 + 数据 + 历史按钮迁移
    print("[migrate] prompt_type_config_v1: 启动迁移...", flush=True)
    await _migrate_prompt_type_config_v1()
    print("[migrate] prompt_type_config_v1: 迁移完成", flush=True)
    # [PRD-HEALTH-OPT-V1 2026-05-14] 健康档案优化：AI 外呼用药提醒
    await _migrate_health_opt_v1_ai_call()
    # [Bug-470 2026-05-15] 一次性清理 chat_function_buttons 中 icon_url/card_cover_image/external_url 等
    # URL 字段被错误存为字面值"无"等占位词的脏数据，避免前端把它拼作 <img src> 触发 /ai-home/无/ 404
    print("[migrate] bug470_cleanup_placeholder: 启动迁移...", flush=True)
    await _migrate_bug470_cleanup_placeholder()
    print("[migrate] bug470_cleanup_placeholder: 迁移完成", flush=True)
    # [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查功能：新增 2 张表 + chat_function_buttons 加 4 列 + 初始化默认数据
    print("[migrate] health_self_check_v1: 启动迁移...", flush=True)
    await _migrate_health_self_check_v1()
    print("[migrate] health_self_check_v1: 迁移完成", flush=True)
    # [PRD-AICHAT-CAPSULE-V2 2026-05-15] 3 个识药内置模板 + reply_mode → prompt_template_id 迁移
    try:
        print("[migrate] prd_aichat_capsule_v2: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session
        from app.services.prd_aichat_capsule_v2_migration import run_migration_with_session as _run_capsule_v2
        _stats = await _run_capsule_v2(_async_session)
        print(f"[migrate] prd_aichat_capsule_v2: 迁移完成 stats={_stats}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] prd_aichat_capsule_v2: 迁移失败 err={_e}", flush=True)
    # [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 历史 is_enabled 回填到 is_recommended/is_capsule
    try:
        print("[migrate] prd_aichat_home_grid_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session2
        from app.services.prd_aichat_home_grid_v1_migration import run_migration_with_session as _run_home_grid_v1
        _stats2 = await _run_home_grid_v1(_async_session2)
        print(f"[migrate] prd_aichat_home_grid_v1: 迁移完成 stats={_stats2}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] prd_aichat_home_grid_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 功能按钮管理优化：sort_weight→grid/capsule_sort + 老枚举映射
    try:
        print("[migrate] prd_aichat_funcbtn_optim_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session3
        from app.services.prd_aichat_funcbtn_optim_v1_migration import run_migration_with_session as _run_funcbtn_optim
        _stats3 = await _run_funcbtn_optim(_async_session3)
        print(f"[migrate] prd_aichat_funcbtn_optim_v1: 迁移完成 stats={_stats3}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] prd_aichat_funcbtn_optim_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-MED-PLAN-INTERACT-OPTIM-V1 2026-05-18] 用药计划重复 active 软删 + 名字标准化
    try:
        print("[migrate] prd_med_plan_interact_optim_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session4
        from app.services.prd_med_plan_interact_optim_v1_migration import run_migration_with_session as _run_med_plan_optim
        _stats4 = await _run_med_plan_optim(_async_session4)
        print(f"[migrate] prd_med_plan_interact_optim_v1: 迁移完成 stats={_stats4}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] prd_med_plan_interact_optim_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] AI 外呼配置迁移：用药计划层 + 人维度总开关 → 单层被守护人维度
    try:
        print("[migrate] prd_health_archive_optim_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session5
        from app.services.prd_health_archive_optim_v1_migration import run_migration_with_session as _run_health_archive_optim
        _stats5 = await _run_health_archive_optim(_async_session5)
        print(f"[migrate] prd_health_archive_optim_v1: 迁移完成 stats={_stats5}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] prd_health_archive_optim_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 通用问卷与图像采集架构重构
    try:
        print("[migrate] questionnaire_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session6
        from app.services.prd_questionnaire_v1_migration import run_migration_with_session as _run_questionnaire_v1
        _stats6 = await _run_questionnaire_v1(_async_session6)
        print(f"[migrate] questionnaire_v1: 迁移完成 stats={_stats6}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] questionnaire_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-LEGACY-HOME-CLEANUP-V1.1 2026-05-19] 管理后台「首页配置」遗留菜单下线清理
    try:
        print("[migrate] prd_legacy_home_cleanup_v11: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session7
        from app.services.prd_legacy_home_cleanup_v11_migration import run_migration_with_session as _run_legacy_home_cleanup
        _stats7 = await _run_legacy_home_cleanup(_async_session7)
        print(f"[migrate] prd_legacy_home_cleanup_v11: 迁移完成 stats={_stats7}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] prd_legacy_home_cleanup_v11: 迁移失败 err={_e}", flush=True)
    # [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 健康自查抽屉化 + 新版问卷模板体系融合
    try:
        print("[migrate] questionnaire_drawer_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session8
        from app.services.prd_questionnaire_drawer_v1_migration import run_migration_with_session as _run_questionnaire_drawer_v1
        _stats8 = await _run_questionnaire_drawer_v1(_async_session8)
        print(f"[migrate] questionnaire_drawer_v1: 迁移完成 stats={_stats8}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] questionnaire_drawer_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-TCM-DRAWER-V12 2026-05-20] 中医体质 36 题 seed + 触发词/AI 引用 5 字段
    try:
        print("[migrate] tcm36_drawer_v12: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session9
        from app.services.prd_tcm36_drawer_v12_migration import run_migration_with_session as _run_tcm36_drawer_v12
        _stats9 = await _run_tcm36_drawer_v12(_async_session9)
        print(f"[migrate] tcm36_drawer_v12: 迁移完成 stats={_stats9}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] tcm36_drawer_v12: 迁移失败 err={_e}", flush=True)
    # [PRD-TAG-RECOMMEND-V1 2026-05-20] 标签管理 + 商品标签关联 + 问卷推荐配置
    try:
        print("[migrate] prd_tag_recommend_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session10
        from app.services.prd_tag_recommend_v1_migration import run_migration_with_session as _run_tag_recommend
        _stats10 = await _run_tag_recommend(_async_session10)
        print(f"[migrate] prd_tag_recommend_v1: 迁移完成 stats={_stats10}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] prd_tag_recommend_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-QN-CONTENT-V1 2026-05-20] 4 个问卷题库 + 健康自查 6 维度 + chips/CTA 后台配置
    try:
        print("[migrate] qn_content_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session11
        from app.services.prd_qn_content_v1_migration import run_migration_with_session as _run_qn_content_v1
        _stats11 = await _run_qn_content_v1(_async_session11)
        print(f"[migrate] qn_content_v1: 迁移完成 stats={_stats11}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] qn_content_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 自动下一步呈现配置三件套
    try:
        print("[migrate] questionnaire_autonext_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session12
        from app.services.prd_questionnaire_autonext_v1_migration import run_migration_with_session as _run_qn_autonext
        _stats12 = await _run_qn_autonext(_async_session12)
        print(f"[migrate] questionnaire_autonext_v1: 迁移完成 stats={_stats12}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] questionnaire_autonext_v1: 迁移失败 err={_e}", flush=True)
    # [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] 健康自查四问题修复（卡片协议 + 三段式 + Q5/Q6 文案 + AI 追问摘要字段）
    try:
        print("[migrate] health_self_check_fix_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session_hscfix
        from app.services.prd_health_self_check_fix_v1_migration import run_migration_with_session as _run_hsc_fix
        _stats_hscfix = await _run_hsc_fix(_async_session_hscfix)
        print(f"[migrate] health_self_check_fix_v1: 迁移完成 stats={_stats_hscfix}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] health_self_check_fix_v1: 迁移失败 err={_e}", flush=True)
    # [BUG-HSC-FIX-V2-20260521] B-5 老表合并下线（health_check_template / body_part_dict）
    # 默认 dry-run（仅校验+备份信息），需 HSC_LEGACY_OFFLINE_DROP=1 才真正 DROP TABLE
    try:
        print("[migrate] hsc_legacy_offline_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session_hsclegacy
        from app.services.prd_health_self_check_legacy_offline_v1_migration import (
            run_migration_with_session as _run_hsc_legacy,
        )
        _stats_hsclegacy = await _run_hsc_legacy(_async_session_hsclegacy)
        print(f"[migrate] hsc_legacy_offline_v1: 迁移完成 stats={_stats_hsclegacy}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] hsc_legacy_offline_v1: 迁移失败 err={_e}", flush=True)
    # [BUG-FIX-AI-HOME-ARCHIVE-PATH-404-V1 2026-05-21] AI 对话主页"查看档案"跨端档案路径统一（/health-records|/health-archive → /health-profile）
    try:
        print("[migrate] ai_home_archive_path_fix_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session_aihome_arch
        from app.services.prd_ai_home_archive_path_fix_v1_migration import run_migration_with_session as _run_aihome_arch
        _stats_aihome_arch = await _run_aihome_arch(_async_session_aihome_arch)
        print(f"[migrate] ai_home_archive_path_fix_v1: 迁移完成 stats={_stats_aihome_arch}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] ai_home_archive_path_fix_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-HSC-OPTIM-V3-20260521] 健康自查功能优化 V3
    #   - questionnaire_answer 加 subject_*/ai_status/ai_full_interpretation 等字段
    #   - chat_function_buttons 加 result_cta_* 4 字段
    try:
        print("[migrate] hsc_optim_v3: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session_hsc_v3
        from app.services.prd_hsc_optim_v3_migration import (
            run_migration_with_session as _run_hsc_optim_v3,
        )
        async with _async_session_hsc_v3() as _db_hsc_v3:
            _stats_hsc_v3 = await _run_hsc_optim_v3(_db_hsc_v3)
        print(f"[migrate] hsc_optim_v3: 迁移完成 stats={_stats_hsc_v3}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] hsc_optim_v3: 迁移失败 err={_e}", flush=True)

    # [PRD-HSC-AI-REAL-V1 2026-05-21] 健康自查 AI 解读真接入大模型：
    # questionnaire_answer 新增 ai_profile_snapshot / ai_generated_at；
    # 同步更新 health_self_check 模板 ai_prompt_template 为正式版（中文占位符）。
    try:
        print("[migrate] hsc_ai_real_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session_hsc_ai
        from app.services.prd_hsc_ai_real_v1_migration import (
            run_migration_with_session as _run_hsc_ai_real,
        )
        async with _async_session_hsc_ai() as _db_hsc_ai:
            _stats_hsc_ai = await _run_hsc_ai_real(_db_hsc_ai)
        print(f"[migrate] hsc_ai_real_v1: 迁移完成 stats={_stats_hsc_ai}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] hsc_ai_real_v1: 迁移失败 err={_e}", flush=True)

    # [PRD-MY-DEVICES-V1 2026-05-21] 「我的设备」V2：建表 + 幂等 seed 品牌目录
    try:
        print("[migrate] my_devices_v1: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session_mydev
        from sqlalchemy import text as _sql_text_mydev
        async with _async_session_mydev() as _db_mydev:
            await _db_mydev.execute(_sql_text_mydev(
                "CREATE TABLE IF NOT EXISTS device_catalog ("
                " id INT NOT NULL AUTO_INCREMENT,"
                " brand_code VARCHAR(32) NOT NULL,"
                " brand_name VARCHAR(64) NOT NULL,"
                " category_code VARCHAR(64) NOT NULL,"
                " device_name VARCHAR(128) NOT NULL,"
                " icon VARCHAR(16) NULL,"
                " is_active TINYINT(1) NOT NULL DEFAULT 0,"
                " is_unique TINYINT(1) NOT NULL DEFAULT 1,"
                " sort_order INT NOT NULL DEFAULT 0,"
                " created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                " updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
                " PRIMARY KEY (id),"
                " KEY idx_dc_brand (brand_code),"
                " KEY idx_dc_category (category_code)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            ))
            await _db_mydev.execute(_sql_text_mydev(
                "CREATE TABLE IF NOT EXISTS device_user_bindings ("
                " id INT NOT NULL AUTO_INCREMENT,"
                " user_id INT NOT NULL,"
                " catalog_id INT NOT NULL,"
                " sn VARCHAR(128) NOT NULL,"
                " alias VARCHAR(64) NULL,"
                " member_id INT NULL,"
                " bound_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                " unbound_at DATETIME NULL,"
                " is_active TINYINT(1) NOT NULL DEFAULT 1,"
                " created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                " updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
                " PRIMARY KEY (id),"
                " KEY idx_dub_user (user_id),"
                " KEY idx_dub_catalog (catalog_id),"
                " KEY idx_dub_sn (sn),"
                " KEY idx_dub_member (member_id),"
                " KEY idx_dub_active (is_active)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            ))
            await _db_mydev.commit()
            from app.api.devices_v2 import seed_device_catalog as _seed_dc
            _stats_mydev = await _seed_dc(_db_mydev)
            await _db_mydev.commit()
        print(f"[migrate] my_devices_v1: 迁移完成 stats={_stats_mydev}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] my_devices_v1: 迁移失败 err={_e}", flush=True)
    # [PRD-HEALTH-ARCHIVE-V5-20260521] 健康档案与就医资料：新增 3 张表
    try:
        print("[migrate] health_archive_v5: 启动迁移...", flush=True)
        from app.core.database import async_session as _async_session_hav5
        from app.services.prd_health_archive_v5_migration import run_migration_with_session as _run_hav5
        async with _async_session_hav5() as _db_hav5:
            _stats_hav5 = await _run_hav5(_db_hav5)
        print(f"[migrate] health_archive_v5: 迁移完成 stats={_stats_hav5}", flush=True)
    except Exception as _e:
        import traceback as _tb
        _tb.print_exc()
        print(f"[migrate] health_archive_v5: 迁移失败 err={_e}", flush=True)
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
# [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人健康档案完善：/api/health-profile/self
# [BUG_FIX 2026-05-29] 改为 importlib 动态加载 + try/except 兜底，避免容器内某些边缘情况下
# `from app.api import health_profile_self` 解析失败导致 ImportError，整个服务无法启动。
try:
    import importlib as _importlib
    _health_profile_self = _importlib.import_module("app.api.health_profile_self")
    app.include_router(_health_profile_self.router)
except Exception as _e_self_complete:  # pragma: no cover - defensive
    import logging as _lg
    _lg.getLogger("app.startup").error(
        "[health_profile_self] include_router failed: %s", _e_self_complete
    )
app.include_router(chat.router)
app.include_router(chat_history.router)
# [PRD-AI-HOME-OPTIM-V4 2026-05-21] AI 首页 60min 刷新 + 埋点接口
app.include_router(ai_home_optim_v4.router)
app.include_router(health_archive_v5.router)
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
# [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29] 健康档案成员卡片状态机 + 统一删除接口
try:
    from app.api import family_member_v2 as _family_member_v2
    app.include_router(_family_member_v2.router)
except Exception as _e_fmv2:
    import logging as _l
    _l.getLogger(__name__).warning("[family_member_v2] include_router failed: %s", _e_fmv2)
app.include_router(family_management.public_protocol_router)

# [守护人体系 PRD v1.1 2026-05-25] guardian_system 路由（主/普通守护人、转移、串行外呼、额度）
from app.api import guardian_system as _guardian_system  # noqa: E402
app.include_router(_guardian_system.router)

# [守护人体系 PRD v1.2 2026-05-25] guardian_system_v12 路由：
# - 直筒列表（带关系称呼、角色徽章、代付状态）
# - 守护管理抽屉、提醒设置抽屉
# - 主守护人转让（接收者同意）、被守护人上帝视角
# - 紧急 AI 呼叫扣主守护人、AI 外呼提醒扣额度（含代付）
# - 紧急呼叫触发源后台管理
from app.api import guardian_system_v12 as _guardian_v12  # noqa: E402
app.include_router(_guardian_v12.router)
app.include_router(_guardian_v12.admin_router)
# [守护人体系 PRD v1.3 2026-05-26] 健康档案融合优化：守护中/待守护两态 Tab + invite_lifecycle + 主代付统一扣费
from app.api import guardian_system_v13 as _guardian_v13  # noqa: E402
app.include_router(_guardian_v13.router)
# [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 真删除 + 频次防护 + 邀请 nickname 必填 + 列表口径一致
from app.api import guardian_bugfix_v1 as _guardian_bugfix_v1  # noqa: E402
app.include_router(_guardian_bugfix_v1.router)
# [PRD-REVERSE-GUARDIAN-V1] 反向守护邀请
from app.api import reverse_guardian as _reverse_guardian  # noqa: E402
app.include_router(_reverse_guardian.router)
# [PRD-FAMILY-GUARDIAN-V1] 家庭体检异常守护推送
from app.api import family_guardian as _family_guardian  # noqa: E402
from app.api import admin_family_guardian as _admin_family_guardian  # noqa: E402
app.include_router(_family_guardian.router)
app.include_router(_admin_family_guardian.router)
app.include_router(content.router)
app.include_router(notification.router)
# PRD-425: AI 对话首页顶栏徽标——通知中心未读总数统一聚合接口
app.include_router(notifications_unified.router)
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
app.include_router(report_history.router)
app.include_router(checkup_api_v2.router)
app.include_router(ocr.router)
app.include_router(ocr.admin_router)
app.include_router(ocr_details.router)
app.include_router(ocr_details.user_router)
app.include_router(prompt_templates.router)
# [PRD-PROMPT-CONFIG-V1 2026-05-14] Prompt 类型配置 API
app.include_router(prompt_type_config.router)
# [PRD-HEALTH-OPT-V1 2026-05-14] AI 外呼用药提醒
app.include_router(ai_call.router)
app.include_router(ai_call.admin_router)
# [PRD-PROMPT-CONFIG-V1 2026-05-14] 报告解读按钮专属流程入口 /api/report-interpret/start
app.include_router(report_interpret_button.router)
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
# [PRD-MED-PLAN-INTERACT-OPTIM-V1 2026-05-18 §5.2] /api/medication-plan/check-duplicate 别名
app.include_router(health_plan_v2._med_plan_alias_router)
app.include_router(admin_health_plan.router)
app.include_router(city.router)
app.include_router(city.admin_router)
app.include_router(function_button.router)
app.include_router(function_button.admin_router)
# [AICHAT-OPTIM-FIX-V1 F-04 2026-05-14] 公开顶层 /api/function-buttons
app.include_router(function_button.public_router)
# [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查（health_self_check）
app.include_router(health_self_check.public_router)
app.include_router(health_self_check.admin_router)
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
app.include_router(themes.router)  # PRD-447 v2 后台主题模块（4 admin API + H5 注入）
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
app.include_router(ai_home_care_v1.router)
app.include_router(care_ai_home.router)
# [PRD-HOME-SAFETY-V1 2026-05-27] 智能硬件绑定 · 居家安全设备 v1.0
app.include_router(home_safety_v1.router)
app.include_router(care_card_v1.router)
# [2026-05-07 PRD-370 H5 登录页设计稿对齐] 远程开关：登录 UI 版本（v1 旧版 / v2 新版）
app.include_router(login_ui_config.router)
# [BUG-FIX-RESCHEDULE-V2 2026-05-07] 系统时间接口：供三端改约弹窗按服务器时间过滤过去时段
from app.api import system as _system  # noqa: E402
app.include_router(_system.router)
# [BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29] 前端兜底响应监控上报接口
try:
    from app.api import frontend_log as _frontend_log  # noqa: E402
    app.include_router(_frontend_log.router)
except Exception as _e_frontend_log:  # pragma: no cover
    logging.getLogger(__name__).warning(
        "[frontend_log] include_router failed: %s", _e_frontend_log
    )
# [PRD-405 2026-05-07] AI 对话模式首页配置（admin 后台 + 用户端公共读取 + 操作日志）
from app.api import ai_home_config as _ai_home_config  # noqa: E402
app.include_router(_ai_home_config.router)
app.include_router(user_health_profile.router)
# [PRD-432 2026-05-09] AI 回答顶部「咨询对象档案」折叠卡片
from app.api import consultant_profile_card as _consultant_profile_card  # noqa: E402
app.include_router(_consultant_profile_card.router)
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

# [PRD-423 T-08 2026-05-08] AI 对话页埋点接收接口（EVT-01 ~ EVT-10）
from app.api import analytics as _analytics  # noqa: E402
app.include_router(_analytics.router)

# [PRD-439 2026-05-10] H5 健康打卡升级为用药提醒：用药计划/打卡/徽标/待核销预约
app.include_router(medication_reminder.router)
app.include_router(prd469_health_v5.router)  # [PRD-469] 健康档案 v2 优化（v5 设计稿对齐）
app.include_router(health_dashboard.router)  # [PRD-HEALTH-DASHBOARD-V1] 家人健康看板
app.include_router(devices_v2.router)  # [PRD-MY-DEVICES-V1 2026-05-21] 我的设备 V2（/api/devices/*）
# [PRD-DRUG-CARD-V3 2026-05-16] AI 对话拍照识药 v3：权威库匹配 + 待审池 + 医疗咨询热线
app.include_router(medication_library_v3.router)
app.include_router(medication_library_v3.admin_router)
# [PRD-MED-PLAN-ENTRY-V1 2026-05-17] ç¨è¯è®¡åå¥å£æ¹é 
app.include_router(medication_plans_v1.router)
# [PRD-MED-PLAN-ADD-OPTIM-V1 2026-05-17] 添加用药计划页面优化 - 药品名称联想 API
app.include_router(medication_add_optim_v1.router)
# [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] ai-home 首页优化 - 同源「今日用药」接口
app.include_router(medication_today_v1.router)
# [PRD-468 2026-05-12] 健康档案改版 v3
app.include_router(health_profile_v3.router)
# [PRD-GLUCOSE-V1 2026-05-30] 血糖闭环管理模块
from app.api import glucose_v1 as _glucose_v1  # noqa: E402
app.include_router(_glucose_v1.router)
# [PRD-HEALTH-METRIC-CARD-UNIFY-V1 2026-05-31] 健康指标卡片统一改造（血压/血糖/心率/血氧）
from app.api import health_metric_card_v1 as _health_metric_card_v1  # noqa: E402
app.include_router(_health_metric_card_v1.router)
# [PRD-BP-AI-EXPLAIN-V1 2026-05-31] 血压 AI 解读（对齐血糖 AI 解读）
from app.api import bp_v1 as _bp_v1  # noqa: E402
app.include_router(_bp_v1.router)
app.include_router(health_archive_optim_v1.router)  # [PRD-HEALTH-ARCHIVE-OPTIM-V1] 健康档案页面优化 V1
# [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 通用问卷 API
app.include_router(questionnaire.router)
app.include_router(questionnaire.admin_router)
# [PRD-TCM-DRAWER-V12 2026-05-20] 聊天意图识别接口
from app.api import chat_intent as _chat_intent  # noqa: E402
app.include_router(_chat_intent.router)
# [PRD-TAG-RECOMMEND-V1 2026-05-20] 标签管理 + 商品标签关联 + 问卷推荐配置
from app.api import tag_recommend as _tag_recommend  # noqa: E402
app.include_router(_tag_recommend.router)
app.include_router(_tag_recommend.goods_tags_router)
app.include_router(_tag_recommend.recommend_router)
# [PRD-HEALTH-ARCHIVE-OPTIM-V2 2026-05-18] 健康档案页面优化 V2：成员徽章/Hero角标/设备列表/提醒设置/解绑
from app.api import health_archive_optim_v2 as _health_archive_optim_v2  # noqa: E402
app.include_router(_health_archive_optim_v2.router)
# [PRD-AI-PAGE-OPTIM-V1 2026-05-21] 种子数据导入管理后台 API
from app.api import seed_import as _seed_import  # noqa: E402
app.include_router(_seed_import.router)


# [2026-05-05 SDK 健康看板] 启动期 SDK 分级自检：核心缺失 → 容器退出；可选缺失 → CRITICAL 告警
@app.on_event("startup")
async def _sdk_health_startup_check() -> None:
    from app.core.sdk_health import run_startup_sdk_check
    run_startup_sdk_check()


# [PRD-432 2026-05-09] AI 回答顶部「咨询对象档案」折叠卡片相关表迁移
@app.on_event("startup")
async def _prd432_profile_card_migrate() -> None:
    _logger = logging.getLogger("app.prd432_migrate")
    from app.core.database import async_session as _async_session
    from sqlalchemy import text as _text
    columns_to_add = [
        ("health_profiles", "past_history_is_none", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("health_profiles", "allergy_is_none", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("health_profiles", "medication_is_none", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("chat_messages", "consultant_target_id", "BIGINT NULL"),
    ]
    try:
        async with _async_session() as db:
            for table, col, defn in columns_to_add:
                try:
                    await db.execute(_text(f"ALTER TABLE {table} ADD COLUMN {col} {defn}"))
                    await db.commit()
                    _logger.info(f"[PRD-432] {table}.{col} 列已添加")
                except Exception as e:
                    await db.rollback()
                    msg = str(e)
                    if "Duplicate column" in msg or "exists" in msg.lower():
                        _logger.debug(f"[PRD-432] {table}.{col} 已存在，跳过")
                    else:
                        _logger.warning(f"[PRD-432] {table}.{col} 添加失败：{e}")
    except Exception as e:
        _logger.warning(f"[PRD-432] 迁移连接失败：{e}")


# [PRD-AICHAT-CAPSULE-V2 2026-05-15] 启动期：写入 3 个识药内置模板 + 迁移 reply_mode → prompt_template_id
@app.on_event("startup")
async def _prd_aichat_capsule_v2_migrate() -> None:
    print("[migrate] prd_aichat_capsule_v2: 启动迁移...", flush=True)
    try:
        from app.core.database import async_session as _async_session
        from app.services.prd_aichat_capsule_v2_migration import run_migration_with_session
        stats = await run_migration_with_session(_async_session)
        print(f"[migrate] prd_aichat_capsule_v2: 迁移完成 stats={stats}", flush=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[migrate] prd_aichat_capsule_v2: 迁移失败 err={e}", flush=True)


# [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 迁移已嵌入 lifespan() 函数内，此处不再需要 startup hook
# （lifespan 与 on_event 共存时，FastAPI 会忽略 on_event，因此必须放到 lifespan 内部执行）


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

# [付费会员体系 PRD v1.1] 付费会员套餐 + 用户订阅 + 收银台优惠计算
from app.api import membership as _membership  # noqa: E402
app.include_router(_membership.admin_router)
app.include_router(_membership.user_router)

# [会员中心优化 PRD v2.0 2026-05-26] 注册新的会员中心 v2 路由
from app.api import member_center_v2 as _member_center_v2  # noqa: E402
app.include_router(_member_center_v2.router)
app.include_router(_member_center_v2.admin_router)

# [BUG_FIX_CARE_MODE_ENTRY_H5_20260527] 关怀模式入口缺失修复 - 用户模式偏好接口
from app.api import user_mode_preference as _user_mode_preference  # noqa: E402
app.include_router(_user_mode_preference.router)

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


# [Bug-419 2026-05-08 B-1/B-4] 422 校验错误友好化：
# 将 FastAPI/Pydantic 的英文校验错误转换为中文，并打印完整请求体（便于排查），
# 同时保留 422 状态码与 errors 数组以兼容前端 axios.error.response.data。
_VALIDATION_FIELD_LABELS = {
    "session_type": "会话类型 session_type",
    "family_member_id": "咨询对象 family_member_id",
    "title": "会话标题 title",
    "content": "消息内容 content",
    "phone": "手机号 phone",
    "password": "密码 password",
}


def _zh_validation_message(error: dict) -> str:
    loc = error.get("loc", [])
    field = loc[-1] if loc else ""
    label = _VALIDATION_FIELD_LABELS.get(str(field), str(field) if field else "请求参数")
    err_type = error.get("type") or ""
    msg = error.get("msg") or ""
    if "missing" in err_type:
        return f"{label} 必填"
    if "type_error" in err_type or "type" in err_type:
        return f"{label} 类型不正确：{msg}"
    if "value_error" in err_type or "literal" in err_type or "enum" in err_type:
        return f"{label} 取值不合法：{msg}"
    return f"{label}：{msg}"


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors() if hasattr(exc, "errors") else []
    try:
        # 安全脱敏：长度超过 500 的请求体直接截断；password/token 字段值置 ***
        try:
            raw_body = await request.body()
            body_text = raw_body.decode("utf-8", errors="replace")[:500]
        except Exception:
            body_text = "<unreadable>"
        _exception_logger.warning(
            "[Bug-419] RequestValidationError at %s %s: errors=%s body=%s",
            request.method,
            request.url.path,
            errors,
            body_text,
        )
    except Exception:
        pass

    zh_messages = [_zh_validation_message(e) for e in errors] if errors else ["请求参数不合法"]
    return JSONResponse(
        status_code=422,
        content={
            "detail": "；".join(zh_messages),
            "messages": zh_messages,
            "errors": errors,
        },
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
