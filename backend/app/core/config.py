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
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""

    UPLOAD_DIR: str = "uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
