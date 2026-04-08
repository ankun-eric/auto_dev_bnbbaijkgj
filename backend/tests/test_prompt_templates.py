"""
TC-PT-001 ~ TC-PT-008: Prompt 模板管理接口测试
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import PromptTemplate, User, UserRole


async def _create_prompt_template(
    db_session,
    prompt_type: str = "checkup_report",
    content: str = "你是体检报告解读专家",
    version: int = 1,
    is_active: bool = True,
    parent_id=None,
) -> PromptTemplate:
    tpl = PromptTemplate(
        name=f"模板_{prompt_type}_v{version}",
        prompt_type=prompt_type,
        content=content,
        version=version,
        is_active=is_active,
        parent_id=parent_id,
    )
    db_session.add(tpl)
    await db_session.commit()
    await db_session.refresh(tpl)
    return tpl


# ──────────────── TC-PT-001: 管理员获取所有Prompt模板列表 ────────────────


@pytest.mark.asyncio
async def test_list_prompt_templates(client: AsyncClient, admin_headers, db_session):
    """TC-PT-001: 管理员获取所有Prompt模板列表"""
    await _create_prompt_template(db_session, prompt_type="checkup_report")
    await _create_prompt_template(db_session, prompt_type="drug_general")

    resp = await client.get("/api/admin/prompt-templates", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    prompt_types = [item["prompt_type"] for item in data]
    assert "checkup_report" in prompt_types
    assert "drug_general" in prompt_types
    for item in data:
        assert "prompt_type" in item
        assert "display_name" in item


# ──────────────── TC-PT-002: 管理员获取指定类型模板（checkup_report类型）────────────────


@pytest.mark.asyncio
async def test_get_prompt_template_checkup_report(client: AsyncClient, admin_headers, db_session):
    """TC-PT-002: 管理员获取指定类型模板（checkup_report类型）"""
    await _create_prompt_template(
        db_session,
        prompt_type="checkup_report",
        content="你是专业体检报告解读专家，请分析以下报告。",
        version=1,
    )

    resp = await client.get("/api/admin/prompt-templates/checkup_report", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["prompt_type"] == "checkup_report"
    assert data["display_name"] == "体检报告解读"
    assert data["active"] is not None
    assert data["active"]["content"] == "你是专业体检报告解读专家，请分析以下报告。"
    assert data["active"]["version"] == 1
    assert data["active"]["is_active"] is True
    assert isinstance(data["history"], list)


# ──────────────── TC-PT-003: 管理员获取指定类型模板（drug_general类型）────────────────


@pytest.mark.asyncio
async def test_get_prompt_template_drug_general(client: AsyncClient, admin_headers, db_session):
    """TC-PT-003: 管理员获取指定类型模板（drug_general类型）"""
    await _create_prompt_template(
        db_session,
        prompt_type="drug_general",
        content="你是专业药剂师AI，请分析以下药物信息。",
        version=1,
    )

    resp = await client.get("/api/admin/prompt-templates/drug_general", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["prompt_type"] == "drug_general"
    assert data["display_name"] == "药物识别通用建议"
    assert data["active"] is not None
    assert data["active"]["content"] == "你是专业药剂师AI，请分析以下药物信息。"


# ──────────────── TC-PT-004: 管理员更新Prompt模板内容（更新后版本号+1）────────────────


@pytest.mark.asyncio
async def test_update_prompt_template_version_increment(client: AsyncClient, admin_headers, db_session):
    """TC-PT-004: 管理员更新Prompt模板内容（更新后版本号+1）"""
    await _create_prompt_template(
        db_session,
        prompt_type="checkup_report",
        content="旧版Prompt内容",
        version=1,
        is_active=True,
    )

    resp = await client.put(
        "/api/admin/prompt-templates/checkup_report",
        json={"content": "新版Prompt内容，更详细的解读指令。"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "新版Prompt内容，更详细的解读指令。"
    assert data["version"] == 2
    assert data["is_active"] is True
    assert data["prompt_type"] == "checkup_report"


# ──────────────── TC-PT-005: 管理员预览Prompt模板效果 ────────────────


@pytest.mark.asyncio
async def test_preview_prompt_template_returns_ai_result(client: AsyncClient, admin_headers, db_session):
    """TC-PT-005: 管理员预览Prompt模板效果（返回ai_result字段）"""
    await _create_prompt_template(
        db_session,
        prompt_type="checkup_report",
        content="你是体检报告解读专家。",
        version=1,
    )

    with patch("app.api.prompt_templates.call_ai_model", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = '{"overall_assessment": "正常", "suggestions": []}'

        resp = await client.post(
            "/api/admin/prompt-templates/checkup_report/preview",
            json={"input_text": "血红蛋白 150 g/L 参考范围 120-160"},
            headers=admin_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "ai_result" in data
    assert data["prompt_type"] == "checkup_report"
    assert data["input_text"] == "血红蛋白 150 g/L 参考范围 120-160"


# ──────────────── TC-PT-006: 管理员回滚到历史版本 ────────────────


@pytest.mark.asyncio
async def test_rollback_prompt_template(client: AsyncClient, admin_headers, db_session):
    """TC-PT-006: 管理员回滚到历史版本"""
    v1 = await _create_prompt_template(
        db_session,
        prompt_type="drug_general",
        content="V1版本内容",
        version=1,
        is_active=False,
    )
    await _create_prompt_template(
        db_session,
        prompt_type="drug_general",
        content="V2版本内容",
        version=2,
        is_active=True,
        parent_id=v1.id,
    )

    resp = await client.post(
        f"/api/admin/prompt-templates/drug_general/rollback/1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "active_version" in data
    assert data["active_version"] == 3


# ──────────────── TC-PT-007: 非管理员访问Prompt模板接口应返回403 ────────────────


@pytest.mark.asyncio
async def test_prompt_templates_forbidden_for_normal_user(client: AsyncClient, auth_headers):
    """TC-PT-007: 非管理员访问Prompt模板接口应返回403"""
    list_resp = await client.get("/api/admin/prompt-templates", headers=auth_headers)
    assert list_resp.status_code == 403

    get_resp = await client.get("/api/admin/prompt-templates/checkup_report", headers=auth_headers)
    assert get_resp.status_code == 403

    put_resp = await client.put(
        "/api/admin/prompt-templates/checkup_report",
        json={"content": "非法更新"},
        headers=auth_headers,
    )
    assert put_resp.status_code == 403

    preview_resp = await client.post(
        "/api/admin/prompt-templates/checkup_report/preview",
        json={"input_text": "测试"},
        headers=auth_headers,
    )
    assert preview_resp.status_code == 403


# ──────────────── TC-PT-008: 更新模板后旧版本保留在历史记录中 ────────────────


@pytest.mark.asyncio
async def test_update_template_keeps_old_version_in_history(client: AsyncClient, admin_headers, db_session):
    """TC-PT-008: 更新模板后旧版本保留在历史记录中"""
    await _create_prompt_template(
        db_session,
        prompt_type="trend_analysis",
        content="原始Prompt内容",
        version=1,
        is_active=True,
    )

    await client.put(
        "/api/admin/prompt-templates/trend_analysis",
        json={"content": "更新后的Prompt内容"},
        headers=admin_headers,
    )

    resp = await client.get("/api/admin/prompt-templates/trend_analysis", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["active"] is not None
    assert data["active"]["content"] == "更新后的Prompt内容"
    assert data["active"]["version"] == 2

    assert len(data["history"]) >= 1
    old_versions = [h for h in data["history"] if h["version"] == 1]
    assert len(old_versions) == 1
    assert old_versions[0]["content"] == "原始Prompt内容"
    assert old_versions[0]["is_active"] is False


# ──────────────── 边界用例 ────────────────


@pytest.mark.asyncio
async def test_get_invalid_prompt_type(client: AsyncClient, admin_headers):
    """无效的模板类型应返回400"""
    resp = await client.get("/api/admin/prompt-templates/invalid_type", headers=admin_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_invalid_prompt_type(client: AsyncClient, admin_headers):
    """更新无效类型模板应返回400"""
    resp = await client.put(
        "/api/admin/prompt-templates/invalid_type",
        json={"content": "内容"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_preview_no_active_template(client: AsyncClient, admin_headers):
    """预览无激活模板时应返回404"""
    resp = await client.post(
        "/api/admin/prompt-templates/drug_interaction/preview",
        json={"input_text": "测试内容"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_prompt_templates_unauthorized(client: AsyncClient):
    """未登录访问Prompt模板接口应返回401"""
    resp = await client.get("/api/admin/prompt-templates")
    assert resp.status_code == 401
