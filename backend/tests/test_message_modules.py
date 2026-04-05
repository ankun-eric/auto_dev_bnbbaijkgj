"""Tests for the message management modules: SMS (enhanced), WeChat push, Email notify."""

import pytest
from httpx import AsyncClient

from app.models.models import SmsConfig, SmsLog, SmsTemplate, EmailLog, SystemConfig
from app.services.sms_service import encrypt_secret_key


# ═══════════════════════════════════════════════════════════════
#  SMS Config
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sms_config_get_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/sms/config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "tencent" in data
    assert "aliyun" in data
    assert data["tencent"]["is_active"] is False
    assert data["aliyun"]["is_active"] is False


@pytest.mark.asyncio
async def test_sms_config_get_unauthorized(client: AsyncClient):
    resp = await client.get("/api/admin/sms/config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sms_config_get_forbidden_for_normal_user(client: AsyncClient, auth_headers):
    resp = await client.get("/api/admin/sms/config", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sms_config_put_tencent(client: AsyncClient, admin_headers):
    resp = await client.put("/api/admin/sms/config", json={
        "provider": "tencent",
        "secret_id": "AKIDxxxx",
        "secret_key": "my_secret",
        "sdk_app_id": "1400000001",
        "sign_name": "宾尼健康",
        "template_id": "123456",
        "is_active": True,
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["secret_id"] == "AKIDxxxx"
    assert data["sdk_app_id"] == "1400000001"
    assert data["is_active"] is True
    assert data["has_secret_key"] is True
    assert "secret_key" not in data


@pytest.mark.asyncio
async def test_sms_config_put_aliyun(client: AsyncClient, admin_headers):
    resp = await client.put("/api/admin/sms/config", json={
        "provider": "aliyun",
        "access_key_id": "LTAI_test",
        "access_key_secret": "aliyun_secret",
        "sign_name": "宾尼测试",
        "template_id": "SMS_100001",
        "is_active": True,
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_key_id"] == "LTAI_test"
    assert data["is_active"] is True
    assert data["has_access_key_secret"] is True
    assert "access_key_secret" not in data


@pytest.mark.asyncio
async def test_sms_config_put_invalid_provider(client: AsyncClient, admin_headers):
    resp = await client.put("/api/admin/sms/config", json={
        "provider": "huawei",
    }, headers=admin_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_sms_config_put_unauthorized(client: AsyncClient):
    resp = await client.put("/api/admin/sms/config", json={
        "provider": "tencent",
        "is_active": True,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sms_config_exclusive_active(client: AsyncClient, admin_headers):
    """Enabling one provider should disable the other."""
    await client.put("/api/admin/sms/config", json={
        "provider": "tencent",
        "secret_id": "AKIDxxxx",
        "secret_key": "key1",
        "sdk_app_id": "140",
        "sign_name": "A",
        "template_id": "T1",
        "is_active": True,
    }, headers=admin_headers)

    await client.put("/api/admin/sms/config", json={
        "provider": "aliyun",
        "access_key_id": "LTAI",
        "access_key_secret": "sec",
        "sign_name": "B",
        "template_id": "SMS_2",
        "is_active": True,
    }, headers=admin_headers)

    resp = await client.get("/api/admin/sms/config", headers=admin_headers)
    data = resp.json()
    assert data["aliyun"]["is_active"] is True
    assert data["tencent"]["is_active"] is False


# ═══════════════════════════════════════════════════════════════
#  SMS Templates CRUD
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sms_template_create(client: AsyncClient, admin_headers):
    resp = await client.post("/api/admin/sms/templates", json={
        "name": "验证码模板",
        "provider": "tencent",
        "template_id": "TPL_001",
        "content": "您的验证码是{code}",
        "sign_name": "宾尼",
        "scene": "verification",
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "验证码模板"
    assert data["provider"] == "tencent"
    assert data["template_id"] == "TPL_001"
    assert data["status"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_sms_template_create_missing_required(client: AsyncClient, admin_headers):
    resp = await client.post("/api/admin/sms/templates", json={
        "provider": "tencent",
    }, headers=admin_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sms_template_create_unauthorized(client: AsyncClient):
    resp = await client.post("/api/admin/sms/templates", json={
        "name": "test",
        "provider": "tencent",
        "template_id": "T1",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sms_template_list(client: AsyncClient, admin_headers):
    await client.post("/api/admin/sms/templates", json={
        "name": "模板A",
        "provider": "tencent",
        "template_id": "A01",
    }, headers=admin_headers)
    await client.post("/api/admin/sms/templates", json={
        "name": "模板B",
        "provider": "aliyun",
        "template_id": "B01",
    }, headers=admin_headers)

    resp = await client.get("/api/admin/sms/templates", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_sms_template_list_filter_provider(client: AsyncClient, admin_headers):
    await client.post("/api/admin/sms/templates", json={
        "name": "腾讯模板",
        "provider": "tencent",
        "template_id": "T100",
    }, headers=admin_headers)
    await client.post("/api/admin/sms/templates", json={
        "name": "阿里模板",
        "provider": "aliyun",
        "template_id": "A100",
    }, headers=admin_headers)

    resp = await client.get(
        "/api/admin/sms/templates", params={"provider": "tencent"}, headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["provider"] == "tencent"


@pytest.mark.asyncio
async def test_sms_template_update(client: AsyncClient, admin_headers):
    create_resp = await client.post("/api/admin/sms/templates", json={
        "name": "原始模板",
        "provider": "tencent",
        "template_id": "UP01",
    }, headers=admin_headers)
    tpl_id = create_resp.json()["id"]

    resp = await client.put(f"/api/admin/sms/templates/{tpl_id}", json={
        "name": "修改后模板",
        "content": "新内容",
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "修改后模板"
    assert resp.json()["content"] == "新内容"


@pytest.mark.asyncio
async def test_sms_template_update_not_found(client: AsyncClient, admin_headers):
    resp = await client.put("/api/admin/sms/templates/99999", json={
        "name": "不存在",
    }, headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sms_template_delete(client: AsyncClient, admin_headers):
    create_resp = await client.post("/api/admin/sms/templates", json={
        "name": "待删模板",
        "provider": "tencent",
        "template_id": "DEL01",
    }, headers=admin_headers)
    tpl_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/admin/sms/templates/{tpl_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert "删除" in resp.json()["message"]

    list_resp = await client.get("/api/admin/sms/templates", headers=admin_headers)
    assert list_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_sms_template_delete_not_found(client: AsyncClient, admin_headers):
    resp = await client.delete("/api/admin/sms/templates/99999", headers=admin_headers)
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
#  SMS Logs
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sms_logs_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/sms/logs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_sms_logs_with_records(client: AsyncClient, admin_headers, db_session):
    db_session.add(SmsLog(
        phone="13800001111",
        code="123456",
        template_id="T1",
        provider="tencent",
        status="success",
        is_test=False,
    ))
    db_session.add(SmsLog(
        phone="13800002222",
        code="654321",
        template_id="T2",
        provider="aliyun",
        status="failed",
        error_message="配额用完",
        is_test=True,
    ))
    await db_session.commit()

    resp = await client.get("/api/admin/sms/logs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_sms_logs_phone_masked(client: AsyncClient, admin_headers, db_session):
    db_session.add(SmsLog(
        phone="13800001111",
        code="000000",
        status="success",
        is_test=False,
    ))
    await db_session.commit()

    resp = await client.get("/api/admin/sms/logs", headers=admin_headers)
    data = resp.json()
    phone = data["items"][0]["phone"]
    assert "****" in phone
    assert phone == "138****1111"


@pytest.mark.asyncio
async def test_sms_logs_filter_provider(client: AsyncClient, admin_headers, db_session):
    db_session.add(SmsLog(phone="13800001111", status="success", provider="tencent", is_test=False))
    db_session.add(SmsLog(phone="13800002222", status="success", provider="aliyun", is_test=False))
    await db_session.commit()

    resp = await client.get(
        "/api/admin/sms/logs", params={"provider": "aliyun"}, headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["provider"] == "aliyun"


@pytest.mark.asyncio
async def test_sms_logs_unauthorized(client: AsyncClient):
    resp = await client.get("/api/admin/sms/logs")
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
#  SMS Test Send
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sms_test_send_no_config(client: AsyncClient, admin_headers, monkeypatch):
    """Without any SMS config, test send should return success=False (RuntimeError caught)."""
    async def _fail(*a, **kw):
        raise RuntimeError("短信服务未配置")
    monkeypatch.setattr("app.api.sms.send_sms", _fail)

    resp = await client.post("/api/admin/sms/test", json={
        "phone": "13800009999",
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_sms_test_send_success(client: AsyncClient, admin_headers, monkeypatch):
    async def _ok(*a, **kw):
        return None
    monkeypatch.setattr("app.api.sms.send_sms", _ok)

    resp = await client.post("/api/admin/sms/test", json={
        "phone": "13800009999",
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_sms_test_send_unauthorized(client: AsyncClient):
    resp = await client.post("/api/admin/sms/test", json={"phone": "13800009999"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sms_test_send_missing_phone(client: AsyncClient, admin_headers):
    resp = await client.post("/api/admin/sms/test", json={}, headers=admin_headers)
    assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════
#  WeChat Push Config
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_wechat_config_get_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/wechat-push/config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enable_wechat_push"] is False
    assert data["has_wechat_app_secret"] is False
    assert data["wechat_app_id"] is None


@pytest.mark.asyncio
async def test_wechat_config_get_unauthorized(client: AsyncClient):
    resp = await client.get("/api/admin/wechat-push/config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wechat_config_get_forbidden(client: AsyncClient, auth_headers):
    resp = await client.get("/api/admin/wechat-push/config", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_wechat_config_put(client: AsyncClient, admin_headers):
    resp = await client.put("/api/admin/wechat-push/config", json={
        "enable_wechat_push": True,
        "wechat_app_id": "wx1234567890",
        "wechat_app_secret": "my_wechat_secret",
        "order_notify_template": "TPL_ORDER_001",
        "service_notify_template": "TPL_SERVICE_001",
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enable_wechat_push"] is True
    assert data["wechat_app_id"] == "wx1234567890"
    assert data["has_wechat_app_secret"] is True
    assert data["order_notify_template"] == "TPL_ORDER_001"
    assert data["service_notify_template"] == "TPL_SERVICE_001"
    assert "wechat_app_secret" not in data


@pytest.mark.asyncio
async def test_wechat_config_put_unauthorized(client: AsyncClient):
    resp = await client.put("/api/admin/wechat-push/config", json={
        "enable_wechat_push": True,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wechat_config_put_partial_update(client: AsyncClient, admin_headers):
    await client.put("/api/admin/wechat-push/config", json={
        "wechat_app_id": "wxAAAA",
        "order_notify_template": "TPL_1",
    }, headers=admin_headers)

    await client.put("/api/admin/wechat-push/config", json={
        "enable_wechat_push": True,
    }, headers=admin_headers)

    resp = await client.get("/api/admin/wechat-push/config", headers=admin_headers)
    data = resp.json()
    assert data["enable_wechat_push"] is True
    assert data["wechat_app_id"] == "wxAAAA"
    assert data["order_notify_template"] == "TPL_1"


@pytest.mark.asyncio
async def test_wechat_config_secret_not_exposed(client: AsyncClient, admin_headers):
    """After saving app_secret, it should be stored encrypted and not returned in plaintext."""
    await client.put("/api/admin/wechat-push/config", json={
        "wechat_app_secret": "super_secret_value",
    }, headers=admin_headers)

    resp = await client.get("/api/admin/wechat-push/config", headers=admin_headers)
    data = resp.json()
    assert data["has_wechat_app_secret"] is True
    assert "wechat_app_secret" not in data
    assert "super_secret_value" not in str(data)


# ═══════════════════════════════════════════════════════════════
#  Email Notify Config
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_email_config_get_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/email-notify/config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enable_email_notify"] is False
    assert data["has_smtp_password"] is False
    assert data["smtp_host"] is None


@pytest.mark.asyncio
async def test_email_config_get_unauthorized(client: AsyncClient):
    resp = await client.get("/api/admin/email-notify/config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_email_config_get_forbidden(client: AsyncClient, auth_headers):
    resp = await client.get("/api/admin/email-notify/config", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_email_config_put(client: AsyncClient, admin_headers):
    resp = await client.put("/api/admin/email-notify/config", json={
        "enable_email_notify": True,
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
        "smtp_user": "user@example.com",
        "smtp_password": "email_pass_123",
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enable_email_notify"] is True
    assert data["smtp_host"] == "smtp.example.com"
    assert data["smtp_port"] == 465
    assert data["smtp_user"] == "user@example.com"
    assert data["has_smtp_password"] is True
    assert "smtp_password" not in data


@pytest.mark.asyncio
async def test_email_config_put_unauthorized(client: AsyncClient):
    resp = await client.put("/api/admin/email-notify/config", json={
        "enable_email_notify": True,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_email_config_put_partial_update(client: AsyncClient, admin_headers):
    await client.put("/api/admin/email-notify/config", json={
        "smtp_host": "smtp.test.com",
        "smtp_port": 587,
        "smtp_user": "admin@test.com",
    }, headers=admin_headers)

    await client.put("/api/admin/email-notify/config", json={
        "enable_email_notify": True,
    }, headers=admin_headers)

    resp = await client.get("/api/admin/email-notify/config", headers=admin_headers)
    data = resp.json()
    assert data["enable_email_notify"] is True
    assert data["smtp_host"] == "smtp.test.com"
    assert data["smtp_port"] == 587


@pytest.mark.asyncio
async def test_email_config_password_not_exposed(client: AsyncClient, admin_headers):
    await client.put("/api/admin/email-notify/config", json={
        "smtp_password": "my_secret_pwd",
    }, headers=admin_headers)

    resp = await client.get("/api/admin/email-notify/config", headers=admin_headers)
    data = resp.json()
    assert data["has_smtp_password"] is True
    assert "my_secret_pwd" not in str(data)


# ═══════════════════════════════════════════════════════════════
#  Email Logs
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_email_logs_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/email-notify/logs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_email_logs_with_records(client: AsyncClient, admin_headers, db_session):
    db_session.add(EmailLog(
        to_email="a@test.com",
        subject="测试主题",
        content="内容",
        status="success",
        is_test=True,
    ))
    db_session.add(EmailLog(
        to_email="b@test.com",
        subject="失败主题",
        content="内容",
        status="failed",
        error_message="SMTP超时",
        is_test=False,
    ))
    await db_session.commit()

    resp = await client.get("/api/admin/email-notify/logs", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_email_logs_filter_status(client: AsyncClient, admin_headers, db_session):
    db_session.add(EmailLog(to_email="a@t.com", subject="S1", status="success", is_test=False))
    db_session.add(EmailLog(to_email="b@t.com", subject="S2", status="failed", is_test=False))
    await db_session.commit()

    resp = await client.get(
        "/api/admin/email-notify/logs", params={"status": "failed"}, headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_email_logs_unauthorized(client: AsyncClient):
    resp = await client.get("/api/admin/email-notify/logs")
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
#  Email Test Send
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_email_test_no_config(client: AsyncClient, admin_headers):
    """Without SMTP config, test email should return 400."""
    resp = await client.post("/api/admin/email-notify/test", json={
        "to_email": "test@example.com",
        "subject": "测试",
    }, headers=admin_headers)
    assert resp.status_code == 400
    assert "配置不完整" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_email_test_with_config(client: AsyncClient, admin_headers, monkeypatch):
    """With complete config, test email tries to send (we mock smtplib)."""
    await client.put("/api/admin/email-notify/config", json={
        "smtp_host": "smtp.mock.com",
        "smtp_port": 465,
        "smtp_user": "sender@mock.com",
        "smtp_password": "pass123",
    }, headers=admin_headers)

    class MockSMTP_SSL:
        def __init__(self, *a, **kw):
            pass
        def login(self, *a):
            pass
        def sendmail(self, *a):
            pass
        def quit(self):
            pass

    monkeypatch.setattr("app.api.email_notify.smtplib.SMTP_SSL", MockSMTP_SSL)

    resp = await client.post("/api/admin/email-notify/test", json={
        "to_email": "recipient@test.com",
        "subject": "测试邮件",
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_email_test_unauthorized(client: AsyncClient):
    resp = await client.post("/api/admin/email-notify/test", json={
        "to_email": "x@x.com",
        "subject": "t",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_email_test_missing_required_fields(client: AsyncClient, admin_headers):
    resp = await client.post("/api/admin/email-notify/test", json={}, headers=admin_headers)
    assert resp.status_code == 422
