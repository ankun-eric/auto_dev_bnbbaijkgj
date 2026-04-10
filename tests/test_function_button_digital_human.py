"""
Function Button & Digital Human — Non-UI Automated Tests
Covers:
  - User-facing: function-buttons list, digital-human detail, voice-call lifecycle, VAD config
  - Admin CRUD: function-buttons, digital-humans, voice-service config
  - Permission / validation / 404 edge cases
"""
import uuid
import warnings

import pytest
import requests

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
TIMEOUT = 15
TEST_PHONE = "13800138000"
TEST_CODE = "123456"
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"


def _uid():
    return uuid.uuid4().hex[:6]


# ──────────────── Fixtures ────────────────


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.verify = False
    return s


@pytest.fixture(scope="module")
def user_token(session):
    """Obtain user token via SMS login."""
    r = session.post(
        f"{BASE_URL}/api/auth/sms-code",
        json={"phone": TEST_PHONE, "type": "login"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"Send SMS code failed: {r.status_code} {r.text}"
    r = session.post(
        f"{BASE_URL}/api/auth/sms-login",
        json={"phone": TEST_PHONE, "code": TEST_CODE},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"SMS login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="module")
def admin_token(session):
    """Obtain admin token via password login."""
    r = session.post(
        f"{BASE_URL}/api/admin/login",
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ══════════════════════════════════════════
#  TC-001: 用户端 — 功能按钮列表
# ══════════════════════════════════════════


class TestFunctionButtonList:
    def test_tc001_function_buttons_returns_list(self, session):
        """GET /api/chat/function-buttons returns 200 with a list."""
        r = session.get(
            f"{BASE_URL}/api/chat/function-buttons",
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_tc002_function_buttons_cache_consistency(self, session):
        """Two consecutive requests should return the same structure."""
        r1 = session.get(f"{BASE_URL}/api/chat/function-buttons", timeout=TIMEOUT)
        r2 = session.get(f"{BASE_URL}/api/chat/function-buttons", timeout=TIMEOUT)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert len(r1.json()) == len(r2.json())


# ══════════════════════════════════════════
#  TC-003~006: 管理端 — 功能按钮 CRUD
# ══════════════════════════════════════════


class TestAdminFunctionButtonCRUD:
    _created_id: int = 0

    def test_tc003_create_button(self, session, admin_headers):
        """POST /api/admin/function-buttons creates a new button."""
        tag = _uid()
        r = session.post(
            f"{BASE_URL}/api/admin/function-buttons",
            headers=admin_headers,
            json={
                "name": f"TestBtn_{tag}",
                "button_type": "ai_consult",
                "sort_weight": 99,
                "is_enabled": True,
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == f"TestBtn_{tag}"
        assert data["button_type"] == "ai_consult"
        assert "id" in data
        TestAdminFunctionButtonCRUD._created_id = data["id"]

    def test_tc004_list_buttons(self, session, admin_headers):
        """GET /api/admin/function-buttons returns paginated list containing the created button."""
        r = session.get(
            f"{BASE_URL}/api/admin/function-buttons",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "total" in data
        ids = [item["id"] for item in data["items"]]
        assert TestAdminFunctionButtonCRUD._created_id in ids

    def test_tc005_update_button(self, session, admin_headers):
        """PUT /api/admin/function-buttons/{id} updates the button."""
        btn_id = TestAdminFunctionButtonCRUD._created_id
        assert btn_id > 0, "No button created in tc003"
        r = session.put(
            f"{BASE_URL}/api/admin/function-buttons/{btn_id}",
            headers=admin_headers,
            json={"name": "UpdatedBtn", "sort_weight": 1},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "UpdatedBtn"
        assert data["sort_weight"] == 1

    def test_tc006_delete_button(self, session, admin_headers):
        """DELETE /api/admin/function-buttons/{id} deletes the button."""
        btn_id = TestAdminFunctionButtonCRUD._created_id
        assert btn_id > 0, "No button created in tc003"
        r = session.delete(
            f"{BASE_URL}/api/admin/function-buttons/{btn_id}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("message"), "Expected a success message"


# ══════════════════════════════════════════
#  TC-007~010: 管理端 — 数字人 CRUD
# ══════════════════════════════════════════


class TestAdminDigitalHumanCRUD:
    _created_id: int = 0

    def test_tc007_create_digital_human(self, session, admin_headers):
        """POST /api/admin/digital-humans creates a new digital human."""
        tag = _uid()
        r = session.post(
            f"{BASE_URL}/api/admin/digital-humans",
            headers=admin_headers,
            json={
                "name": f"TestDH_{tag}",
                "silent_video_url": "https://example.com/silent.mp4",
                "speaking_video_url": "https://example.com/speaking.mp4",
                "tts_voice_id": "voice_001",
                "description": "Automated test digital human",
                "is_enabled": True,
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == f"TestDH_{tag}"
        assert "id" in data
        TestAdminDigitalHumanCRUD._created_id = data["id"]

    def test_tc008_list_digital_humans(self, session, admin_headers):
        """GET /api/admin/digital-humans returns paginated list."""
        r = session.get(
            f"{BASE_URL}/api/admin/digital-humans",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "total" in data
        ids = [item["id"] for item in data["items"]]
        assert TestAdminDigitalHumanCRUD._created_id in ids

    def test_tc009_update_digital_human(self, session, admin_headers):
        """PUT /api/admin/digital-humans/{id} updates the digital human."""
        dh_id = TestAdminDigitalHumanCRUD._created_id
        assert dh_id > 0, "No digital human created in tc007"
        r = session.put(
            f"{BASE_URL}/api/admin/digital-humans/{dh_id}",
            headers=admin_headers,
            json={"name": "UpdatedDH", "description": "Updated by test"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "UpdatedDH"
        assert data["description"] == "Updated by test"

    def test_tc010_delete_digital_human(self, session, admin_headers):
        """DELETE /api/admin/digital-humans/{id} deletes the digital human."""
        dh_id = TestAdminDigitalHumanCRUD._created_id
        assert dh_id > 0, "No digital human created in tc007"
        r = session.delete(
            f"{BASE_URL}/api/admin/digital-humans/{dh_id}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("message"), "Expected a success message"


# ══════════════════════════════════════════
#  TC-011~013: 通话生命周期（start / message / end）
# ══════════════════════════════════════════


class TestVoiceCallLifecycle:
    _call_id: int = 0

    def test_tc011_start_voice_call(self, session, user_headers):
        """POST /api/chat/voice-call/start returns a call record with id."""
        r = session.post(
            f"{BASE_URL}/api/chat/voice-call/start",
            headers=user_headers,
            json={"digital_human_id": None, "chat_session_id": None},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data, "Response must contain call record id"
        assert "start_time" in data
        TestVoiceCallLifecycle._call_id = data["id"]

    def test_tc012_voice_call_message(self, session, user_headers):
        """POST /api/chat/voice-call/{id}/message returns AI reply."""
        call_id = TestVoiceCallLifecycle._call_id
        assert call_id > 0, "No call started in tc011"
        r = session.post(
            f"{BASE_URL}/api/chat/voice-call/{call_id}/message",
            headers=user_headers,
            json={"user_text": "你好，请问感冒了应该怎么办？"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ai_text" in data, "Response must contain ai_text"
        assert len(data["ai_text"]) > 0, "AI reply should not be empty"

    def test_tc013_end_voice_call(self, session, user_headers):
        """POST /api/chat/voice-call/{id}/end successfully ends the call."""
        call_id = TestVoiceCallLifecycle._call_id
        assert call_id > 0, "No call started in tc011"
        r = session.post(
            f"{BASE_URL}/api/chat/voice-call/{call_id}/end",
            headers=user_headers,
            json={
                "dialog_content": [
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好！有什么可以帮助您的？"},
                ]
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("end_time") is not None, "end_time should be set"


# ══════════════════════════════════════════
#  TC-014: VAD 配置
# ══════════════════════════════════════════


class TestVADConfig:
    def test_tc014_get_vad_config(self, session):
        """GET /api/chat/voice-service/vad-config returns a dict of configs."""
        r = session.get(
            f"{BASE_URL}/api/chat/voice-service/vad-config",
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"


# ══════════════════════════════════════════
#  TC-015~016: 管理端 — 语音服务配置
# ══════════════════════════════════════════


class TestAdminVoiceServiceConfig:
    def test_tc015_get_voice_config(self, session, admin_headers):
        """GET /api/admin/voice-service/config returns config items."""
        r = session.get(
            f"{BASE_URL}/api/admin/voice-service/config",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_tc016_update_voice_config(self, session, admin_headers):
        """PUT /api/admin/voice-service/config updates a config item."""
        list_r = session.get(
            f"{BASE_URL}/api/admin/voice-service/config",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert list_r.status_code == 200
        items = list_r.json().get("items", [])
        if not items:
            pytest.skip("No voice-service config items exist to update")

        target = items[0]
        original_value = target["config_value"]
        r = session.put(
            f"{BASE_URL}/api/admin/voice-service/config",
            headers=admin_headers,
            json={
                "config_key": target["config_key"],
                "config_value": original_value,
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["config_key"] == target["config_key"]

    def test_tc016b_test_voice_connection(self, session, admin_headers):
        """POST /api/admin/voice-service/test-connection returns ok status."""
        r = session.post(
            f"{BASE_URL}/api/admin/voice-service/test-connection",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "ok"


# ══════════════════════════════════════════
#  TC-017: 权限测试
# ══════════════════════════════════════════


class TestPermission:
    def test_tc017_user_cannot_access_admin_buttons(self, session, user_headers):
        """Non-admin user accessing admin endpoints should get 401 or 403."""
        endpoints = [
            ("GET", f"{BASE_URL}/api/admin/function-buttons"),
            ("POST", f"{BASE_URL}/api/admin/function-buttons"),
            ("GET", f"{BASE_URL}/api/admin/digital-humans"),
            ("POST", f"{BASE_URL}/api/admin/digital-humans"),
            ("GET", f"{BASE_URL}/api/admin/voice-service/config"),
        ]
        for method, url in endpoints:
            if method == "GET":
                r = session.get(url, headers=user_headers, timeout=TIMEOUT)
            else:
                r = session.post(url, headers=user_headers, json={}, timeout=TIMEOUT)
            assert r.status_code in (401, 403), (
                f"{method} {url} expected 401/403, got {r.status_code}"
            )

    def test_tc017b_no_token_admin_buttons(self, session):
        """No token at all should get 401."""
        r = session.get(
            f"{BASE_URL}/api/admin/function-buttons",
            timeout=TIMEOUT,
        )
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


# ══════════════════════════════════════════
#  TC-018: 参数校验测试
# ══════════════════════════════════════════


class TestParamValidation:
    def test_tc018_create_button_missing_required_fields(self, session, admin_headers):
        """POST /api/admin/function-buttons with missing required fields returns 422."""
        r = session.post(
            f"{BASE_URL}/api/admin/function-buttons",
            headers=admin_headers,
            json={"sort_weight": 1},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

    def test_tc018b_create_digital_human_missing_fields(self, session, admin_headers):
        """POST /api/admin/digital-humans with missing required fields returns 422."""
        r = session.post(
            f"{BASE_URL}/api/admin/digital-humans",
            headers=admin_headers,
            json={"description": "incomplete"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


# ══════════════════════════════════════════
#  TC-019: 不存在资源测试
# ══════════════════════════════════════════


class TestNotFound:
    def test_tc019_get_nonexistent_digital_human(self, session):
        """GET /api/chat/digital-human/999999 returns 404."""
        r = session.get(
            f"{BASE_URL}/api/chat/digital-human/999999",
            timeout=TIMEOUT,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_tc019b_delete_nonexistent_button(self, session, admin_headers):
        """DELETE /api/admin/function-buttons/999999 returns 404."""
        r = session.delete(
            f"{BASE_URL}/api/admin/function-buttons/999999",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_tc019c_delete_nonexistent_digital_human(self, session, admin_headers):
        """DELETE /api/admin/digital-humans/999999 returns 404."""
        r = session.delete(
            f"{BASE_URL}/api/admin/digital-humans/999999",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
