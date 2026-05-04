from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://root:password@db:3306/bini_health"
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
