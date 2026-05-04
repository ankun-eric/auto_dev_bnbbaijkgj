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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
