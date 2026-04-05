"""
消息管理模块自动化测试 — 短信 / 微信推送 / 邮件通知
针对已部署服务器: https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857
"""

import time
import httpx
import pytest

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"
TIMEOUT = 20


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, verify=False) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client: httpx.Client) -> str:
    resp = client.post("/api/admin/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="session")
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


# ═══════════════════════════════════════════════
#  1. 短信配置
# ═══════════════════════════════════════════════

class TestSmsConfig:

    def test_get_config(self, client, auth_headers):
        resp = client.get("/api/admin/sms/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tencent" in data, "响应缺少 tencent 区块"
        assert "aliyun" in data, "响应缺少 aliyun 区块"

    def test_save_tencent_config(self, client, auth_headers):
        resp = client.put("/api/admin/sms/config", headers=auth_headers, json={
            "provider": "tencent",
            "secret_id": "test_secret_id",
            "secret_key": "test_secret_key",
            "sdk_app_id": "1400000001",
            "sign_name": "测试签名",
            "template_id": "100001",
            "app_key": "test_app_key",
            "is_active": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("secret_id") == "test_secret_id"
        assert data.get("is_active") is True

    def test_save_aliyun_config(self, client, auth_headers):
        resp = client.put("/api/admin/sms/config", headers=auth_headers, json={
            "provider": "aliyun",
            "access_key_id": "test_ak_id",
            "access_key_secret": "test_ak_secret",
            "sign_name": "阿里测试签名",
            "template_id": "SMS_200001",
            "is_active": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("access_key_id") == "test_ak_id"
        assert data.get("is_active") is True

    def test_mutual_exclusion(self, client, auth_headers):
        """启用阿里云后腾讯云应自动禁用"""
        resp = client.get("/api/admin/sms/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["aliyun"]["is_active"] is True
        assert data["tencent"]["is_active"] is False, "互斥逻辑失败：启用阿里云后腾讯云仍为 active"

    def test_switch_back_to_tencent(self, client, auth_headers):
        """切回腾讯云，阿里云应被禁用"""
        resp = client.put("/api/admin/sms/config", headers=auth_headers, json={
            "provider": "tencent",
            "is_active": True,
        })
        assert resp.status_code == 200
        cfg = client.get("/api/admin/sms/config", headers=auth_headers).json()
        assert cfg["tencent"]["is_active"] is True
        assert cfg["aliyun"]["is_active"] is False

    def test_invalid_provider(self, client, auth_headers):
        resp = client.put("/api/admin/sms/config", headers=auth_headers, json={
            "provider": "invalid_provider",
        })
        assert resp.status_code in (400, 422)


# ═══════════════════════════════════════════════
#  2. 短信模板 CRUD
# ═══════════════════════════════════════════════

class TestSmsTemplates:

    created_ids: list[int] = []

    def test_create_template_tencent(self, client, auth_headers):
        resp = client.post("/api/admin/sms/templates", headers=auth_headers, json={
            "name": "测试模板_腾讯",
            "provider": "tencent",
            "template_id": "TPL_TC_001",
            "content": "您的验证码是{code}",
            "sign_name": "测试签名",
            "scene": "login",
            "variables": "code",
            "status": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试模板_腾讯"
        assert data["provider"] == "tencent"
        self.__class__.created_ids.append(data["id"])

    def test_create_template_aliyun(self, client, auth_headers):
        resp = client.post("/api/admin/sms/templates", headers=auth_headers, json={
            "name": "测试模板_阿里",
            "provider": "aliyun",
            "template_id": "TPL_ALI_001",
            "content": "您的验证码是${code}",
            "sign_name": "阿里签名",
            "scene": "register",
            "variables": "code",
            "status": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "aliyun"
        self.__class__.created_ids.append(data["id"])

    def test_list_templates(self, client, auth_headers):
        resp = client.get("/api/admin/sms/templates", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_list_templates_pagination(self, client, auth_headers):
        resp = client.get("/api/admin/sms/templates", headers=auth_headers, params={"page": 1, "page_size": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 1

    def test_filter_by_provider(self, client, auth_headers):
        resp = client.get("/api/admin/sms/templates", headers=auth_headers, params={"provider": "tencent"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["provider"] == "tencent"

    def test_filter_by_scene(self, client, auth_headers):
        resp = client.get("/api/admin/sms/templates", headers=auth_headers, params={"scene": "login"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["scene"] == "login"

    def test_search_by_name(self, client, auth_headers):
        resp = client.get("/api/admin/sms/templates", headers=auth_headers, params={"name": "腾讯"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert "腾讯" in item["name"]

    def test_update_template(self, client, auth_headers):
        if not self.created_ids:
            pytest.skip("No template created")
        tid = self.created_ids[0]
        resp = client.put(f"/api/admin/sms/templates/{tid}", headers=auth_headers, json={
            "name": "测试模板_腾讯_已修改",
            "content": "您的验证码是{code}，5分钟内有效",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "测试模板_腾讯_已修改"

    def test_update_nonexistent(self, client, auth_headers):
        resp = client.put("/api/admin/sms/templates/999999", headers=auth_headers, json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_template(self, client, auth_headers):
        if len(self.created_ids) < 2:
            pytest.skip("Not enough templates")
        tid = self.created_ids.pop()
        resp = client.delete(f"/api/admin/sms/templates/{tid}", headers=auth_headers)
        assert resp.status_code == 200

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete("/api/admin/sms/templates/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_cleanup(self, client, auth_headers):
        for tid in self.created_ids:
            client.delete(f"/api/admin/sms/templates/{tid}", headers=auth_headers)
        self.__class__.created_ids.clear()


# ═══════════════════════════════════════════════
#  3. 短信发送记录
# ═══════════════════════════════════════════════

class TestSmsLogs:

    def test_get_logs(self, client, auth_headers):
        resp = client.get("/api/admin/sms/logs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_logs_pagination(self, client, auth_headers):
        resp = client.get("/api/admin/sms/logs", headers=auth_headers, params={"page": 1, "page_size": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_filter_by_provider(self, client, auth_headers):
        resp = client.get("/api/admin/sms/logs", headers=auth_headers, params={"provider": "tencent"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["provider"] == "tencent"

    def test_filter_by_status(self, client, auth_headers):
        resp = client.get("/api/admin/sms/logs", headers=auth_headers, params={"status": "success"})
        assert resp.status_code == 200

    def test_search_by_phone(self, client, auth_headers):
        resp = client.get("/api/admin/sms/logs", headers=auth_headers, params={"phone": "138"})
        assert resp.status_code == 200


# ═══════════════════════════════════════════════
#  4. 短信测试发送
# ═══════════════════════════════════════════════

class TestSmsSend:

    def test_send_tencent(self, client, auth_headers):
        resp = client.post("/api/admin/sms/test", headers=auth_headers, json={
            "phone": "13800000001",
            "provider": "tencent",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data or "message" in data

    def test_send_aliyun(self, client, auth_headers):
        resp = client.post("/api/admin/sms/test", headers=auth_headers, json={
            "phone": "13800000001",
            "provider": "aliyun",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data or "message" in data

    def test_send_missing_phone(self, client, auth_headers):
        resp = client.post("/api/admin/sms/test", headers=auth_headers, json={
            "provider": "tencent",
        })
        assert resp.status_code == 422


# ═══════════════════════════════════════════════
#  5. 微信推送配置
# ═══════════════════════════════════════════════

class TestWechatPushConfig:

    def test_get_config(self, client, auth_headers):
        resp = client.get("/api/admin/wechat-push/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "enable_wechat_push" in data
        assert "wechat_app_id" in data
        assert "has_wechat_app_secret" in data

    def test_save_config(self, client, auth_headers):
        resp = client.put("/api/admin/wechat-push/config", headers=auth_headers, json={
            "enable_wechat_push": True,
            "wechat_app_id": "wx_test_app_id",
            "wechat_app_secret": "wx_test_app_secret",
            "order_notify_template": "TPL_ORDER_001",
            "service_notify_template": "TPL_SVC_001",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["enable_wechat_push"] is True
        assert data["wechat_app_id"] == "wx_test_app_id"
        assert data["has_wechat_app_secret"] is True
        assert data["order_notify_template"] == "TPL_ORDER_001"

    def test_disable_wechat_push(self, client, auth_headers):
        resp = client.put("/api/admin/wechat-push/config", headers=auth_headers, json={
            "enable_wechat_push": False,
        })
        assert resp.status_code == 200
        assert resp.json()["enable_wechat_push"] is False

    def test_partial_update(self, client, auth_headers):
        resp = client.put("/api/admin/wechat-push/config", headers=auth_headers, json={
            "order_notify_template": "TPL_ORDER_002",
        })
        assert resp.status_code == 200
        assert resp.json()["order_notify_template"] == "TPL_ORDER_002"


# ═══════════════════════════════════════════════
#  6. 邮件配置
# ═══════════════════════════════════════════════

class TestEmailConfig:

    def test_get_config(self, client, auth_headers):
        resp = client.get("/api/admin/email-notify/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "enable_email_notify" in data
        assert "smtp_host" in data
        assert "smtp_port" in data
        assert "smtp_user" in data
        assert "has_smtp_password" in data

    def test_save_config(self, client, auth_headers):
        resp = client.put("/api/admin/email-notify/config", headers=auth_headers, json={
            "enable_email_notify": True,
            "smtp_host": "smtp.test.com",
            "smtp_port": 465,
            "smtp_user": "test@test.com",
            "smtp_password": "test_password_123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["enable_email_notify"] is True
        assert data["smtp_host"] == "smtp.test.com"
        assert data["smtp_port"] == 465
        assert data["smtp_user"] == "test@test.com"
        assert data["has_smtp_password"] is True

    def test_partial_update(self, client, auth_headers):
        resp = client.put("/api/admin/email-notify/config", headers=auth_headers, json={
            "smtp_port": 587,
        })
        assert resp.status_code == 200
        assert resp.json()["smtp_port"] == 587

    def test_disable_email(self, client, auth_headers):
        resp = client.put("/api/admin/email-notify/config", headers=auth_headers, json={
            "enable_email_notify": False,
        })
        assert resp.status_code == 200
        assert resp.json()["enable_email_notify"] is False


# ═══════════════════════════════════════════════
#  7. 邮件发送记录
# ═══════════════════════════════════════════════

class TestEmailLogs:

    def test_get_logs(self, client, auth_headers):
        resp = client.get("/api/admin/email-notify/logs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_logs_pagination(self, client, auth_headers):
        resp = client.get("/api/admin/email-notify/logs", headers=auth_headers, params={"page": 1, "page_size": 5})
        assert resp.status_code == 200

    def test_filter_by_status(self, client, auth_headers):
        resp = client.get("/api/admin/email-notify/logs", headers=auth_headers, params={"status": "success"})
        assert resp.status_code == 200

    def test_filter_by_email(self, client, auth_headers):
        resp = client.get("/api/admin/email-notify/logs", headers=auth_headers, params={"to_email": "test"})
        assert resp.status_code == 200


# ═══════════════════════════════════════════════
#  8. 邮件测试发送
# ═══════════════════════════════════════════════

class TestEmailSend:

    def test_send_test_email(self, client, auth_headers):
        resp = client.post("/api/admin/email-notify/test", headers=auth_headers, json={
            "to_email": "testrecipient@example.com",
            "subject": "自动化测试邮件",
            "content": "<p>这是自动化测试邮件</p>",
        })
        # SMTP 未真实配置时可能返回 400（配置不完整）或 200（发送失败但 API 正常）
        assert resp.status_code in (200, 400)
        data = resp.json()
        assert "success" in data or "detail" in data

    def test_send_missing_fields(self, client, auth_headers):
        resp = client.post("/api/admin/email-notify/test", headers=auth_headers, json={
            "to_email": "test@example.com",
        })
        assert resp.status_code == 422


# ═══════════════════════════════════════════════
#  9. 权限控制 — 未登录
# ═══════════════════════════════════════════════

class TestAuthRequired:

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/admin/sms/config"),
        ("PUT", "/api/admin/sms/config"),
        ("GET", "/api/admin/sms/templates"),
        ("POST", "/api/admin/sms/templates"),
        ("GET", "/api/admin/sms/logs"),
        ("POST", "/api/admin/sms/test"),
        ("GET", "/api/admin/wechat-push/config"),
        ("PUT", "/api/admin/wechat-push/config"),
        ("GET", "/api/admin/email-notify/config"),
        ("PUT", "/api/admin/email-notify/config"),
        ("GET", "/api/admin/email-notify/logs"),
        ("POST", "/api/admin/email-notify/test"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_no_token_returns_401(self, client, method, path):
        if method == "GET":
            resp = client.get(path)
        elif method == "PUT":
            resp = client.put(path, json={})
        else:
            resp = client.post(path, json={})
        assert resp.status_code in (401, 403), f"{method} {path} returned {resp.status_code} without auth"


# ═══════════════════════════════════════════════
# 10. 废弃接口
# ═══════════════════════════════════════════════

class TestDeprecatedPushEndpoint:

    def test_push_settings_deprecated(self, client, auth_headers):
        resp = client.post("/api/admin/settings/push", headers=auth_headers, json={})
        assert resp.status_code == 410, f"Expected 410 Gone, got {resp.status_code}"
        data = resp.json()
        detail = data.get("detail", "")
        assert "废弃" in detail or "sms" in detail.lower() or "wechat" in detail.lower()

    def test_push_settings_no_auth(self, client):
        resp = client.post("/api/admin/settings/push", json={})
        assert resp.status_code in (401, 403, 410)
