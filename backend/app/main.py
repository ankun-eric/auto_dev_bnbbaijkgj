import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    addresses,
    admin,
    admin_health_plan,
    admin_merchant,
    admin_messages,
    admin_search,
    ai_center,
    auth,
    bottom_nav,
    chat,
    chat_history,
    chat_share,
    city,
    content,
    cos,
    coupons,
    customer_service,
    drug,
    drug_identify_share,
    email_notify,
    expert,
    family,
    family_management,
    favorites,
    font_setting,
    function_button,
    health_plan_v2,
    health_profile,
    home_config,
    knowledge,
    member_qr,
    messages,
    notice,
    notification,
    ocr,
    ocr_details,
    order,
    plan,
    points,
    merchant,
    product_admin,
    products,
    prompt_templates,
    referral,
    report,
    scan,
    search,
    service,
    sms,
    tcm,
    tts,
    unified_orders,
    upload,
    wechat_push,
)
from app.core.database import Base, engine
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

            await db.commit()
    except Exception as e:
        _logger.error(f"积分枚举/配置迁移异常（不影响启动）: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await sync_register_schema(conn)
    await _migrate_points_enums_and_config()
    await migrate_existing_users_user_no()
    from app.init_data import init_default_data
    await init_default_data()
    from app.init_cities import init_cities
    from app.core.database import async_session
    async with async_session() as db:
        await init_cities(db)
        await db.commit()
    from app.services.notification_scheduler import init_scheduler, shutdown_scheduler
    init_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="宾尼小康 AI健康管家", version="1.0.0", lifespan=lifespan)

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
app.include_router(service.router)
app.include_router(order.router)
app.include_router(expert.router)
app.include_router(points.router)
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
app.include_router(merchant.router)
app.include_router(sms.router)
app.include_router(email_notify.router)
app.include_router(wechat_push.router)
app.include_router(knowledge.router)
app.include_router(cos.router)
app.include_router(ai_center.router)
app.include_router(report.router)
app.include_router(report.admin_router)
app.include_router(ocr.router)
app.include_router(ocr.admin_router)
app.include_router(ocr_details.router)
app.include_router(ocr_details.user_router)
app.include_router(prompt_templates.router)
app.include_router(drug_identify_share.router)
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
app.include_router(unified_orders.router)
app.include_router(member_qr.router)
app.include_router(favorites.router)
app.include_router(coupons.router)
app.include_router(addresses.router)
app.include_router(product_admin.router)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "bini-health-api"}
