from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://root:bini_health_2026@localhost:3306/bini_health"
    SECRET_KEY: str = "bini-health-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    AI_BASE_URL: str = ""
    AI_MODEL_NAME: str = ""
    AI_API_KEY: str = ""

    SMS_API_KEY: str = ""

    TENCENT_SMS_SECRET_ID: str = ""
    TENCENT_SMS_SECRET_KEY: str = ""
    TENCENT_SMS_SDK_APP_ID: str = "1400920269"
    TENCENT_SMS_SIGN_NAME: str = "呃唉帮帮网络"
    TENCENT_SMS_TEMPLATE_ID: str = "2201340"
    TENCENT_SMS_APP_KEY: str = "7e3c8242bf0799cca367fa18fa47a7ea"

    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""

    UPLOAD_DIR: str = "uploads"

    # [H5 支付链路修复 v1.0] 项目对外基础 URL（如 https://example.com/bnbbaijkgj），
    # 用于构造支付宝 H5 沙盒收银台 pay_url。生产接入真实支付后可移除依赖。
    PROJECT_BASE_URL: str = ""

    # [订单核销码状态与未支付超时治理 v1.0]
    # 全局支付超时分钟数：
    # 1) 「未支付超时自动取消」定时任务的判定阈值
    # 2) H5 下单流程中 `_count_occupied*` 系列对 pending_payment 的占用保护时长
    # 3) 创建订单后站内信文案中的"X 分钟内完成支付"的 X
    # 默认 15 分钟（与团购到店行业惯例一致），通过 .env 覆盖后重启服务生效。
    PAYMENT_TIMEOUT_MINUTES: int = 15

    # [BUG-461 (2026-05-11)] AI 对话「旧会话 X 小时无活动 → 自动开新会话」阈值
    # 默认 6 小时，运营可通过 .env 覆盖为 4 / 8 / 12 等。
    # 判定字段：ChatSession.updated_at（最后一次消息往返时间）
    # [PRD-AI-HOME-OPTIM-V4 2026-05-21] v4 已废除 6 小时切片机制，统一为下方 60 分钟刷新阈值
    AI_CHAT_AUTO_NEW_SESSION_HOURS: int = 6

    # [PRD-AI-HOME-OPTIM-V4 2026-05-21] AI 首页 60 分钟定时自动刷新机制阈值
    # 默认 60 分钟（与蚂蚁阿福 / 晓医对标），运营可通过 .env 覆盖为 30 / 90 / 120 等
    # 进入 AI 首页时若 (now - 上次会话 updated_at) >= SESSION_REFRESH_MINUTES，
    # 则不加载旧会话，直接进入空欢迎页（清空旧会话）
    SESSION_REFRESH_MINUTES: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
