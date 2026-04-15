"""体检报告与家庭成员关联：模型、上传/OCR、列表与 AI 解读行为测试。"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.models import CheckupReport, FamilyMember, HealthProfile, OcrSceneTemplate
from app.schemas.report import FamilyMemberBrief

from .test_report import (
    _create_ocr_config,
    _create_report,
    _get_user_id,
    _make_test_image,
)


# ──────────────── 1. CheckupReport 模型 ────────────────


def test_checkup_report_has_nullable_family_member_id_column():
    assert "family_member_id" in CheckupReport.__table__.columns
    col = CheckupReport.__table__.c.family_member_id
    assert col.nullable is True


# ──────────────── 2. FamilyMemberBrief Schema ────────────────


def test_family_member_brief_schema_fields():
    fields = FamilyMemberBrief.model_fields
    assert set(fields.keys()) == {"id", "nickname", "relationship_type", "is_self"}

    brief = FamilyMemberBrief(
        id=1,
        nickname="父亲",
        relationship_type="parent",
        is_self=False,
    )
    assert brief.id == 1
    assert brief.nickname == "父亲"
    assert brief.relationship_type == "parent"
    assert brief.is_self is False


# ──────────────── 3. POST /api/report/upload ────────────────


@pytest.mark.asyncio
async def test_upload_report_without_family_member_id_backward_compatible(
    client: AsyncClient, auth_headers, db_session,
):
    await _create_ocr_config(db_session)
    image_data = _make_test_image()

    with patch("app.api.report.try_cos_upload", new_callable=AsyncMock, return_value=None), \
         patch("app.api.report.ensure_access_token", new_callable=AsyncMock) as mock_token, \
         patch("app.api.report.ocr_recognize", new_callable=AsyncMock) as mock_ocr:
        mock_token.return_value = ("fake_token", datetime.utcnow() + timedelta(days=1))
        mock_ocr.return_value = "血红蛋白 150 g/L"

        resp = await client.post(
            "/api/report/upload",
            files={"file": ("report.jpg", image_data, "image/jpeg")},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    report_id = resp.json()["id"]
    report = await db_session.get(CheckupReport, report_id)
    assert report is not None
    assert report.family_member_id is None


@pytest.mark.asyncio
async def test_upload_report_with_family_member_id(
    client: AsyncClient, auth_headers, db_session,
):
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)
    fm = FamilyMember(
        user_id=user_id,
        relationship_type="parent",
        nickname="父亲",
        gender="male",
        birthday=date(1960, 3, 1),
        is_self=False,
    )
    db_session.add(fm)
    await db_session.commit()
    await db_session.refresh(fm)

    image_data = _make_test_image()

    with patch("app.api.report.try_cos_upload", new_callable=AsyncMock, return_value=None), \
         patch("app.api.report.ensure_access_token", new_callable=AsyncMock) as mock_token, \
         patch("app.api.report.ocr_recognize", new_callable=AsyncMock) as mock_ocr:
        mock_token.return_value = ("fake_token", datetime.utcnow() + timedelta(days=1))
        mock_ocr.return_value = "血红蛋白 150 g/L"

        resp = await client.post(
            "/api/report/upload",
            files={"file": ("report.jpg", image_data, "image/jpeg")},
            data={"family_member_id": str(fm.id)},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    report_id = resp.json()["id"]
    report = await db_session.get(CheckupReport, report_id)
    assert report.family_member_id == fm.id


# ──────────────── 4. POST /api/ocr/batch-recognize ────────────────


@pytest.mark.asyncio
async def test_batch_recognize_without_family_member_id(
    client: AsyncClient, auth_headers, db_session,
):
    db_session.add(OcrSceneTemplate(scene_name="体检报告识别", prompt_content="test"))
    await db_session.commit()

    image_data = _make_test_image()
    merged_ai = {
        "report_type": "体检",
        "categories": [{
            "name": "血常规",
            "items": [{"name": "白细胞", "value": "6", "unit": "10^9/L", "riskLevel": 2}],
        }],
    }

    with patch("app.api.ocr.smart_ocr_recognize", new_callable=AsyncMock) as mock_smart, \
         patch("app.api.ocr._call_ai_with_scene", new_callable=AsyncMock) as mock_ai:
        mock_smart.return_value = ("ocr text line", "test_provider")
        mock_ai.return_value = merged_ai

        resp = await client.post(
            "/api/ocr/batch-recognize",
            files=[("files", ("a.jpg", image_data, "image/jpeg"))],
            data={"scene_name": "体检报告识别"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("report_id") is not None
    report = await db_session.get(CheckupReport, body["report_id"])
    assert report is not None
    assert report.family_member_id is None


@pytest.mark.asyncio
async def test_batch_recognize_with_family_member_id(
    client: AsyncClient, auth_headers, db_session,
):
    db_session.add(OcrSceneTemplate(scene_name="体检报告识别", prompt_content="test"))
    await db_session.commit()

    user_id = await _get_user_id(client, auth_headers)
    fm = FamilyMember(
        user_id=user_id,
        relationship_type="child",
        nickname="孩子",
        gender="male",
        is_self=False,
    )
    db_session.add(fm)
    await db_session.commit()
    await db_session.refresh(fm)

    image_data = _make_test_image()
    merged_ai = {
        "report_type": "体检",
        "categories": [{
            "name": "血常规",
            "items": [{"name": "白细胞", "value": "6", "unit": "10^9/L", "riskLevel": 2}],
        }],
    }

    with patch("app.api.ocr.smart_ocr_recognize", new_callable=AsyncMock) as mock_smart, \
         patch("app.api.ocr._call_ai_with_scene", new_callable=AsyncMock) as mock_ai:
        mock_smart.return_value = ("ocr text line", "test_provider")
        mock_ai.return_value = merged_ai

        resp = await client.post(
            "/api/ocr/batch-recognize",
            files=[("files", ("a.jpg", image_data, "image/jpeg"))],
            data={"scene_name": "体检报告识别", "family_member_id": str(fm.id)},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("report_id") is not None
    report = await db_session.get(CheckupReport, body["report_id"])
    assert report.family_member_id == fm.id


# ──────────────── 5. GET /api/report/list family_member ────────────────


@pytest.mark.asyncio
async def test_report_list_includes_family_member_field_old_data_null(
    client: AsyncClient, auth_headers, db_session,
):
    user_id = await _get_user_id(client, auth_headers)
    old = await _create_report(db_session, user_id, file_url="/uploads/old.jpg")

    resp = await client.get("/api/report/list", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    row = next((x for x in items if x["id"] == old.id), None)
    assert row is not None
    assert "family_member" in row
    assert row["family_member"] is None


@pytest.mark.asyncio
async def test_report_list_family_member_brief_populated(
    client: AsyncClient, auth_headers, db_session,
):
    user_id = await _get_user_id(client, auth_headers)
    fm = FamilyMember(
        user_id=user_id,
        relationship_type="spouse",
        nickname="配偶",
        gender="female",
        is_self=False,
    )
    db_session.add(fm)
    await db_session.commit()
    await db_session.refresh(fm)

    r = await _create_report(
        db_session, user_id,
        file_url="/uploads/with_fm.jpg",
        family_member_id=fm.id,
    )

    resp = await client.get("/api/report/list", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    row = next((x for x in items if x["id"] == r.id), None)
    assert row is not None
    fm_json = row["family_member"]
    assert fm_json is not None
    assert fm_json["id"] == fm.id
    assert fm_json["nickname"] == "配偶"
    assert fm_json["relationship_type"] == "spouse"
    assert fm_json["is_self"] is False


# ──────────────── 6. POST /api/report/analyze 档案来源 ────────────────


@pytest.mark.asyncio
async def test_analyze_uses_health_profile_for_own_report(
    client: AsyncClient, auth_headers, db_session,
):
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)

    hp = HealthProfile(
        user_id=user_id,
        gender="male",
        birthday=date(1990, 6, 15),
        height=175.0,
        weight=72.0,
    )
    db_session.add(hp)
    await db_session.commit()

    report = await _create_report(
        db_session, user_id,
        status="pending",
        file_url="/uploads/local.jpg",
        ocr_result={"text": "血红蛋白 150 g/L"},
        family_member_id=None,
    )

    mock_analysis = {
        "overall_assessment": "正常",
        "categories": [{
            "category_name": "血常规",
            "indicators": [{
                "name": "血红蛋白",
                "value": "150",
                "unit": "g/L",
                "reference_range": "120-160",
                "riskLevel": 2,
            }],
        }],
        "suggestions": [],
    }

    with patch("app.api.report.analyze_report_structured", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = mock_analysis
        resp = await client.post(
            "/api/report/analyze",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    mock_ai.assert_called_once()
    passed_profile = mock_ai.call_args[0][1]
    assert passed_profile == {
        "gender": "male",
        "birthday": "1990-06-15",
        "height": 175.0,
        "weight": 72.0,
    }


@pytest.mark.asyncio
async def test_analyze_uses_family_member_profile_for_relative_report(
    client: AsyncClient, auth_headers, db_session,
):
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)

    hp = HealthProfile(
        user_id=user_id,
        gender="male",
        birthday=date(1990, 6, 15),
        height=175.0,
        weight=72.0,
    )
    db_session.add(hp)

    fm = FamilyMember(
        user_id=user_id,
        relationship_type="parent",
        nickname="父亲",
        gender="female",
        birthday=date(1962, 1, 20),
        height=158.0,
        weight=55.0,
        is_self=False,
    )
    db_session.add(fm)
    await db_session.commit()
    await db_session.refresh(fm)

    report = await _create_report(
        db_session, user_id,
        status="pending",
        file_url="/uploads/local.jpg",
        ocr_result={"text": "血红蛋白 150 g/L"},
        family_member_id=fm.id,
    )

    mock_analysis = {
        "overall_assessment": "正常",
        "categories": [{
            "category_name": "血常规",
            "indicators": [{
                "name": "血红蛋白",
                "value": "150",
                "unit": "g/L",
                "riskLevel": 2,
            }],
        }],
        "suggestions": [],
    }

    with patch("app.api.report.analyze_report_structured", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = mock_analysis
        resp = await client.post(
            "/api/report/analyze",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    mock_ai.assert_called_once()
    passed_profile = mock_ai.call_args[0][1]
    assert passed_profile == {
        "gender": "female",
        "birthday": "1962-01-20",
        "height": 158.0,
        "weight": 55.0,
    }
