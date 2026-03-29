import base64
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session

logger = logging.getLogger(__name__)


def encrypt_secret_key(plain: str) -> str:
    return base64.b64encode(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret_key(encrypted: str) -> str:
    return base64.b64decode(encrypted.encode("utf-8")).decode("utf-8")


async def _get_db_sms_config(db: AsyncSession | None = None):
    """Return the active SmsConfig row from DB, or None."""
    from app.models.models import SmsConfig

    async def _query(session: AsyncSession):
        result = await session.execute(
            select(SmsConfig).where(SmsConfig.is_active == True).limit(1)  # noqa: E712
        )
        return result.scalar_one_or_none()

    if db is not None:
        return await _query(db)

    async with async_session() as session:
        return await _query(session)


async def _resolve_sms_config(db: AsyncSession | None = None):
    """
    Resolve SMS credentials.
    Priority: DB config (is_active=True) > environment variables.
    Returns a dict with keys: secret_id, secret_key, sdk_app_id, sign_name, template_id.
    Raises RuntimeError if neither source provides credentials.
    """
    db_config = await _get_db_sms_config(db)
    if db_config and db_config.secret_id and db_config.secret_key_encrypted:
        return {
            "secret_id": db_config.secret_id,
            "secret_key": decrypt_secret_key(db_config.secret_key_encrypted),
            "sdk_app_id": db_config.sdk_app_id or settings.TENCENT_SMS_SDK_APP_ID,
            "sign_name": db_config.sign_name or settings.TENCENT_SMS_SIGN_NAME,
            "template_id": db_config.template_id or settings.TENCENT_SMS_TEMPLATE_ID,
        }

    secret_id = settings.TENCENT_SMS_SECRET_ID
    secret_key = settings.TENCENT_SMS_SECRET_KEY
    if secret_id and secret_key:
        return {
            "secret_id": secret_id,
            "secret_key": secret_key,
            "sdk_app_id": settings.TENCENT_SMS_SDK_APP_ID,
            "sign_name": settings.TENCENT_SMS_SIGN_NAME,
            "template_id": settings.TENCENT_SMS_TEMPLATE_ID,
        }

    raise RuntimeError(
        "短信服务未配置：TENCENT_SMS_SECRET_ID / TENCENT_SMS_SECRET_KEY 未设置，且数据库中无有效短信配置"
    )


async def _record_sms_log(
    phone: str,
    code: str | None,
    template_id: str | None,
    status: str,
    error_message: str | None = None,
    is_test: bool = False,
    operator_id: int | None = None,
    db: AsyncSession | None = None,
):
    from app.models.models import SmsLog

    log = SmsLog(
        phone=phone,
        code=code,
        template_id=template_id,
        status=status,
        error_message=error_message,
        is_test=is_test,
        operator_id=operator_id,
    )

    if db is not None:
        db.add(log)
        return

    async with async_session() as session:
        session.add(log)
        await session.commit()


async def send_sms(
    phone: str,
    code: str,
    is_test: bool = False,
    operator_id: int | None = None,
    db: AsyncSession | None = None,
) -> None:
    cfg = await _resolve_sms_config(db)
    template_id = cfg["template_id"]

    try:
        from tencentcloud.common import credential
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
            TencentCloudSDKException,
        )
        from tencentcloud.sms.v20210111 import models, sms_client

        cred = credential.Credential(cfg["secret_id"], cfg["secret_key"])
        client = sms_client.SmsClient(cred, "ap-guangzhou")

        req = models.SendSmsRequest()
        req.SmsSdkAppId = cfg["sdk_app_id"]
        req.SignName = cfg["sign_name"]
        req.TemplateId = template_id
        req.TemplateParamSet = [code, "5"]
        req.PhoneNumberSet = [f"+86{phone}"]

        resp = client.SendSms(req)

        send_status = resp.SendStatusSet[0]
        if send_status.Code != "Ok":
            logger.error(
                "腾讯云短信发送失败: code=%s, message=%s",
                send_status.Code,
                send_status.Message,
            )
            await _record_sms_log(
                phone, code, template_id, "failed",
                error_message=send_status.Message,
                is_test=is_test, operator_id=operator_id, db=db,
            )
            raise RuntimeError(f"短信发送失败: {send_status.Message}")

        logger.info("短信发送成功: phone=%s", phone)
        await _record_sms_log(
            phone, code, template_id, "success",
            is_test=is_test, operator_id=operator_id, db=db,
        )

    except TencentCloudSDKException as exc:
        logger.error("腾讯云 SDK 异常: %s", exc)
        await _record_sms_log(
            phone, code, template_id, "failed",
            error_message=str(exc),
            is_test=is_test, operator_id=operator_id, db=db,
        )
        raise RuntimeError(f"短信发送失败: {exc}") from exc
