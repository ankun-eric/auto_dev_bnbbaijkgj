import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import (
    AiDisclaimerConfig,
    AiPromptConfig,
    AiSensitiveWord,
    User,
    UserRole,
)


async def _create_admin(db_session, phone="13800060001"):
    user = User(
        phone=phone,
        password_hash=get_password_hash("admin123"),
        nickname="AI中心管理员",
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _admin_login(client: AsyncClient, phone="13800060001"):
    resp = await client.post("/api/admin/login", json={
        "phone": phone,
        "password": "admin123",
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def _seed_sensitive_word(db_session, word="暴力", replacement="***"):
    sw = AiSensitiveWord(sensitive_word=word, replacement_word=replacement)
    db_session.add(sw)
    await db_session.commit()
    await db_session.refresh(sw)
    return sw


async def _seed_prompt(db_session, chat_type="health_qa", display_name="健康问答", prompt="你是健康助手"):
    p = AiPromptConfig(chat_type=chat_type, display_name=display_name, system_prompt=prompt)
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


async def _seed_disclaimer(db_session, chat_type="health_qa", display_name="健康问答", text="仅供参考", enabled=True):
    d = AiDisclaimerConfig(
        chat_type=chat_type,
        display_name=display_name,
        disclaimer_text=text,
        is_enabled=enabled,
    )
    db_session.add(d)
    await db_session.commit()
    await db_session.refresh(d)
    return d


# ────────────────────────── 敏感词管理测试 ──────────────────────────


@pytest.mark.asyncio
async def test_tc001_admin_login(client: AsyncClient, db_session):
    """TC-001: 管理员登录获取token"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Bearer ")


@pytest.mark.asyncio
async def test_tc002_list_sensitive_words(client: AsyncClient, db_session):
    """TC-002: 获取敏感词列表（成功）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_sensitive_word(db_session, "暴力", "***")
    await _seed_sensitive_word(db_session, "赌博", "***")

    resp = await client.get(
        "/api/admin/ai-center/sensitive-words",
        headers=headers,
        params={"page": 1, "page_size": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_tc003_create_sensitive_word(client: AsyncClient, db_session):
    """TC-003: 新增敏感词（成功）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)

    resp = await client.post(
        "/api/admin/ai-center/sensitive-words",
        headers=headers,
        json={"sensitive_word": "脏话", "replacement_word": "**"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sensitive_word"] == "脏话"
    assert data["replacement_word"] == "**"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_tc004_create_sensitive_word_missing_fields(client: AsyncClient, db_session):
    """TC-004: 新增敏感词 - 参数校验（缺少必填字段返回422）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)

    resp = await client.post(
        "/api/admin/ai-center/sensitive-words",
        headers=headers,
        json={"sensitive_word": "测试"},
    )
    assert resp.status_code == 422

    resp2 = await client.post(
        "/api/admin/ai-center/sensitive-words",
        headers=headers,
        json={},
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_tc005_update_sensitive_word(client: AsyncClient, db_session):
    """TC-005: 编辑敏感词（成功）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    sw = await _seed_sensitive_word(db_session, "旧词", "旧替换")

    resp = await client.put(
        f"/api/admin/ai-center/sensitive-words/{sw.id}",
        headers=headers,
        json={"sensitive_word": "新词", "replacement_word": "新替换"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sensitive_word"] == "新词"
    assert data["replacement_word"] == "新替换"
    assert data["id"] == sw.id


@pytest.mark.asyncio
async def test_tc006_update_nonexistent_sensitive_word(client: AsyncClient, db_session):
    """TC-006: 编辑不存在的敏感词（404）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)

    resp = await client.put(
        "/api/admin/ai-center/sensitive-words/99999",
        headers=headers,
        json={"sensitive_word": "不存在"},
    )
    assert resp.status_code == 404
    assert "不存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tc007_delete_sensitive_word(client: AsyncClient, db_session):
    """TC-007: 删除敏感词（成功）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    sw = await _seed_sensitive_word(db_session, "待删除", "xxx")

    resp = await client.delete(
        f"/api/admin/ai-center/sensitive-words/{sw.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert "删除成功" in resp.json()["message"]

    verify = await client.get(
        "/api/admin/ai-center/sensitive-words",
        headers=headers,
        params={"page": 1, "page_size": 100},
    )
    ids = [item["id"] for item in verify.json()["items"]]
    assert sw.id not in ids


@pytest.mark.asyncio
async def test_tc008_delete_nonexistent_sensitive_word(client: AsyncClient, db_session):
    """TC-008: 删除不存在的敏感词（404）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)

    resp = await client.delete(
        "/api/admin/ai-center/sensitive-words/99999",
        headers=headers,
    )
    assert resp.status_code == 404
    assert "不存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tc009_search_sensitive_words_by_keyword(client: AsyncClient, db_session):
    """TC-009: 按关键字搜索敏感词"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_sensitive_word(db_session, "暴力内容", "***")
    await _seed_sensitive_word(db_session, "赌博网站", "***")
    await _seed_sensitive_word(db_session, "色情信息", "***")

    resp = await client.get(
        "/api/admin/ai-center/sensitive-words",
        headers=headers,
        params={"keyword": "暴力", "page": 1, "page_size": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert "暴力" in item["sensitive_word"] or "暴力" in item["replacement_word"]


@pytest.mark.asyncio
async def test_tc010_non_admin_access_sensitive_words(client: AsyncClient):
    """TC-010: 非管理员访问敏感词接口（401/403）"""
    resp_no_auth = await client.get("/api/admin/ai-center/sensitive-words")
    assert resp_no_auth.status_code in (401, 403)

    await client.post("/api/auth/register", json={
        "phone": "13900060001",
        "password": "user123",
        "nickname": "普通用户",
    })
    login_resp = await client.post("/api/auth/login", json={
        "phone": "13900060001",
        "password": "user123",
    })
    user_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp_user = await client.get(
        "/api/admin/ai-center/sensitive-words",
        headers=user_headers,
    )
    assert resp_user.status_code in (401, 403)


# ────────────────────────── 提示词配置测试 ──────────────────────────


@pytest.mark.asyncio
async def test_tc011_list_prompt_configs(client: AsyncClient, db_session):
    """TC-011: 获取所有提示词配置"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_prompt(db_session, "health_qa", "健康问答", "你是健康顾问")
    await _seed_prompt(db_session, "tcm_qa", "中医问答", "你是中医助手")

    resp = await client.get("/api/admin/ai-center/prompts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_tc012_get_prompt_by_type(client: AsyncClient, db_session):
    """TC-012: 获取指定类型提示词（health_qa）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_prompt(db_session, "health_qa", "健康问答", "你是一个专业的健康顾问")

    resp = await client.get("/api/admin/ai-center/prompts/health_qa", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["chat_type"] == "health_qa"
    assert data["display_name"] == "健康问答"
    assert data["system_prompt"] == "你是一个专业的健康顾问"
    assert "id" in data


@pytest.mark.asyncio
async def test_tc013_update_prompt_config(client: AsyncClient, db_session):
    """TC-013: 更新指定类型提示词（成功）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_prompt(db_session, "health_qa", "健康问答", "旧提示词")

    resp = await client.put(
        "/api/admin/ai-center/prompts/health_qa",
        headers=headers,
        json={"system_prompt": "你是一个全新的健康助手，请用简洁的语言回答"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["system_prompt"] == "你是一个全新的健康助手，请用简洁的语言回答"
    assert data["chat_type"] == "health_qa"

    verify = await client.get("/api/admin/ai-center/prompts/health_qa", headers=headers)
    assert verify.json()["system_prompt"] == "你是一个全新的健康助手，请用简洁的语言回答"


@pytest.mark.asyncio
async def test_tc014_get_nonexistent_prompt_type(client: AsyncClient, db_session):
    """TC-014: 获取不存在的类型提示词（404）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)

    resp = await client.get("/api/admin/ai-center/prompts/nonexistent_type", headers=headers)
    assert resp.status_code == 404
    assert "不存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tc015_non_admin_access_prompts(client: AsyncClient):
    """TC-015: 非管理员访问提示词接口（401/403）"""
    resp_no_auth = await client.get("/api/admin/ai-center/prompts")
    assert resp_no_auth.status_code in (401, 403)

    await client.post("/api/auth/register", json={
        "phone": "13900060002",
        "password": "user123",
        "nickname": "普通用户2",
    })
    login_resp = await client.post("/api/auth/login", json={
        "phone": "13900060002",
        "password": "user123",
    })
    user_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp_list = await client.get("/api/admin/ai-center/prompts", headers=user_headers)
    assert resp_list.status_code in (401, 403)

    resp_detail = await client.get("/api/admin/ai-center/prompts/health_qa", headers=user_headers)
    assert resp_detail.status_code in (401, 403, 404)


# ────────────────────────── 免责提示配置测试 ──────────────────────────


@pytest.mark.asyncio
async def test_tc016_list_disclaimer_configs(client: AsyncClient, db_session):
    """TC-016: 获取所有免责提示配置"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_disclaimer(db_session, "health_qa", "健康问答", "本回答仅供参考", True)
    await _seed_disclaimer(db_session, "tcm_qa", "中医问答", "请遵医嘱", True)

    resp = await client.get("/api/admin/ai-center/disclaimers", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_tc017_get_disclaimer_by_type(client: AsyncClient, db_session):
    """TC-017: 获取指定类型免责提示（health_qa）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_disclaimer(db_session, "health_qa", "健康问答", "本回答仅供参考，不构成医疗建议", True)

    resp = await client.get("/api/admin/ai-center/disclaimers/health_qa", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["chat_type"] == "health_qa"
    assert data["display_name"] == "健康问答"
    assert data["disclaimer_text"] == "本回答仅供参考，不构成医疗建议"
    assert data["is_enabled"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_tc018_update_disclaimer_text(client: AsyncClient, db_session):
    """TC-018: 更新免责提示文案（成功）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_disclaimer(db_session, "health_qa", "健康问答", "旧免责文案", True)

    resp = await client.put(
        "/api/admin/ai-center/disclaimers/health_qa",
        headers=headers,
        json={"disclaimer_text": "新免责文案：本内容由AI生成，仅供参考"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["disclaimer_text"] == "新免责文案：本内容由AI生成，仅供参考"
    assert data["chat_type"] == "health_qa"

    verify = await client.get("/api/admin/ai-center/disclaimers/health_qa", headers=headers)
    assert verify.json()["disclaimer_text"] == "新免责文案：本内容由AI生成，仅供参考"


@pytest.mark.asyncio
async def test_tc019_update_disclaimer_enabled_status(client: AsyncClient, db_session):
    """TC-019: 更新免责提示启用状态（成功）"""
    await _create_admin(db_session)
    headers = await _admin_login(client)
    await _seed_disclaimer(db_session, "health_qa", "健康问答", "免责文案", True)

    resp = await client.put(
        "/api/admin/ai-center/disclaimers/health_qa",
        headers=headers,
        json={"is_enabled": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_enabled"] is False

    resp2 = await client.put(
        "/api/admin/ai-center/disclaimers/health_qa",
        headers=headers,
        json={"is_enabled": True},
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_enabled"] is True


@pytest.mark.asyncio
async def test_tc020_non_admin_access_disclaimers(client: AsyncClient):
    """TC-020: 非管理员访问免责提示接口（401/403）"""
    resp_no_auth = await client.get("/api/admin/ai-center/disclaimers")
    assert resp_no_auth.status_code in (401, 403)

    await client.post("/api/auth/register", json={
        "phone": "13900060003",
        "password": "user123",
        "nickname": "普通用户3",
    })
    login_resp = await client.post("/api/auth/login", json={
        "phone": "13900060003",
        "password": "user123",
    })
    user_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp_list = await client.get("/api/admin/ai-center/disclaimers", headers=user_headers)
    assert resp_list.status_code in (401, 403)

    resp_detail = await client.get("/api/admin/ai-center/disclaimers/health_qa", headers=user_headers)
    assert resp_detail.status_code in (401, 403, 404)
