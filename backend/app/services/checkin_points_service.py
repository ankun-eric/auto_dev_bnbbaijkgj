"""打卡积分发放服务"""
from datetime import date, datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import SystemConfig, PointsRecord, PointsType, User
import logging

logger = logging.getLogger(__name__)


async def get_checkin_points_config(db: AsyncSession) -> dict:
    """获取打卡积分配置（从通用规则读取）"""
    try:
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_key.in_([
                "healthCheckIn",
                "healthCheckInDailyLimit",
            ]))
        )
        configs = {c.config_key: c.config_value for c in result.scalars().all()}

        per_action = 0
        daily_limit = 0
        try:
            per_action = int(configs.get("healthCheckIn", "0"))
        except (ValueError, TypeError):
            logger.warning(f"healthCheckIn 配置值无效: {configs.get('healthCheckIn')}, 使用默认值 0")
        try:
            daily_limit = int(configs.get("healthCheckInDailyLimit", "0"))
        except (ValueError, TypeError):
            logger.warning(f"healthCheckInDailyLimit 配置值无效: {configs.get('healthCheckInDailyLimit')}, 使用默认值 0")

        enabled = per_action > 0
        return {
            "enabled": enabled,
            "per_action": per_action,
            "daily_limit": daily_limit,
        }
    except Exception as e:
        logger.error(f"读取打卡积分配置异常: {e}")
        return {"enabled": False, "per_action": 0, "daily_limit": 0}


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
    打卡时发放积分（异常安全：任何异常都不影响打卡本身）

    Args:
        db: 数据库会话
        user: 用户对象
        checkin_type: 打卡类型描述

    Returns:
        dict: {"points_earned": int, "points_limit_reached": bool}
    """
    try:
        config = await get_checkin_points_config(db)

        if not config["enabled"]:
            return {"points_earned": 0, "points_limit_reached": False}

        earned_today = await get_today_checkin_points(db, user.id)

        if config["daily_limit"] > 0:
            remaining = config["daily_limit"] - earned_today
            if remaining <= 0:
                return {"points_earned": 0, "points_limit_reached": True}
            actual_points = min(config["per_action"], remaining)
        else:
            actual_points = config["per_action"]

        user.points = (user.points or 0) + actual_points

        pr = PointsRecord(
            user_id=user.id,
            points=actual_points,
            type=PointsType.checkin,
            description=checkin_type,
        )
        db.add(pr)

        new_total = earned_today + actual_points
        limit_reached = config["daily_limit"] > 0 and new_total >= config["daily_limit"]

        logger.info(f"用户 {user.id} 打卡积分: +{actual_points}, 今日累计: {new_total}/{config['daily_limit']}")

        return {"points_earned": actual_points, "points_limit_reached": limit_reached}
    except Exception as e:
        logger.error(f"打卡积分发放异常 (用户: {user.id}, 类型: {checkin_type}): {e}", exc_info=True)
        return {"points_earned": 0, "points_limit_reached": False}


async def award_complete_profile_points(db: AsyncSession, user: User, profile) -> dict:
    """
    完善健康档案时发放积分（一次性奖励，终身只发一次）

    Args:
        db: 数据库会话
        user: 用户对象
        profile: HealthProfile 对象

    Returns:
        dict: {"points_earned": int, "already_awarded": bool}
    """
    try:
        core_fields = [profile.gender, profile.birthday, profile.height, profile.weight]
        if not all(f is not None for f in core_fields):
            return {"points_earned": 0, "already_awarded": False}

        existing = await db.execute(
            select(PointsRecord).where(
                PointsRecord.user_id == user.id,
                PointsRecord.type == PointsType.completeProfile,
            )
        )
        if existing.scalar_one_or_none():
            return {"points_earned": 0, "already_awarded": True}

        config_result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_key == "completeProfile")
        )
        config = config_result.scalar_one_or_none()
        points_value = 0
        if config:
            try:
                points_value = int(config.config_value)
            except (ValueError, TypeError):
                logger.warning(f"completeProfile 配置值无效: {config.config_value}")

        if points_value <= 0:
            return {"points_earned": 0, "already_awarded": False}

        user.points = (user.points or 0) + points_value

        pr = PointsRecord(
            user_id=user.id,
            points=points_value,
            type=PointsType.completeProfile,
            description="完善健康档案",
        )
        db.add(pr)

        logger.info(f"用户 {user.id} 完善健康档案积分: +{points_value}")

        return {"points_earned": points_value, "already_awarded": False}
    except Exception as e:
        logger.error(f"完善健康档案积分发放异常 (用户: {user.id}): {e}", exc_info=True)
        return {"points_earned": 0, "already_awarded": False}


async def get_today_progress(db: AsyncSession, user_id: int) -> dict:
    """获取用户今日打卡积分进度"""
    config = await get_checkin_points_config(db)
    earned_today = await get_today_checkin_points(db, user_id)

    return {
        "earned_today": earned_today,
        "daily_limit": config["daily_limit"],
        "is_limit_reached": config["daily_limit"] > 0 and earned_today >= config["daily_limit"],
        "enabled": config["enabled"],
    }
