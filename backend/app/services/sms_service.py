import base64
import hashlib
import hmac
import json
import logging
import urllib.parse
import uuid
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


async def _get_db_sms_config(db: AsyncSession | None = None, provider: str | None = None):
    from app.models.models import SmsConfig

    async def _query(session: AsyncSession):
        if provider:
            result = await session.execute(
                select(SmsConfig).where(SmsConfig.provider == provider).limit(1)
            )
            return result.scalar_one_or_none()
        result = await session.execute(
            select(SmsConfig).where(SmsConfig.is_active == True).limit(1)  # noqa: E712
        )
        return result.scalar_one_or_none()

    if db is not None:
        return await _query(db)

    async with async_session() as session:
        return await _query(session)


async def _resolve_sms_config(db: AsyncSession | None = None, provider: str | None = None):
    """
    Resolve SMS credentials for the given provider.
    If provider is specified, fetch that provider's config regardless of is_active.
    If provider is None, use the active config.
    Falls back to environment variables for tencent.
    """
    db_config = await _get_db_sms_config(db, provider=provider)

    if db_config:
        resolved_provider = db_config.provider or "tencent"
        if resolved_provider == "aliyun":
            if db_config.access_key_id and db_config.access_key_secret_encrypted:
                return {
                    "provider": "aliyun",
                    "access_key_id": db_config.access_key_id,
                    "access_key_secret": decrypt_secret_key(db_config.access_key_secret_encrypted),
                    "sign_name": db_config.sign_name or "",
                    "template_id": db_config.template_id or "",
                }
        else:
            if db_config.secret_id and db_config.secret_key_encrypted:
                return {
                    "provider": "tencent",
                    "secret_id": db_config.secret_id,
                    "secret_key": decrypt_secret_key(db_config.secret_key_encrypted),
                    "sdk_app_id": db_config.sdk_app_id or settings.TENCENT_SMS_SDK_APP_ID,
                    "sign_name": db_config.sign_name or settings.TENCENT_SMS_SIGN_NAME,
                    "template_id": db_config.template_id or settings.TENCENT_SMS_TEMPLATE_ID,
                }

    if provider and provider == "aliyun":
        raise RuntimeError("阿里云短信服务未配置：数据库中无有效阿里云短信配置")

    secret_id = settings.TENCENT_SMS_SECRET_ID
    secret_key = settings.TENCENT_SMS_SECRET_KEY
    if secret_id and secret_key:
        return {
            "provider": "tencent",
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
    provider: str | None = None,
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
        provider=provider,
    )

    if db is not None:
        db.add(log)
        return

    async with async_session() as session:
        session.add(log)
        await session.commit()


async def _send_via_tencent(phone: str, code: str, cfg: dict) -> None:
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
    req.TemplateId = cfg["template_id"]
    req.TemplateParamSet = [code, "5"]
    req.PhoneNumberSet = [f"+86{phone}"]

    resp = client.SendSms(req)

    send_status = resp.SendStatusSet[0]
    if send_status.Code != "Ok":
        raise RuntimeError(f"短信发送失败: {send_status.Message}")

    logger.info("腾讯云短信发送成功: phone=%s", phone)


async def _send_via_aliyun(phone: str, code: str, cfg: dict) -> None:
    try:
        from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
        from alibabacloud_tea_openapi.models import Config as OpenApiConfig
        from alibabacloud_dysmsapi20170525.models import SendSmsRequest

        config = OpenApiConfig(
            access_key_id=cfg["access_key_id"],
            access_key_secret=cfg["access_key_secret"],
        )
        config.endpoint = "dysmsapi.aliyuncs.com"
        client = DysmsapiClient(config)

        request = SendSmsRequest(
            phone_numbers=phone,
            sign_name=cfg["sign_name"],
            template_code=cfg["template_id"],
            template_param=json.dumps({"code": code}),
        )
        resp = client.send_sms(request)
        body = resp.body
        if body.code != "OK":
            raise RuntimeError(f"短信发送失败: {body.message}")
        logger.info("阿里云短信发送成功: phone=%s", phone)

    except ImportError:
        logger.info("alibabacloud SDK not installed, using HTTP API fallback")
        await _send_via_aliyun_http(phone, code, cfg)


async def _send_via_aliyun_http(phone: str, code: str, cfg: dict) -> None:
    """Fallback: call Alibaba Cloud SMS via HTTP API without SDK."""
    import httpx

    access_key_id = cfg["access_key_id"]
    access_key_secret = cfg["access_key_secret"]

    params = {
        "AccessKeyId": access_key_id,
        "Action": "SendSms",
        "Format": "JSON",
        "PhoneNumbers": phone,
        "RegionId": "cn-hangzhou",
        "SignName": cfg["sign_name"],
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": str(uuid.uuid4()),
        "SignatureVersion": "1.0",
        "TemplateCode": cfg["template_id"],
        "TemplateParam": json.dumps({"code": code}),
        "Timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Version": "2017-05-25",
    }

    sorted_params = sorted(params.items())
    query_string = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)
    string_to_sign = "GET&%2F&" + urllib.parse.quote(query_string, safe="")
    sign_key = (access_key_secret + "&").encode("utf-8")
    signature = base64.b64encode(
        hmac.new(sign_key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")
    params["Signature"] = signature

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://dysmsapi.aliyuncs.com/", params=params)
        result = resp.json()
        if result.get("Code") != "OK":
            raise RuntimeError(f"短信发送失败: {result.get('Message', '未知错误')}")
        logger.info("阿里云HTTP短信发送成功: phone=%s", phone)


async def send_sms(
    phone: str,
    code: str,
    is_test: bool = False,
    operator_id: int | None = None,
    provider: str | None = None,
    db: AsyncSession | None = None,
) -> None:
    cfg = await _resolve_sms_config(db, provider=provider)
    resolved_provider = cfg["provider"]
    template_id = cfg["template_id"]

    try:
        if resolved_provider == "aliyun":
            await _send_via_aliyun(phone, code, cfg)
        else:
            await _send_via_tencent(phone, code, cfg)

        await _record_sms_log(
            phone, code, template_id, "success",
            is_test=is_test, operator_id=operator_id,
            provider=resolved_provider, db=db,
        )

    except RuntimeError as exc:
        await _record_sms_log(
            phone, code, template_id, "failed",
            error_message=str(exc),
            is_test=is_test, operator_id=operator_id,
            provider=resolved_provider, db=db,
        )
        raise

    except Exception as exc:
        logger.error("短信发送异常 (%s): %s", resolved_provider, exc)
        await _record_sms_log(
            phone, code, template_id, "failed",
            error_message=str(exc),
            is_test=is_test, operator_id=operator_id,
            provider=resolved_provider, db=db,
        )
        raise RuntimeError(f"短信发送失败: {exc}") from exc
