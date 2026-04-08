"""
TC-SL-001 ~ TC-SL-007: 分享链接 & 个性化药物建议接口测试
"""
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import (
    CheckupReport,
    DrugIdentifyDetail,
    HealthProfile,
    PromptTemplate,
    User,
    UserRole,
)


async def _get_user_id(client: AsyncClient, headers: dict) -> int:
    me = await client.get("/api/auth/me", headers=headers)
    return me.json()["id"]


async def _create_report(db_session, user_id: int, **overrides) -> CheckupReport:
    defaults = dict(
        user_id=user_id,
        file_url="/uploads/test_report.jpg",
        thumbnail_url="/uploads/test_report.jpg",
        file_type="image",
        status="completed",
        ocr_result={"text": "血红蛋白 150 g/L"},
        ai_analysis="整体健康状况良好",
        ai_analysis_json={
            "overall_assessment": "整体健康状况良好",
            "categories": [],
            "suggestions": [],
        },
        abnormal_count=0,
    )
    defaults.update(overrides)
    report = CheckupReport(**defaults)
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report


async def _create_drug_record(db_session, user_id: int, **overrides) -> DrugIdentifyDetail:
    defaults = dict(
        user_id=user_id,
        drug_name="阿司匹林",
        drug_category="解热镇痛药",
        dosage="每次100mg，每日一次",
        precautions="胃溃疡患者慎用",
        provider_name="test_provider",
        original_image_url="/uploads/drug_test.jpg",
        ocr_raw_text="阿司匹林肠溶片 100mg",
        ai_structured_result={
            "drug_name": "阿司匹林",
            "category": "解热镇痛药",
        },
        status="success",
    )
    defaults.update(overrides)
    record = DrugIdentifyDetail(**defaults)
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    return record


# ──────────────── TC-SL-001: 用户为体检报告生成分享链接 ────────────────


@pytest.mark.asyncio
async def test_create_report_share_link(client: AsyncClient, auth_headers, db_session):
    """TC-SL-001: 用户为体检报告生成分享链接（POST /api/report/share）"""
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)

    resp = await client.post(
        "/api/report/share",
        json={"report_id": report.id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "share_token" in data
    assert "share_url" in data
    assert "expires_at" in data
    assert len(data["share_token"]) > 0


# ──────────────── TC-SL-002: 公开访问体检报告分享链接 ────────────────


@pytest.mark.asyncio
async def test_view_report_share_link(client: AsyncClient, auth_headers, db_session):
    """TC-SL-002: 公开访问体检报告分享链接（GET /api/report/share/{token}）"""
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)

    share_resp = await client.post(
        "/api/report/share",
        json={"report_id": report.id},
        headers=auth_headers,
    )
    assert share_resp.status_code == 200
    token = share_resp.json()["share_token"]

    resp = await client.get(f"/api/report/share/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert "disclaimer" in data
    assert "abnormal_count" in data
    assert "indicators" in data


# ──────────────── TC-SL-003: 用户为药物识别记录生成分享链接 ────────────────


@pytest.mark.asyncio
async def test_create_drug_share_link(client: AsyncClient, auth_headers, db_session):
    """TC-SL-003: 用户为药物识别记录生成分享链接（POST /api/drug-identify/{id}/share）"""
    user_id = await _get_user_id(client, auth_headers)
    record = await _create_drug_record(db_session, user_id)

    resp = await client.post(
        f"/api/drug-identify/{record.id}/share",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "share_token" in data
    assert "share_url" in data
    assert "record_id" in data
    assert data["record_id"] == record.id
    assert len(data["share_token"]) > 0


# ──────────────── TC-SL-004: 公开访问药物识别分享链接 ────────────────


@pytest.mark.asyncio
async def test_view_drug_share_link(client: AsyncClient, auth_headers, db_session):
    """TC-SL-004: 公开访问药物识别分享链接（GET /api/drug-identify/share/{token}）"""
    user_id = await _get_user_id(client, auth_headers)
    record = await _create_drug_record(db_session, user_id)

    share_resp = await client.post(
        f"/api/drug-identify/{record.id}/share",
        headers=auth_headers,
    )
    assert share_resp.status_code == 200
    token = share_resp.json()["share_token"]

    resp = await client.get(f"/api/drug-identify/share/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_id"] == record.id
    assert data["drug_name"] == "阿司匹林"
    assert data["drug_category"] == "解热镇痛药"
    assert "view_count" in data
    assert data["view_count"] >= 1


# ──────────────── TC-SL-005: 未登录用户无法生成分享链接 ────────────────


@pytest.mark.asyncio
async def test_create_share_link_unauthorized(client: AsyncClient, db_session):
    """TC-SL-005: 未登录用户无法生成分享链接（应返回401）"""
    report_resp = await client.post(
        "/api/report/share",
        json={"report_id": 1},
    )
    assert report_resp.status_code == 401

    drug_resp = await client.post("/api/drug-identify/1/share")
    assert drug_resp.status_code == 401


# ──────────────── TC-SL-006: 不存在的分享token应返回404 ────────────────


@pytest.mark.asyncio
async def test_view_nonexistent_share_token(client: AsyncClient):
    """TC-SL-006: 不存在的分享token应返回404"""
    report_resp = await client.get("/api/report/share/nonexistent_token_xyz_abc_123")
    assert report_resp.status_code == 404

    drug_resp = await client.get("/api/drug-identify/share/nonexistent_token_xyz_abc_123")
    assert drug_resp.status_code == 404


# ──────────────── TC-SL-007: 个性化药物建议接口 ────────────────


@pytest.mark.asyncio
async def test_personal_drug_suggestion_no_health_profile(client: AsyncClient, auth_headers, db_session):
    """TC-SL-007a: 无健康档案时获取个性化药物建议"""
    user_id = await _get_user_id(client, auth_headers)
    record = await _create_drug_record(db_session, user_id)

    with patch("app.api.ocr_details.call_ai_model", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = '{"suggestion": "建议按医嘱服用", "warnings": []}'

        resp = await client.get(
            f"/api/drug-identify/{record.id}/personal-suggestion",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "ai_result" in data
    assert "has_health_profile" in data
    assert data["record_id"] == record.id
    assert data["has_health_profile"] is False


@pytest.mark.asyncio
async def test_personal_drug_suggestion_with_health_profile(client: AsyncClient, auth_headers, db_session):
    """TC-SL-007b: 有健康档案时获取个性化药物建议"""
    user_id = await _get_user_id(client, auth_headers)

    hp = HealthProfile(
        user_id=user_id,
        gender="male",
        height=175.0,
        weight=70.0,
        blood_type="A",
        smoking="否",
        drinking="偶尔",
    )
    db_session.add(hp)
    await db_session.commit()

    record = await _create_drug_record(db_session, user_id)

    with patch("app.api.ocr_details.call_ai_model", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = '{"suggestion": "根据您的档案，建议饭后服用", "warnings": ["注意血压"]}'

        resp = await client.get(
            f"/api/drug-identify/{record.id}/personal-suggestion",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_health_profile"] is True
    assert "ai_result" in data
    assert data["record_id"] == record.id


@pytest.mark.asyncio
async def test_personal_drug_suggestion_with_custom_template(client: AsyncClient, auth_headers, db_session):
    """TC-SL-007c: 有自定义Prompt模板时使用模板生成建议"""
    user_id = await _get_user_id(client, auth_headers)
    record = await _create_drug_record(db_session, user_id)

    tpl = PromptTemplate(
        name="个性化药物建议",
        prompt_type="drug_personal",
        content="你是专业药剂师。用户档案：{health_profile}。请给出个性化建议。",
        version=1,
        is_active=True,
    )
    db_session.add(tpl)
    await db_session.commit()

    with patch("app.api.ocr_details.call_ai_model", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = {"suggestion": "使用自定义模板生成", "warnings": []}

        resp = await client.get(
            f"/api/drug-identify/{record.id}/personal-suggestion",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["record_id"] == record.id
    assert "ai_result" in data


@pytest.mark.asyncio
async def test_personal_drug_suggestion_record_not_found(client: AsyncClient, auth_headers):
    """TC-SL-007d: 不存在的药物记录应返回404"""
    resp = await client.get(
        "/api/drug-identify/99999/personal-suggestion",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_personal_drug_suggestion_unauthorized(client: AsyncClient):
    """TC-SL-007e: 未登录访问个性化建议应返回401"""
    resp = await client.get("/api/drug-identify/1/personal-suggestion")
    assert resp.status_code == 401


# ──────────────── 药物分享链接重复生成 ────────────────


@pytest.mark.asyncio
async def test_create_drug_share_link_idempotent(client: AsyncClient, auth_headers, db_session):
    """重复生成药物分享链接应返回同一token"""
    user_id = await _get_user_id(client, auth_headers)
    record = await _create_drug_record(db_session, user_id)

    resp1 = await client.post(
        f"/api/drug-identify/{record.id}/share",
        headers=auth_headers,
    )
    resp2 = await client.post(
        f"/api/drug-identify/{record.id}/share",
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["share_token"] == resp2.json()["share_token"]


@pytest.mark.asyncio
async def test_drug_share_view_increments_view_count(client: AsyncClient, auth_headers, db_session):
    """访问药物分享链接应增加浏览计数"""
    user_id = await _get_user_id(client, auth_headers)
    record = await _create_drug_record(db_session, user_id)

    share_resp = await client.post(
        f"/api/drug-identify/{record.id}/share",
        headers=auth_headers,
    )
    token = share_resp.json()["share_token"]

    resp1 = await client.get(f"/api/drug-identify/share/{token}")
    assert resp1.json()["view_count"] == 1

    resp2 = await client.get(f"/api/drug-identify/share/{token}")
    assert resp2.json()["view_count"] == 2


@pytest.mark.asyncio
async def test_drug_share_other_user_record_not_found(client: AsyncClient, auth_headers, db_session):
    """不能为他人的药物记录生成分享链接"""
    other = User(
        phone="13800300001",
        password_hash=get_password_hash("other123"),
        nickname="他人用户",
        role=UserRole.user,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    record = await _create_drug_record(db_session, other.id)

    resp = await client.post(
        f"/api/drug-identify/{record.id}/share",
        headers=auth_headers,
    )
    assert resp.status_code == 404
