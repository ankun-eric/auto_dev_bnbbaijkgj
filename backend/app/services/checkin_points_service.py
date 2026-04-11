"""打卡积分发放服务"""
from datetime import date, datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import SystemConfig, PointsRecord, PointsType, User
import logging

logger = logging.getLogger(__name__)


async def get_checkin_points_config(db: AsyncSession) -> dict:
    """获取打卡积分配置"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_([
            "checkin_points_enabled",
            "checkin_points_per_action",
            "checkin_points_daily_limit",
        ]))
    )
    configs = {c.config_key: c.config_value for c in result.scalars().all()}
    return {
        "enabled": configs.get("checkin_points_enabled", "false").lower() == "true",
        "per_action": int(configs.get("checkin_points_per_action", "2")),
        "daily_limit": int(configs.get("checkin_points_daily_limit", "50")),
    }


async def get_today_checkin_points(db: AsyncSession, user_id: int) -> int:
    """获取用户今日已通过打卡获得的积分总数"""
    today = date.today()
    result = await db.execute(
        select(func.coalesce(func.sum(PointsRecord.points), 0)).where(
            PointsRecord.user_id == user_id,
            PointsRecord.type == PointsType.checkin,
            func.date(PointsRecord.created_at) == today,
        )
    )
    return result.scalar() or 0


async def award_checkin_points(db: AsyncSession, user: User, checkin_type: str) -> dict:
    """
    打卡时发放积分

    Args:
        db: 数据库会话
        user: 用户对象
        checkin_type: 打卡类型描述 ("健康习惯打卡" / "用药提醒打卡" / "健康计划任务打卡")

    Returns:
        dict: {"points_earned": int, "points_limit_reached": bool}
    """
    config = await get_checkin_points_config(db)

    if not config["enabled"]:
        return {"points_earned": 0, "points_limit_reached": False}

    earned_today = await get_today_checkin_points(db, user.id)
    remaining = config["daily_limit"] - earned_today

    if remaining <= 0:
        return {"points_earned": 0, "points_limit_reached": True}

    actual_points = min(config["per_action"], remaining)

    user.points = (user.points or 0) + actual_points

    pr = PointsRecord(
        user_id=user.id,
        points=actual_points,
        type=PointsType.checkin,
        description=checkin_type,
    )
    db.add(pr)

    new_total = earned_today + actual_points
    limit_reached = new_total >= config["daily_limit"]

    logger.info(f"用户 {user.id} 打卡积分: +{actual_points}, 今日累计: {new_total}/{config['daily_limit']}")

    return {"points_earned": actual_points, "points_limit_reached": limit_reached}


async def get_today_progress(db: AsyncSession, user_id: int) -> dict:
    """获取用户今日打卡积分进度"""
    config = await get_checkin_points_config(db)
    earned_today = await get_today_checkin_points(db, user_id)

    return {
        "earned_today": earned_today,
        "daily_limit": config["daily_limit"],
        "is_limit_reached": earned_today >= config["daily_limit"],
        "enabled": config["enabled"],
    }
