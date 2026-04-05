import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import EmailLog, SystemConfig
from app.schemas.email_notify import (
    EmailConfigResponse,
    EmailConfigUpdate,
    EmailLogResponse,
    EmailTestRequest,
)
from app.services.sms_service import decrypt_secret_key, encrypt_secret_key

router = APIRouter(prefix="/api/admin/email-notify", tags=["邮件通知管理"])

admin_dep = require_role("admin")
logger = logging.getLogger(__name__)

_KEYS = [
    "email_notify_enable",
    "email_notify_smtp_host",
    "email_notify_smtp_port",
    "email_notify_smtp_user",
    "email_notify_smtp_password",
]


async def _get_config_map(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(_KEYS))
    )
    return {c.config_key: c.config_value for c in result.scalars().all()}


async def _set_config(db: AsyncSession, key: str, value: str, config_type: str = "email_notify"):
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    config = result.scalar_one_or_none()
    if config:
        config.config_value = value
        config.updated_at = datetime.utcnow()
    else:
        db.add(SystemConfig(config_key=key, config_value=value, config_type=config_type, description=key))


@router.get("/config", response_model=EmailConfigResponse)
async def get_email_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    m = await _get_config_map(db)
    port_str = m.get("email_notify_smtp_port")
    return EmailConfigResponse(
        enable_email_notify=m.get("email_notify_enable", "").lower() == "true",
        smtp_host=m.get("email_notify_smtp_host"),
        smtp_port=int(port_str) if port_str and port_str.isdigit() else None,
        smtp_user=m.get("email_notify_smtp_user"),
        has_smtp_password=bool(m.get("email_notify_smtp_password")),
    )


@router.put("/config", response_model=EmailConfigResponse)
async def update_email_config(
    data: EmailConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    if data.enable_email_notify is not None:
        await _set_config(db, "email_notify_enable", str(data.enable_email_notify))
    if data.smtp_host is not None:
        await _set_config(db, "email_notify_smtp_host", data.smtp_host)
    if data.smtp_port is not None:
        await _set_config(db, "email_notify_smtp_port", str(data.smtp_port))
    if data.smtp_user is not None:
        await _set_config(db, "email_notify_smtp_user", data.smtp_user)
    if data.smtp_password is not None:
        encrypted = encrypt_secret_key(data.smtp_password)
        await _set_config(db, "email_notify_smtp_password", encrypted)

    m = await _get_config_map(db)
    port_str = m.get("email_notify_smtp_port")
    return EmailConfigResponse(
        enable_email_notify=m.get("email_notify_enable", "").lower() == "true",
        smtp_host=m.get("email_notify_smtp_host"),
        smtp_port=int(port_str) if port_str and port_str.isdigit() else None,
        smtp_user=m.get("email_notify_smtp_user"),
        has_smtp_password=bool(m.get("email_notify_smtp_password")),
    )


@router.get("/logs")
async def get_email_logs(
    to_email: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(EmailLog)
    count_query = select(func.count(EmailLog.id))

    if to_email:
        query = query.where(EmailLog.to_email.contains(to_email))
        count_query = count_query.where(EmailLog.to_email.contains(to_email))
    if status:
        query = query.where(EmailLog.status == status)
        count_query = count_query.where(EmailLog.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(EmailLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [EmailLogResponse.model_validate(log) for log in result.scalars().all()]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/test")
async def test_email(
    data: EmailTestRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    m = await _get_config_map(db)
    smtp_host = m.get("email_notify_smtp_host")
    smtp_port_str = m.get("email_notify_smtp_port")
    smtp_user = m.get("email_notify_smtp_user")
    smtp_password_enc = m.get("email_notify_smtp_password")

    if not all([smtp_host, smtp_port_str, smtp_user, smtp_password_enc]):
        raise HTTPException(status_code=400, detail="邮件配置不完整，请先完成SMTP配置")

    smtp_port = int(smtp_port_str)
    smtp_password = decrypt_secret_key(smtp_password_enc)

    body = data.content or f"这是一封来自系统的测试邮件，发送时间: {datetime.utcnow().isoformat()}"

    email_log = EmailLog(
        to_email=data.to_email,
        subject=data.subject,
        content=body,
        status="pending",
        is_test=True,
        operator_id=current_user.id,
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = data.to_email
        msg["Subject"] = data.subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.starttls()

        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [data.to_email], msg.as_string())
        server.quit()

        email_log.status = "success"
        db.add(email_log)
        return {"success": True, "message": "测试邮件发送成功"}

    except Exception as exc:
        logger.error("邮件发送失败: %s", exc)
        email_log.status = "failed"
        email_log.error_message = str(exc)[:500]
        db.add(email_log)
        return {"success": False, "message": f"邮件发送失败: {exc}"}
