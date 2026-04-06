import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.security import get_password_hash
from app.models.models import (
    AIModelTemplate,
    AiDisclaimerConfig,
    AiPromptConfig,
    AiSensitiveWord,
    ChatMessage,
    ChatSession,
    ConstitutionQuestion,
    MemberLevel,
    OcrConfig,
    ServiceCategory,
    SmsConfig,
    SmsTemplate,
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
            await _init_ai_model_templates(db)
            await _migrate_push_config_keys(db)
            await _migrate_sms_config_provider(db)
            await _init_sms_config_and_template(db)
            await _init_ai_center_configs(db)
            await _init_ocr_config(db)
            await _clean_chat_history_once(db)
            await db.commit()
            logger.info("Default data initialization completed")
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to initialize default data: {e}")
            raise


async def _init_admin(db: AsyncSession):
    from app.core.security import verify_password

    default_phone = "13800000000"
    default_password = "admin123"

    result = await db.execute(
        select(User).where(User.role == UserRole.admin).limit(1)
    )
    existing_admin = result.scalar_one_or_none()
    if existing_admin:
        changed = False
        if existing_admin.phone != default_phone:
            existing_admin.phone = default_phone
            changed = True
        if not existing_admin.password_hash or not verify_password(default_password, existing_admin.password_hash):
            existing_admin.password_hash = get_password_hash(default_password)
            changed = True
        if changed:
            await db.flush()
            logger.info("Reset admin credentials to phone=%s", default_phone)
        return

    admin = User(
        phone=default_phone,
        password_hash=get_password_hash(default_password),
        nickname="平台管理员",
        role=UserRole.admin,
        status="active",
    )
    db.add(admin)
    await db.flush()
    logger.info("Created default admin user (phone: %s)", default_phone)


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
            "icon": "🥉",
            "min_points": 0,
            "max_points": 999,
            "discount_rate": 1.0,
            "benefits": {"desc": "基础会员权益"},
            "color": "#8c8c8c",
        },
        {
            "level_name": "银卡会员",
            "icon": "🥈",
            "min_points": 1000,
            "max_points": 4999,
            "discount_rate": 0.95,
            "benefits": {"desc": "95折优惠, 优先预约"},
            "color": "#a0d911",
        },
        {
            "level_name": "金卡会员",
            "icon": "🥇",
            "min_points": 5000,
            "max_points": 19999,
            "discount_rate": 0.9,
            "benefits": {"desc": "9折优惠, 专属客服, 优先预约"},
            "color": "#faad14",
        },
        {
            "level_name": "钻石会员",
            "icon": "💎",
            "min_points": 20000,
            "max_points": 999999,
            "discount_rate": 0.85,
            "benefits": {"desc": "85折优惠, 专属客服, 优先预约, 免费体检"},
            "color": "#1890ff",
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
        {
            "config_key": "register_enable_self_registration",
            "config_value": "True",
            "config_type": "register",
            "description": "是否开放自助注册",
        },
        {
            "config_key": "register_wechat_register_mode",
            "config_value": "authorize_member",
            "config_type": "register",
            "description": "微信端注册方式",
        },
        {
            "config_key": "register_register_page_layout",
            "config_value": "vertical",
            "config_type": "register",
            "description": "注册页布局",
        },
        {
            "config_key": "register_show_profile_completion_prompt",
            "config_value": "True",
            "config_type": "register",
            "description": "会员信息补充提醒",
        },
        {
            "config_key": "register_member_card_no_rule",
            "config_value": "incremental",
            "config_type": "register",
            "description": "会员卡号生成规则",
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


async def _init_ai_model_templates(db: AsyncSession):
    result = await db.execute(select(AIModelTemplate).limit(1))
    if result.scalar_one_or_none():
        return

    templates = [
        {
            "name": "火山引擎 DeepSeek-V3.2",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "model_name": "deepseek-v3-241226",
            "icon": "volcano",
            "description": "火山引擎提供的 DeepSeek V3.2 模型服务，适合通用对话和文本生成场景",
        },
        {
            "name": "腾讯云 DeepSeek-V3.2",
            "base_url": "https://api.lkeap.cloud.tencent.com/v1",
            "model_name": "deepseek-v3",
            "icon": "tencent",
            "description": "腾讯云提供的 DeepSeek V3.2 模型服务，国内访问速度快，稳定可靠",
        },
    ]
    for tpl in templates:
        db.add(AIModelTemplate(**tpl))
    await db.flush()
    logger.info("Created default AI model templates")


_PUSH_KEY_MIGRATION = {
    "push_enable_wechat_push": "wechat_push_enable",
    "push_wechat_app_id": "wechat_push_app_id",
    "push_wechat_app_secret": "wechat_push_app_secret",
    "push_order_notify_template": "wechat_push_order_notify_template",
    "push_service_notify_template": "wechat_push_service_notify_template",
    "push_enable_email_notify": "email_notify_enable",
    "push_smtp_host": "email_notify_smtp_host",
    "push_smtp_port": "email_notify_smtp_port",
    "push_smtp_user": "email_notify_smtp_user",
    "push_smtp_password": "email_notify_smtp_password",
}


async def _migrate_push_config_keys(db: AsyncSession):
    """Migrate legacy push_* SystemConfig keys to new namespaced keys (idempotent)."""
    old_keys = list(_PUSH_KEY_MIGRATION.keys())
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(old_keys))
    )
    old_configs = {c.config_key: c.config_value for c in result.scalars().all()}
    if not old_configs:
        return

    new_keys = list(_PUSH_KEY_MIGRATION.values())
    result = await db.execute(
        select(SystemConfig.config_key).where(SystemConfig.config_key.in_(new_keys))
    )
    existing_new = {row[0] for row in result.all()}

    migrated = 0
    for old_key, new_key in _PUSH_KEY_MIGRATION.items():
        if old_key in old_configs and new_key not in existing_new:
            config_type = "wechat_push" if new_key.startswith("wechat_push") else "email_notify"
            db.add(SystemConfig(
                config_key=new_key,
                config_value=old_configs[old_key],
                config_type=config_type,
                description=new_key,
            ))
            migrated += 1

    if migrated:
        await db.flush()
        logger.info("Migrated %d push config keys to new namespaces", migrated)


async def _migrate_sms_config_provider(db: AsyncSession):
    """Ensure existing SmsConfig rows have a provider value (default to 'tencent')."""
    result = await db.execute(
        select(SmsConfig).where(
            (SmsConfig.provider == None) | (SmsConfig.provider == "")  # noqa: E711
        )
    )
    configs = result.scalars().all()
    for cfg in configs:
        cfg.provider = "tencent"
    if configs:
        await db.flush()
        logger.info("Set provider='tencent' on %d existing SmsConfig rows", len(configs))


async def _init_sms_config_and_template(db: AsyncSession):
    """Seed default Tencent Cloud SMS config and login verification template."""
    from app.core.config import settings

    expected_sdk_app_id = settings.TENCENT_SMS_SDK_APP_ID or "1400920269"
    expected_app_key = settings.TENCENT_SMS_APP_KEY or "7e3c8242bf0799cca367fa18fa47a7ea"
    expected_sign_name = settings.TENCENT_SMS_SIGN_NAME or "呃唉帮帮网络"
    expected_template_id = settings.TENCENT_SMS_TEMPLATE_ID or "2201340"

    result = await db.execute(
        select(SmsConfig).where(SmsConfig.provider == "tencent").limit(1)
    )
    existing = result.scalar_one_or_none()
    if not existing:
        db.add(SmsConfig(
            provider="tencent",
            sdk_app_id=expected_sdk_app_id,
            app_key=expected_app_key,
            sign_name=expected_sign_name,
            template_id=expected_template_id,
            is_active=True,
        ))
        await db.flush()
        logger.info("Created default Tencent Cloud SMS config (AppKey mode)")
    else:
        changed = False
        if existing.sdk_app_id != expected_sdk_app_id:
            existing.sdk_app_id = expected_sdk_app_id
            changed = True
        if existing.app_key != expected_app_key:
            existing.app_key = expected_app_key
            changed = True
        if existing.sign_name != expected_sign_name:
            existing.sign_name = expected_sign_name
            changed = True
        if existing.template_id != expected_template_id:
            existing.template_id = expected_template_id
            changed = True
        if changed:
            await db.flush()
            logger.info("Updated Tencent SMS config to match env defaults")

    result = await db.execute(
        select(SmsTemplate).where(
            SmsTemplate.template_id == "2201340",
            SmsTemplate.provider == "tencent",
        ).limit(1)
    )
    if not result.scalar_one_or_none():
        variables = json.dumps([
            {"name": "验证码", "description": "6位数字验证码", "default": ""},
            {"name": "有效时间", "description": "验证码有效分钟数", "default": "5"},
        ], ensure_ascii=False)
        db.add(SmsTemplate(
            name="登录验证",
            provider="tencent",
            template_id="2201340",
            content="{1}为您的登录验证码，请于{2}分钟内填写，如非本人操作，请忽略本短信。",
            sign_name="呃唉帮帮网络",
            scene="login",
            variables=variables,
            status=True,
        ))
        await db.flush()
        logger.info("Created default SMS template: 登录验证 (template_id=2201340)")


async def _init_ai_center_configs(db: AsyncSession):
    # ── 提示词配置 ──
    result = await db.execute(select(AiPromptConfig).limit(1))
    if not result.scalar_one_or_none():
        prompts = [
            {
                "chat_type": "health_qa",
                "display_name": "健康问答",
                "system_prompt": (
                    "你是「宾尼小康」AI健康咨询助手，一个专业、友好的健康咨询助手。"
                    "请用通俗易懂的语言回答用户的健康相关问题，提供健康参考信息，"
                    "并在必要时建议用户及时就医。所有内容仅供健康参考，不构成任何医疗诊断或治疗建议。"
                ),
            },
            {
                "chat_type": "symptom_check",
                "display_name": "健康自查",
                "system_prompt": (
                    "你是一位专业的AI健康自查助手。请根据用户描述的身体状况进行初步健康参考分析，"
                    "给出可能的相关因素和健康建议。所有内容仅供自我健康参考，"
                    "不能替代专业医疗检查，如有异常请尽快就医。"
                ),
            },
            {
                "chat_type": "tcm",
                "display_name": "中医养生",
                "system_prompt": (
                    "你是一位中医AI养生助手，精通中医养生理论。请根据用户描述，"
                    "从中医养生角度提供调理建议。所有中医养生建议仅供参考，"
                    "个人体质不同，建议在专业中医师指导下调理。"
                ),
            },
            {
                "chat_type": "drug_query",
                "display_name": "用药参考",
                "system_prompt": (
                    "你是一位药学AI用药参考助手，请提供药品的基本信息供用户参考，"
                    "包括常见用法、注意事项、相互作用等。所有用药信息仅供参考，"
                    "具体用药请严格遵医嘱，切勿自行用药。"
                ),
            },
            {
                "chat_type": "customer_service",
                "display_name": "在线客服",
                "system_prompt": (
                    "你是「宾尼小康」平台的AI客服助手，请热情友好地解答用户关于平台服务的问题。"
                ),
            },
        ]
        for p in prompts:
            db.add(AiPromptConfig(**p))
        await db.flush()
        logger.info("Created default AI prompt configs")

    # ── 免责提示配置 ──
    result = await db.execute(select(AiDisclaimerConfig).limit(1))
    if not result.scalar_one_or_none():
        disclaimers = [
            {
                "chat_type": "health_qa",
                "display_name": "健康问答",
                "disclaimer_text": "以上内容仅供健康参考，不构成任何医疗诊断或治疗建议，如有不适请及时就医。",
                "is_enabled": True,
            },
            {
                "chat_type": "symptom_check",
                "display_name": "健康自查",
                "disclaimer_text": "以上内容仅供自我健康参考，不能替代专业医疗检查，如有异常请尽快就医。",
                "is_enabled": True,
            },
            {
                "chat_type": "tcm",
                "display_name": "中医养生",
                "disclaimer_text": "以上中医养生建议仅供参考，个人体质不同，建议在专业中医师指导下调理。",
                "is_enabled": True,
            },
            {
                "chat_type": "drug_query",
                "display_name": "用药参考",
                "disclaimer_text": "以上用药信息仅供参考，具体用药请严格遵医嘱，切勿自行用药。",
                "is_enabled": True,
            },
            {
                "chat_type": "customer_service",
                "display_name": "在线客服",
                "disclaimer_text": "",
                "is_enabled": False,
            },
        ]
        for d in disclaimers:
            db.add(AiDisclaimerConfig(**d))
        await db.flush()
        logger.info("Created default AI disclaimer configs")

    # ── 默认敏感词 ──
    result = await db.execute(select(AiSensitiveWord).limit(1))
    if not result.scalar_one_or_none():
        words = [
            {"sensitive_word": "诊断为", "replacement_word": "可能与…有关"},
            {"sensitive_word": "确诊", "replacement_word": "初步判断"},
            {"sensitive_word": "处方", "replacement_word": "建议参考"},
            {"sensitive_word": "开药", "replacement_word": "建议咨询医生后用药"},
        ]
        for w in words:
            db.add(AiSensitiveWord(**w))
        await db.flush()
        logger.info("Created default AI sensitive words")


async def _init_ocr_config(db: AsyncSession):
    result = await db.execute(select(OcrConfig).limit(1))
    if result.scalar_one_or_none():
        return

    db.add(OcrConfig(
        enabled=True,
        ocr_type="general_basic",
    ))
    await db.flush()
    logger.info("Created default OCR config")


async def _clean_chat_history_once(db: AsyncSession):
    flag_key = "ai_chat_history_cleaned"
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == flag_key)
    )
    if result.scalar_one_or_none():
        return

    from sqlalchemy import delete
    await db.execute(delete(ChatMessage))
    await db.execute(delete(ChatSession))

    db.add(SystemConfig(
        config_key=flag_key,
        config_value="true",
        config_type="system",
        description="AI聊天记录一次性清理标志",
    ))
    await db.flush()
    logger.info("Cleaned all chat history (one-time migration)")
