import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.security import get_password_hash
from app.models.models import (
    ConstitutionQuestion,
    MemberLevel,
    ServiceCategory,
    SystemConfig,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)


async def init_default_data():
    async with async_session() as db:
        try:
            await _init_admin(db)
            await _init_service_categories(db)
            await _init_member_levels(db)
            await _init_system_configs(db)
            await _init_constitution_questions(db)
            await db.commit()
            logger.info("Default data initialization completed")
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to initialize default data: {e}")
            raise


async def _init_admin(db: AsyncSession):
    result = await db.execute(
        select(User).where(User.role == UserRole.admin).limit(1)
    )
    if result.scalar_one_or_none():
        return

    admin = User(
        phone="13800000000",
        password_hash="$2b$12$LJ3m4ys3zGHlOhKGxXWpPuVHCDLSDKUqG9nJKPPMhmFQpJCRYCXWm",
        nickname="平台管理员",
        role=UserRole.admin,
        status="active",
    )
    db.add(admin)
    await db.flush()
    logger.info("Created default admin user (phone: 13800000000)")


async def _init_service_categories(db: AsyncSession):
    result = await db.execute(select(ServiceCategory).limit(1))
    if result.scalar_one_or_none():
        return

    categories = [
        {"name": "健康食品", "icon": "🥗", "description": "精选优质健康食品", "sort_order": 1},
        {"name": "口腔服务", "icon": "🦷", "description": "专业口腔护理服务", "sort_order": 2},
        {"name": "体检服务", "icon": "🏥", "description": "全面体检套餐", "sort_order": 3},
        {"name": "专家咨询", "icon": "👨‍⚕️", "description": "权威专家一对一咨询", "sort_order": 4},
        {"name": "养老服务", "icon": "🏠", "description": "贴心养老关怀服务", "sort_order": 5},
    ]
    for cat in categories:
        db.add(ServiceCategory(**cat, status="active"))
    await db.flush()
    logger.info("Created default service categories")


async def _init_member_levels(db: AsyncSession):
    result = await db.execute(select(MemberLevel).limit(1))
    if result.scalar_one_or_none():
        return

    levels = [
        {
            "level_name": "普通会员",
            "min_points": 0,
            "max_points": 999,
            "discount_rate": 1.0,
            "benefits": {"desc": "基础会员权益"},
        },
        {
            "level_name": "银卡会员",
            "min_points": 1000,
            "max_points": 4999,
            "discount_rate": 0.95,
            "benefits": {"desc": "95折优惠, 优先预约"},
        },
        {
            "level_name": "金卡会员",
            "min_points": 5000,
            "max_points": 19999,
            "discount_rate": 0.9,
            "benefits": {"desc": "9折优惠, 专属客服, 优先预约"},
        },
        {
            "level_name": "钻石会员",
            "min_points": 20000,
            "max_points": 999999,
            "discount_rate": 0.85,
            "benefits": {"desc": "85折优惠, 专属客服, 优先预约, 免费体检"},
        },
    ]
    for level in levels:
        db.add(MemberLevel(**level))
    await db.flush()
    logger.info("Created default member levels")


async def _init_system_configs(db: AsyncSession):
    result = await db.execute(select(SystemConfig).limit(1))
    if result.scalar_one_or_none():
        return

    configs = [
        {
            "config_key": "site_name",
            "config_value": "宾尼小康 AI健康管家",
            "config_type": "string",
            "description": "站点名称",
        },
        {
            "config_key": "signin_base_points",
            "config_value": "10",
            "config_type": "number",
            "description": "每日签到基础积分",
        },
        {
            "config_key": "signin_consecutive_bonus",
            "config_value": "5",
            "config_type": "number",
            "description": "连续签到每天额外奖励积分",
        },
        {
            "config_key": "points_per_yuan",
            "config_value": "10",
            "config_type": "number",
            "description": "每消费1元获得的积分",
        },
        {
            "config_key": "invite_reward_points",
            "config_value": "100",
            "config_type": "number",
            "description": "邀请好友奖励积分",
        },
    ]
    for cfg in configs:
        db.add(SystemConfig(**cfg))
    await db.flush()
    logger.info("Created default system configs")


async def _init_constitution_questions(db: AsyncSession):
    result = await db.execute(select(ConstitutionQuestion).limit(1))
    if result.scalar_one_or_none():
        return

    options_5level = json.dumps(
        ["没有", "很少", "有时", "经常", "总是"], ensure_ascii=False
    )

    questions = [
        # 气虚质
        {"question_text": "您容易疲乏吗？", "question_group": "气虚质", "order_num": 1},
        {"question_text": "您容易气短（呼吸短促、接不上气）吗？", "question_group": "气虚质", "order_num": 2},
        {"question_text": "您容易心慌吗？", "question_group": "气虚质", "order_num": 3},
        {"question_text": "您容易头晕或站起时晕眩吗？", "question_group": "气虚质", "order_num": 4},
        # 阳虚质
        {"question_text": "您手脚发凉吗？", "question_group": "阳虚质", "order_num": 5},
        {"question_text": "您胃脘部、背部或腰膝部怕冷吗？", "question_group": "阳虚质", "order_num": 6},
        {"question_text": "您比一般人耐受不了寒冷吗？", "question_group": "阳虚质", "order_num": 7},
        {"question_text": "您吃（喝）凉的东西会感到不舒服或者怕吃凉的吗？", "question_group": "阳虚质", "order_num": 8},
        # 阴虚质
        {"question_text": "您感到手脚心发热吗？", "question_group": "阴虚质", "order_num": 9},
        {"question_text": "您感觉身体、脸上发热吗？", "question_group": "阴虚质", "order_num": 10},
        {"question_text": "您皮肤或口唇干吗？", "question_group": "阴虚质", "order_num": 11},
        {"question_text": "您感到眼睛干涩吗？", "question_group": "阴虚质", "order_num": 12},
        # 痰湿质
        {"question_text": "您感到胸闷或腹部胀满吗？", "question_group": "痰湿质", "order_num": 13},
        {"question_text": "您感到身体沉重不轻松吗？", "question_group": "痰湿质", "order_num": 14},
        {"question_text": "您腹部肥满松软吗？", "question_group": "痰湿质", "order_num": 15},
        {"question_text": "您额头部位油脂分泌多吗？", "question_group": "痰湿质", "order_num": 16},
        # 湿热质
        {"question_text": "您面部或鼻部有油腻感或者油亮发光吗？", "question_group": "湿热质", "order_num": 17},
        {"question_text": "您容易生痤疮或疮疖吗？", "question_group": "湿热质", "order_num": 18},
        {"question_text": "您感到口苦或嘴里有异味吗？", "question_group": "湿热质", "order_num": 19},
        {"question_text": "您大便黏滞不爽、有解不尽的感觉吗？", "question_group": "湿热质", "order_num": 20},
        # 血瘀质
        {"question_text": "您皮肤在不知不觉中会出现青紫瘀斑吗？", "question_group": "血瘀质", "order_num": 21},
        {"question_text": "您两颧部有细微红丝吗？", "question_group": "血瘀质", "order_num": 22},
        {"question_text": "您身体上有哪里疼痛吗？", "question_group": "血瘀质", "order_num": 23},
        {"question_text": "您面色晦暗或容易出现褐斑吗？", "question_group": "血瘀质", "order_num": 24},
        # 气郁质
        {"question_text": "您感到闷闷不乐、情绪低沉吗？", "question_group": "气郁质", "order_num": 25},
        {"question_text": "您容易精神紧张、焦虑不安吗？", "question_group": "气郁质", "order_num": 26},
        {"question_text": "您多愁善感、感情脆弱吗？", "question_group": "气郁质", "order_num": 27},
        {"question_text": "您容易感到害怕或受到惊吓吗？", "question_group": "气郁质", "order_num": 28},
        # 特禀质
        {"question_text": "您没有感冒时也会打喷嚏吗？", "question_group": "特禀质", "order_num": 29},
        {"question_text": "您没有感冒时也会鼻塞、流鼻涕吗？", "question_group": "特禀质", "order_num": 30},
        {"question_text": "您有因季节变化、温度变化或异味等原因而咳喘的现象吗？", "question_group": "特禀质", "order_num": 31},
        {"question_text": "您容易过敏（对药物、食物、气味、花粉等）吗？", "question_group": "特禀质", "order_num": 32},
        # 平和质
        {"question_text": "您精力充沛吗？", "question_group": "平和质", "order_num": 33},
        {"question_text": "您容易累吗？", "question_group": "平和质", "order_num": 34},
        {"question_text": "您说话声音低弱无力吗？", "question_group": "平和质", "order_num": 35},
        {"question_text": "您感到不开心吗？", "question_group": "平和质", "order_num": 36},
    ]
    for q in questions:
        db.add(
            ConstitutionQuestion(
                question_text=q["question_text"],
                question_group=q["question_group"],
                options=json.loads(options_5level),
                order_num=q["order_num"],
            )
        )
    await db.flush()
    logger.info("Created default constitution questions (36 questions, 9 types)")
