import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_sms(phone: str, code: str) -> None:
    secret_id = settings.TENCENT_SMS_SECRET_ID
    secret_key = settings.TENCENT_SMS_SECRET_KEY

    if not secret_id or not secret_key:
        logger.warning(
            "TENCENT_SMS_SECRET_ID / TENCENT_SMS_SECRET_KEY 未配置，跳过短信发送 "
            "(phone=%s, code=%s)",
            phone,
            code,
        )
        return

    try:
        from tencentcloud.common import credential
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
            TencentCloudSDKException,
        )
        from tencentcloud.sms.v20210111 import models, sms_client

        cred = credential.Credential(secret_id, secret_key)
        client = sms_client.SmsClient(cred, "ap-guangzhou")

        req = models.SendSmsRequest()
        req.SmsSdkAppId = settings.TENCENT_SMS_SDK_APP_ID
        req.SignName = settings.TENCENT_SMS_SIGN_NAME
        req.TemplateId = settings.TENCENT_SMS_TEMPLATE_ID
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
            raise RuntimeError(f"短信发送失败: {send_status.Message}")

        logger.info("短信发送成功: phone=%s", phone)

    except TencentCloudSDKException as exc:
        logger.error("腾讯云 SDK 异常: %s", exc)
        raise RuntimeError(f"短信发送失败: {exc}") from exc
