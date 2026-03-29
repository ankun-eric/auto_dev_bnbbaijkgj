from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import HealthProfile, SystemConfig, User, UserRole, VerificationCode


async def create_admin_headers(client: AsyncClient, db_session, phone: str = "13800050005"):
    admin_user = User(
        phone=phone,
        password_hash=get_password_hash("admin1234"),
        nickname="设置管理员",
        role=UserRole.admin,
    )
    db_session.add(admin_user)
    await db_session.commit()

    login_resp = await client.post("/api/admin/login", json={
        "phone": phone,
        "password": "admin1234",
    })
    assert login_resp.status_code == 200
    return {"Authorization": f"Bearer {login_resp.json()['token']}"}


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "phone": "13800001111",
        "password": "test1234",
        "nickname": "新用户",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["phone"] == "13800001111"
    assert data["user"]["nickname"] == "新用户"
    assert data["user"]["role"] == "user"
    assert data["user"]["status"] == "active"


@pytest.mark.asyncio
async def test_register_duplicate_phone(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13800002222",
        "password": "test1234",
        "nickname": "用户A",
    })
    response = await client.post("/api/auth/register", json={
        "phone": "13800002222",
        "password": "test5678",
        "nickname": "用户B",
    })
    assert response.status_code == 400
    assert "已注册" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_default_nickname(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "phone": "13800003333",
        "password": "test1234",
    })
    assert response.status_code == 200
    assert response.json()["user"]["nickname"] == "用户3333"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13800004444",
        "password": "mypassword",
    })
    response = await client.post("/api/auth/login", json={
        "phone": "13800004444",
        "password": "mypassword",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["phone"] == "13800004444"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "phone": "13800005555",
        "password": "correct",
    })
    response = await client.post("/api/auth/login", json={
        "phone": "13800005555",
        "password": "wrong",
    })
    assert response.status_code == 400
    assert "密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_phone(client: AsyncClient):
    response = await client.post("/api/auth/login", json={
        "phone": "19999999999",
        "password": "whatever",
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers):
    response = await client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "13900000001"
    assert data["nickname"] == "测试用户"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, auth_headers):
    response = await client.put("/api/auth/me", json={
        "nickname": "新昵称",
        "avatar": "https://example.com/avatar.png",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["nickname"] == "新昵称"
    assert data["avatar"] == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_update_profile_partial(client: AsyncClient, auth_headers):
    response = await client.put("/api/auth/me", json={
        "nickname": "只改昵称",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["nickname"] == "只改昵称"


@pytest.mark.asyncio
async def test_get_register_settings_defaults(client: AsyncClient):
    response = await client.get("/api/auth/register-settings")
    assert response.status_code == 200
    data = response.json()
    assert data["enable_self_registration"] is True
    assert data["wechat_register_mode"] == "authorize_member"
    assert data["douyin_register_mode"] == "authorize_member"
    assert data["register_page_layout"] == "vertical"
    assert data["show_profile_completion_prompt"] is True
    assert data["member_card_no_rule"] == "incremental"


@pytest.mark.asyncio
async def test_register_blocked_when_self_registration_disabled(client: AsyncClient, db_session):
    db_session.add(SystemConfig(
        config_key="register_enable_self_registration",
        config_value="False",
        config_type="register",
    ))
    await db_session.commit()

    response = await client.post("/api/auth/register", json={
        "phone": "13800006666",
        "password": "test1234",
        "nickname": "禁用注册",
    })
    assert response.status_code == 403
    assert "暂未开放自助注册" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sms_login_creates_member_card_no_incrementally(client: AsyncClient, latest_sms_code):
    first_register = await client.post("/api/auth/register", json={
        "phone": "13800007777",
        "password": "test1234",
        "nickname": "首位会员",
    })
    assert first_register.status_code == 200
    assert first_register.json()["user"]["member_card_no"] == "1"

    code_resp = await client.post("/api/auth/sms-code", json={
        "phone": "13800008888",
        "type": "login",
    })
    assert code_resp.status_code == 200
    assert code_resp.json().get("code") is None
    sms_code = await latest_sms_code("13800008888")

    login_resp = await client.post("/api/auth/sms-login", json={
        "phone": "13800008888",
        "code": sms_code,
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["is_new_user"] is True
    assert data["needs_profile_completion"] is True
    assert data["user"]["member_card_no"] == "2"


@pytest.mark.asyncio
async def test_register_settings_member_card_no_rule_random(client: AsyncClient, db_session):
    db_session.add(SystemConfig(
        config_key="register_member_card_no_rule",
        config_value="random",
        config_type="register",
    ))
    await db_session.commit()

    response = await client.post("/api/auth/register", json={
        "phone": "13800010001",
        "password": "test1234",
        "nickname": "随机卡号用户",
    })
    assert response.status_code == 200
    member_card_no = response.json()["user"]["member_card_no"]
    assert member_card_no is not None
    assert len(member_card_no) == 8
    assert member_card_no.isdigit()


@pytest.mark.asyncio
async def test_sms_login_blocked_when_registration_disabled_new_user(client: AsyncClient, db_session):
    db_session.add(SystemConfig(
        config_key="register_enable_self_registration",
        config_value="False",
        config_type="register",
    ))
    await db_session.commit()

    code_resp = await client.post("/api/auth/sms-code", json={
        "phone": "13800020002",
        "type": "login",
    })
    assert code_resp.status_code == 403

    # Even if we bypass sms-code check, sms-login should also block
    # Try with a manually inserted code to confirm sms-login also rejects
    vc = VerificationCode(
        phone="13800020002",
        code="123456",
        type="login",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(vc)
    await db_session.commit()

    login_resp = await client.post("/api/auth/sms-login", json={
        "phone": "13800020002",
        "code": "123456",
    })
    assert login_resp.status_code == 403


@pytest.mark.asyncio
async def test_sms_code_register_type_blocked_new_user_when_self_registration_disabled(
    client: AsyncClient, db_session
):
    db_session.add(
        SystemConfig(
            config_key="register_enable_self_registration",
            config_value="false",
            config_type="register",
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/api/auth/sms-code",
        json={"phone": "13800021021", "type": "register"},
    )
    assert resp.status_code == 403
    assert "暂未开放自助注册" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_sms_login_allowed_when_registration_disabled_existing_user(
    client: AsyncClient, db_session, latest_sms_code
):
    reg_resp = await client.post("/api/auth/register", json={
        "phone": "13800030003",
        "password": "test1234",
        "nickname": "已有用户",
    })
    assert reg_resp.status_code == 200

    db_session.add(SystemConfig(
        config_key="register_enable_self_registration",
        config_value="False",
        config_type="register",
    ))
    await db_session.commit()

    code_resp = await client.post("/api/auth/sms-code", json={
        "phone": "13800030003",
        "type": "login",
    })
    assert code_resp.status_code == 200
    sms_code = await latest_sms_code("13800030003")

    login_resp = await client.post("/api/auth/sms-login", json={
        "phone": "13800030003",
        "code": sms_code,
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["is_new_user"] is False
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_response_includes_needs_profile_completion(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "phone": "13800040004",
        "password": "test1234",
        "nickname": "新注册用户",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["needs_profile_completion"] is True
    assert data["is_new_user"] is True


@pytest.mark.asyncio
async def test_register_needs_profile_completion_false_when_prompt_disabled(
    client: AsyncClient, db_session
):
    db_session.add(
        SystemConfig(
            config_key="register_show_profile_completion_prompt",
            config_value="false",
            config_type="register",
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/auth/register",
        json={
            "phone": "13800041041",
            "password": "test1234",
            "nickname": "关闭资料提示",
        },
    )
    assert response.status_code == 200
    assert response.json()["needs_profile_completion"] is False


@pytest.mark.asyncio
async def test_password_login_needs_profile_completion(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "phone": "13800042042",
            "password": "test1234",
            "nickname": "密码登录资料",
        },
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"phone": "13800042042", "password": "test1234"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["needs_profile_completion"] is True


@pytest.mark.asyncio
async def test_password_login_skips_profile_completion_when_prompt_disabled(
    client: AsyncClient, db_session
):
    await client.post(
        "/api/auth/register",
        json={
            "phone": "13800042142",
            "password": "test1234",
            "nickname": "关闭登录提醒",
        },
    )
    db_session.add(
        SystemConfig(
            config_key="register_show_profile_completion_prompt",
            config_value="false",
            config_type="register",
        )
    )
    await db_session.commit()

    login_resp = await client.post(
        "/api/auth/login",
        json={"phone": "13800042142", "password": "test1234"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["needs_profile_completion"] is False


@pytest.mark.asyncio
async def test_sms_login_existing_user_needs_profile_completion_reflects_health_profile(
    client: AsyncClient, db_session, latest_sms_code
):
    reg = await client.post(
        "/api/auth/register",
        json={
            "phone": "13800043043",
            "password": "test1234",
            "nickname": "短信老用户",
        },
    )
    assert reg.status_code == 200
    user_id = reg.json()["user"]["id"]

    code_resp = await client.post(
        "/api/auth/sms-code",
        json={"phone": "13800043043", "type": "login"},
    )
    assert code_resp.status_code == 200
    sms_code = await latest_sms_code("13800043043")
    first_login = await client.post(
        "/api/auth/sms-login",
        json={"phone": "13800043043", "code": sms_code},
    )
    assert first_login.status_code == 200
    assert first_login.json()["is_new_user"] is False
    assert first_login.json()["needs_profile_completion"] is True

    db_session.add(
        HealthProfile(
            user_id=user_id,
            gender="male",
            birthday=date(1990, 1, 1),
            height=170.0,
            weight=70.0,
        )
    )
    await db_session.commit()

    # Reuse same verification code (sms-login does not consume the row; avoid second sms-code within 60s).
    second_login = await client.post(
        "/api/auth/sms-login",
        json={"phone": "13800043043", "code": sms_code},
    )
    assert second_login.status_code == 200
    assert second_login.json()["needs_profile_completion"] is False


@pytest.mark.asyncio
async def test_register_settings_illegal_enum_normalized_on_public_get(client: AsyncClient, db_session):
    db_session.add(
        SystemConfig(
            config_key="register_member_card_no_rule",
            config_value="not_a_valid_rule",
            config_type="register",
        )
    )
    db_session.add(
        SystemConfig(
            config_key="register_wechat_register_mode",
            config_value="invalid_mode",
            config_type="register",
        )
    )
    await db_session.commit()

    resp = await client.get("/api/auth/register-settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["member_card_no_rule"] == "incremental"
    assert data["wechat_register_mode"] == "authorize_member"


@pytest.mark.asyncio
async def test_admin_save_register_settings_normalizes_illegal_enums(client: AsyncClient, db_session):
    admin_user = User(
        phone="13800044044",
        password_hash=get_password_hash("admin1234"),
        nickname="枚举管理员",
        role=UserRole.admin,
    )
    db_session.add(admin_user)
    await db_session.commit()

    login_resp = await client.post(
        "/api/admin/login",
        json={"phone": "13800044044", "password": "admin1234"},
    )
    assert login_resp.status_code == 200
    headers = {"Authorization": f"Bearer {login_resp.json()['token']}"}

    update_resp = await client.post(
        "/api/admin/settings/register",
        json={
            "register_page_layout": "diagonal",
            "douyin_register_mode": "unknown",
            "member_card_no_rule": "uuid_v4",
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    settings = update_resp.json()["settings"]
    assert settings["register_page_layout"] == "vertical"
    assert settings["douyin_register_mode"] == "authorize_member"
    assert settings["member_card_no_rule"] == "incremental"

    read_resp = await client.get("/api/admin/settings/register", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["register_page_layout"] == "vertical"


@pytest.mark.asyncio
async def test_register_settings_update_and_read(client: AsyncClient, db_session):
    admin_user = User(
        phone="13800050005",
        password_hash=get_password_hash("admin1234"),
        nickname="设置管理员",
        role=UserRole.admin,
    )
    db_session.add(admin_user)
    await db_session.commit()

    login_resp = await client.post("/api/admin/login", json={
        "phone": "13800050005",
        "password": "admin1234",
    })
    assert login_resp.status_code == 200
    admin_token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    update_resp = await client.post("/api/admin/settings/register", json={
        "enable_self_registration": False,
        "member_card_no_rule": "random",
        "register_page_layout": "horizontal",
    }, headers=headers)
    assert update_resp.status_code == 200

    read_resp = await client.get("/api/admin/settings/register", headers=headers)
    assert read_resp.status_code == 200
    settings = read_resp.json()
    assert settings["enable_self_registration"] is False
    assert settings["member_card_no_rule"] == "random"
    assert settings["register_page_layout"] == "horizontal"


@pytest.mark.asyncio
async def test_register_settings_partial_update_preserves_existing_values(
    client: AsyncClient, db_session
):
    headers = await create_admin_headers(client, db_session, phone="13800051005")

    first_update = await client.post(
        "/api/admin/settings/register",
        json={
            "member_card_no_rule": "random",
            "register_page_layout": "horizontal",
            "wechat_register_mode": "fill_profile",
        },
        headers=headers,
    )
    assert first_update.status_code == 200

    second_update = await client.post(
        "/api/admin/settings/register",
        json={"enable_self_registration": False},
        headers=headers,
    )
    assert second_update.status_code == 200

    read_resp = await client.get("/api/admin/settings/register", headers=headers)
    assert read_resp.status_code == 200
    settings = read_resp.json()
    assert settings["enable_self_registration"] is False
    assert settings["member_card_no_rule"] == "random"
    assert settings["register_page_layout"] == "horizontal"
    assert settings["wechat_register_mode"] == "fill_profile"


@pytest.mark.asyncio
async def test_register_settings_requires_admin_role(client: AsyncClient, auth_headers):
    response = await client.get("/api/admin/settings/register", headers=auth_headers)
    assert response.status_code == 403
    assert "权限不足" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sms_code_rate_limit_60s(client: AsyncClient, db_session):
    first = await client.post("/api/auth/sms-code", json={
        "phone": "13800099001",
        "type": "login",
    })
    assert first.status_code == 200

    second = await client.post("/api/auth/sms-code", json={
        "phone": "13800099001",
        "type": "login",
    })
    assert second.status_code == 429
    assert "频繁" in second.json()["detail"]


@pytest.mark.asyncio
async def test_sms_code_rate_limit_different_phones_ok(client: AsyncClient):
    first = await client.post("/api/auth/sms-code", json={
        "phone": "13800099002",
        "type": "login",
    })
    assert first.status_code == 200

    second = await client.post("/api/auth/sms-code", json={
        "phone": "13800099003",
        "type": "login",
    })
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_sms_code_response_no_code_field(client: AsyncClient):
    resp = await client.post("/api/auth/sms-code", json={
        "phone": "13800099004",
        "type": "login",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "验证码已发送"
    assert "code" not in data


@pytest.mark.asyncio
async def test_sms_login_wrong_code(client: AsyncClient, latest_sms_code):
    await client.post("/api/auth/sms-code", json={
        "phone": "13800099005",
        "type": "login",
    })
    login_resp = await client.post("/api/auth/sms-login", json={
        "phone": "13800099005",
        "code": "000000",
    })
    assert login_resp.status_code == 400
    assert "无效" in login_resp.json()["detail"] or "过期" in login_resp.json()["detail"]


@pytest.mark.asyncio
async def test_sms_login_auto_register_new_user(client: AsyncClient, latest_sms_code):
    await client.post("/api/auth/sms-code", json={
        "phone": "13800099006",
        "type": "login",
    })
    code = await latest_sms_code("13800099006")
    login_resp = await client.post("/api/auth/sms-login", json={
        "phone": "13800099006",
        "code": code,
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["is_new_user"] is True
    assert "access_token" in data
    assert data["user"]["phone"] == "13800099006"


@pytest.mark.asyncio
async def test_sms_login_existing_user(client: AsyncClient, latest_sms_code):
    await client.post("/api/auth/register", json={
        "phone": "13800099007",
        "password": "test1234",
        "nickname": "已有用户",
    })
    await client.post("/api/auth/sms-code", json={
        "phone": "13800099007",
        "type": "login",
    })
    code = await latest_sms_code("13800099007")
    login_resp = await client.post("/api/auth/sms-login", json={
        "phone": "13800099007",
        "code": code,
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["is_new_user"] is False
    assert "access_token" in data
