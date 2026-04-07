import io
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import (
    CheckupIndicator,
    CheckupReport,
    IndicatorStatus,
    OcrConfig,
    ReportAlert,
    User,
    UserRole,
)


def _make_test_image(width: int = 600, height: int = 400) -> bytes:
    """Generate a valid JPEG that passes check_image_quality (>10KB, >=200x200)."""
    try:
        import random
        from PIL import Image

        img = Image.new("RGB", (width, height))
        pixels = img.load()
        rng = random.Random(42)
        for x in range(width):
            for y in range(height):
                pixels[x, y] = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except ImportError:
        header = b"\xff\xd8\xff\xe0" + b"\x00" * (12 * 1024)
        return header


async def _create_ocr_config(db_session, *, enabled=True) -> OcrConfig:
    cfg = OcrConfig(
        enabled=enabled,
        api_key="test_api_key",
        secret_key_encrypted="test_secret",
        ocr_type="general_basic",
    )
    db_session.add(cfg)
    await db_session.commit()
    await db_session.refresh(cfg)
    return cfg


async def _create_report(db_session, user_id: int, **overrides) -> CheckupReport:
    defaults = dict(
        user_id=user_id,
        file_url="/uploads/test_report.jpg",
        thumbnail_url="/uploads/test_report.jpg",
        file_type="image",
        status="completed",
        ocr_result={"text": "血红蛋白 150 g/L 参考范围 120-160"},
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


async def _create_indicator(db_session, report_id: int, **overrides) -> CheckupIndicator:
    defaults = dict(
        report_id=report_id,
        indicator_name="血红蛋白",
        value="150",
        unit="g/L",
        reference_range="120-160",
        status=IndicatorStatus.normal,
        category="血常规",
    )
    defaults.update(overrides)
    indicator = CheckupIndicator(**defaults)
    db_session.add(indicator)
    await db_session.commit()
    await db_session.refresh(indicator)
    return indicator


async def _get_user_id(client: AsyncClient, headers: dict) -> int:
    me = await client.get("/api/auth/me", headers=headers)
    return me.json()["id"]


# ──────────────── 1. Login & Token ────────────────


@pytest.mark.asyncio
async def test_admin_login_get_token(client: AsyncClient, db_session):
    db_session.add(User(
        phone="13800100001",
        password_hash=get_password_hash("admin123456"),
        nickname="报告管理员",
        role=UserRole.admin,
    ))
    await db_session.commit()

    resp = await client.post("/api/admin/login", json={
        "phone": "13800100001",
        "password": "admin123456",
    })
    assert resp.status_code == 200
    assert "token" in resp.json()


@pytest.mark.asyncio
async def test_user_register_get_token(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "phone": "13800100002",
        "password": "user123456",
        "nickname": "报告用户",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# ──────────────── 2. OCR Config ────────────────


@pytest.mark.asyncio
async def test_get_ocr_config(client: AsyncClient, admin_headers, db_session):
    await _create_ocr_config(db_session)

    resp = await client.get("/api/admin/ocr/config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["ocr_type"] == "general_basic"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_ocr_config_not_found(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/ocr/config", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_ocr_config(client: AsyncClient, admin_headers, db_session):
    await _create_ocr_config(db_session, enabled=False)

    resp = await client.put("/api/admin/ocr/config", json={
        "enabled": True,
        "ocr_type": "accurate_basic",
    }, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["ocr_type"] == "accurate_basic"


@pytest.mark.asyncio
async def test_update_ocr_config_partial(client: AsyncClient, admin_headers, db_session):
    await _create_ocr_config(db_session)

    resp = await client.put("/api/admin/ocr/config", json={
        "api_key": "new_api_key",
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["api_key"] == "new_api_key"


@pytest.mark.asyncio
async def test_ocr_config_denied_for_normal_user(client: AsyncClient, auth_headers, db_session):
    await _create_ocr_config(db_session)

    get_resp = await client.get("/api/admin/ocr/config", headers=auth_headers)
    assert get_resp.status_code == 403

    put_resp = await client.put("/api/admin/ocr/config", json={"enabled": False}, headers=auth_headers)
    assert put_resp.status_code == 403


@pytest.mark.asyncio
async def test_ocr_test_connection_success(client: AsyncClient, admin_headers, db_session):
    await _create_ocr_config(db_session)

    with patch("app.api.report.ensure_access_token", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = ("fake_token", datetime.utcnow() + timedelta(days=1))
        resp = await client.post("/api/admin/ocr/test", headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_ocr_test_no_config(client: AsyncClient, admin_headers):
    resp = await client.post("/api/admin/ocr/test", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ocr_test_no_keys(client: AsyncClient, admin_headers, db_session):
    cfg = OcrConfig(enabled=True, api_key=None, secret_key_encrypted=None, ocr_type="general_basic")
    db_session.add(cfg)
    await db_session.commit()

    resp = await client.post("/api/admin/ocr/test", headers=admin_headers)
    assert resp.status_code == 400


# ──────────────── 3. Report Upload ────────────────


@pytest.mark.asyncio
async def test_upload_report_image(client: AsyncClient, auth_headers, db_session):
    await _create_ocr_config(db_session)
    image_data = _make_test_image()

    resp = await client.post(
        "/api/report/upload",
        files={"file": ("report.jpg", image_data, "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["file_type"] == "image"
    assert "id" in data
    assert "file_url" in data


@pytest.mark.asyncio
async def test_upload_report_ocr_disabled(client: AsyncClient, auth_headers, db_session):
    await _create_ocr_config(db_session, enabled=False)

    resp = await client.post(
        "/api/report/upload",
        files={"file": ("report.jpg", _make_test_image(), "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_upload_report_unsupported_format(client: AsyncClient, auth_headers, db_session):
    await _create_ocr_config(db_session)

    resp = await client.post(
        "/api/report/upload",
        files={"file": ("report.txt", b"hello world text", "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_report_no_ocr_config(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/report/upload",
        files={"file": ("report.jpg", _make_test_image(), "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 503


# ──────────────── 4. Report List ────────────────


@pytest.mark.asyncio
async def test_report_list_empty(client: AsyncClient, auth_headers):
    resp = await client.get("/api/report/list", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_report_list_with_data(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    await _create_report(db_session, user_id, file_url="/uploads/r1.jpg")
    await _create_report(db_session, user_id, file_url="/uploads/r2.jpg")

    resp = await client.get("/api/report/list", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_report_list_pagination(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    for i in range(5):
        await _create_report(db_session, user_id, file_url=f"/uploads/p{i}.jpg")

    resp = await client.get("/api/report/list?page=1&page_size=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2

    resp2 = await client.get("/api/report/list?page=3&page_size=2", headers=auth_headers)
    data2 = resp2.json()
    assert len(data2["items"]) == 1


# ──────────────── 5. Report Detail ────────────────


@pytest.mark.asyncio
async def test_report_detail(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)
    await _create_indicator(db_session, report.id)

    resp = await client.get(f"/api/report/detail/{report.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == report.id
    assert data["status"] == "completed"
    assert data["ai_analysis"] == "整体健康状况良好"
    assert len(data["indicators"]) == 1
    assert data["indicators"][0]["indicator_name"] == "血红蛋白"


@pytest.mark.asyncio
async def test_report_detail_not_found(client: AsyncClient, auth_headers):
    resp = await client.get("/api/report/detail/99999", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_detail_belongs_to_other_user(client: AsyncClient, auth_headers, db_session):
    other = User(
        phone="13800200001",
        password_hash=get_password_hash("other123"),
        nickname="他人",
        role=UserRole.user,
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    report = await _create_report(db_session, other.id)
    resp = await client.get(f"/api/report/detail/{report.id}", headers=auth_headers)
    assert resp.status_code == 404


# ──────────────── 6. Trend Data ────────────────


@pytest.mark.asyncio
async def test_trend_data(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    r1 = await _create_report(db_session, user_id, file_url="/uploads/t1.jpg")
    r2 = await _create_report(db_session, user_id, file_url="/uploads/t2.jpg")
    await _create_indicator(db_session, r1.id, indicator_name="血红蛋白", value="145")
    await _create_indicator(db_session, r2.id, indicator_name="血红蛋白", value="150")

    resp = await client.get("/api/report/trend/血红蛋白", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator_name"] == "血红蛋白"
    assert len(data["data_points"]) == 2


@pytest.mark.asyncio
async def test_trend_data_empty(client: AsyncClient, auth_headers):
    resp = await client.get("/api/report/trend/不存在指标", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data_points"] == []


@pytest.mark.asyncio
async def test_trend_analysis(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)
    await _create_indicator(db_session, report.id, indicator_name="血糖", value="5.6")

    with patch("app.api.report.analyze_trend", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = "血糖水平正常，建议保持良好生活习惯。"
        resp = await client.post(
            "/api/report/trend/analysis",
            json={"indicator_name": "血糖"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator_name"] == "血糖"
    assert "analysis" in data
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_trend_analysis_no_data(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/report/trend/analysis",
        json={"indicator_name": "不存在指标"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ──────────────── 7. Alert Check ────────────────


@pytest.mark.asyncio
async def test_alert_check_new_abnormal(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)
    await _create_indicator(
        db_session, report.id,
        indicator_name="血糖", value="8.5",
        status=IndicatorStatus.abnormal,
    )

    resp = await client.post(
        "/api/report/alert/check",
        json={"report_id": report.id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["alerts_generated"] >= 1
    assert any(a["alert_type"] == "new_abnormal" for a in data["alerts"])


@pytest.mark.asyncio
async def test_alert_check_no_abnormal(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)
    await _create_indicator(db_session, report.id, status=IndicatorStatus.normal)

    resp = await client.post(
        "/api/report/alert/check",
        json={"report_id": report.id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["alerts_generated"] == 0


@pytest.mark.asyncio
async def test_alert_check_report_not_found(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/report/alert/check",
        json={"report_id": 99999},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ──────────────── 8. Alert List & Mark Read ────────────────


@pytest.mark.asyncio
async def test_alert_list_empty(client: AsyncClient, auth_headers):
    resp = await client.get("/api/report/alerts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_alert_list_with_data(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)

    alert = ReportAlert(
        user_id=user_id,
        report_id=report.id,
        indicator_name="尿酸",
        alert_type="new_abnormal",
        alert_message="尿酸异常",
    )
    db_session.add(alert)
    await db_session.commit()

    resp = await client.get("/api/report/alerts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["indicator_name"] == "尿酸"
    assert data["items"][0]["is_read"] is False


@pytest.mark.asyncio
async def test_mark_alert_read(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)

    alert = ReportAlert(
        user_id=user_id,
        report_id=report.id,
        indicator_name="血压",
        alert_type="new_abnormal",
        alert_message="血压偏高",
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)

    resp = await client.put(f"/api/report/alerts/{alert.id}/read", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True


@pytest.mark.asyncio
async def test_mark_alert_read_not_found(client: AsyncClient, auth_headers):
    resp = await client.put("/api/report/alerts/99999/read", headers=auth_headers)
    assert resp.status_code == 404


# ──────────────── 9. Share ────────────────


@pytest.mark.asyncio
async def test_create_share(client: AsyncClient, auth_headers, db_session):
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


@pytest.mark.asyncio
async def test_view_share_valid_token(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)
    await _create_indicator(db_session, report.id)

    share_resp = await client.post(
        "/api/report/share",
        json={"report_id": report.id},
        headers=auth_headers,
    )
    token = share_resp.json()["share_token"]

    resp = await client.get(f"/api/report/share/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert "disclaimer" in data
    assert "abnormal_count" in data
    assert "indicators" in data


@pytest.mark.asyncio
async def test_view_share_invalid_token(client: AsyncClient):
    resp = await client.get("/api/report/share/nonexistent_token_xyz")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_view_share_expired(client: AsyncClient, auth_headers, db_session):
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)
    report.share_token = "expired_token_abc"
    report.share_expires_at = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()

    resp = await client.get("/api/report/share/expired_token_abc")
    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_share_nonexistent_report(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/report/share",
        json={"report_id": 99999},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ──────────────── 10. Permission Control ────────────────


@pytest.mark.asyncio
async def test_report_list_unauthorized(client: AsyncClient):
    resp = await client.get("/api/report/list")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_report_detail_unauthorized(client: AsyncClient):
    resp = await client.get("/api/report/detail/1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_unauthorized(client: AsyncClient):
    resp = await client.post(
        "/api/report/upload",
        files={"file": ("test.jpg", b"x" * 1024, "image/jpeg")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_alerts_unauthorized(client: AsyncClient):
    resp = await client.get("/api/report/alerts")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_trend_unauthorized(client: AsyncClient):
    resp = await client.get("/api/report/trend/血红蛋白")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_share_create_unauthorized(client: AsyncClient):
    resp = await client.post("/api/report/share", json={"report_id": 1})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_alert_check_unauthorized(client: AsyncClient):
    resp = await client.post("/api/report/alert/check", json={"report_id": 1})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mark_alert_read_unauthorized(client: AsyncClient):
    resp = await client.put("/api/report/alerts/1/read")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ocr_config_unauthorized(client: AsyncClient):
    resp = await client.get("/api/admin/ocr/config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ocr_test_unauthorized(client: AsyncClient):
    resp = await client.post("/api/admin/ocr/test")
    assert resp.status_code == 401


# ──────────────── 11. Bug Fix: Upload Pre-OCR & COS URL Support ────────────────


@pytest.mark.asyncio
async def test_upload_pre_executes_ocr(client: AsyncClient, auth_headers, db_session):
    """Verify that upload pre-executes OCR and stores result when OCR succeeds."""
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
    data = resp.json()
    report_id = data["id"]

    report = await db_session.get(CheckupReport, report_id)
    assert report is not None
    assert report.ocr_result is not None
    assert report.ocr_result.get("text") == "血红蛋白 150 g/L"


@pytest.mark.asyncio
async def test_upload_ocr_failure_does_not_block(client: AsyncClient, auth_headers, db_session):
    """Verify that OCR failure at upload time does not prevent the upload itself."""
    await _create_ocr_config(db_session)
    image_data = _make_test_image()

    with patch("app.api.report.try_cos_upload", new_callable=AsyncMock, return_value=None), \
         patch("app.api.report.ensure_access_token", new_callable=AsyncMock) as mock_token:
        mock_token.side_effect = RuntimeError("token fetch failed")

        resp = await client.post(
            "/api/report/upload",
            files={"file": ("report.jpg", image_data, "image/jpeg")},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_analyze_uses_pre_stored_ocr(client: AsyncClient, auth_headers, db_session):
    """When ocr_result already populated (from upload), analyze skips file read."""
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)

    report = await _create_report(
        db_session, user_id,
        status="pending",
        file_url="https://cos.example.com/reports/test.jpg",
        ocr_result={"text": "血红蛋白 150 g/L 参考范围 120-160"},
        ai_analysis=None,
        ai_analysis_json=None,
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
                "status": "normal",
            }],
        }],
        "suggestions": ["保持良好生活习惯"],
    }

    with patch("app.api.report.analyze_report_structured", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = mock_analysis
        resp = await client.post(
            "/api/report/analyze",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert len(data["categories"]) >= 1


@pytest.mark.asyncio
async def test_analyze_cos_url_fallback(client: AsyncClient, auth_headers, db_session):
    """When ocr_result is empty and file_url is a COS URL, read_file_content fetches remotely."""
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)

    report = await _create_report(
        db_session, user_id,
        status="pending",
        file_url="https://cos.example.com/reports/test.jpg",
        ocr_result=None,
        ai_analysis=None,
        ai_analysis_json=None,
    )

    mock_analysis = {
        "overall_assessment": "正常",
        "categories": [],
        "suggestions": [],
    }

    with patch("app.api.report.read_file_content", new_callable=AsyncMock) as mock_read, \
         patch("app.api.report.ensure_access_token", new_callable=AsyncMock) as mock_token, \
         patch("app.api.report.ocr_recognize", new_callable=AsyncMock) as mock_ocr, \
         patch("app.api.report.analyze_report_structured", new_callable=AsyncMock) as mock_ai:
        mock_read.return_value = _make_test_image()
        mock_token.return_value = ("fake_token", datetime.utcnow() + timedelta(days=1))
        mock_ocr.return_value = "血红蛋白 150 g/L"
        mock_ai.return_value = mock_analysis

        resp = await client.post(
            "/api/report/analyze",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    mock_read.assert_called_once_with("https://cos.example.com/reports/test.jpg")


@pytest.mark.asyncio
async def test_analyze_file_not_found_error(client: AsyncClient, auth_headers, db_session):
    """When file cannot be read, returns clear error message."""
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)

    report = await _create_report(
        db_session, user_id,
        status="pending",
        file_url="https://cos.example.com/reports/missing.jpg",
        ocr_result=None,
        ai_analysis=None,
        ai_analysis_json=None,
    )

    with patch("app.api.report.read_file_content", new_callable=AsyncMock) as mock_read:
        mock_read.return_value = None
        resp = await client.post(
            "/api/report/analyze",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 400
    assert "重新上传" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_report_ocr_cos_url(client: AsyncClient, auth_headers, db_session):
    """report_ocr should read from COS URL via read_file_content."""
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)

    report = await _create_report(
        db_session, user_id,
        status="pending",
        file_url="https://cos.example.com/reports/test.jpg",
        ocr_result=None,
        ai_analysis=None,
        ai_analysis_json=None,
    )

    with patch("app.api.report.read_file_content", new_callable=AsyncMock) as mock_read, \
         patch("app.api.report.ensure_access_token", new_callable=AsyncMock) as mock_token, \
         patch("app.api.report.ocr_recognize", new_callable=AsyncMock) as mock_ocr:
        mock_read.return_value = _make_test_image()
        mock_token.return_value = ("fake_token", datetime.utcnow() + timedelta(days=1))
        mock_ocr.return_value = "OCR识别文字结果"

        resp = await client.post(
            "/api/report/ocr",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["ocr_text"] == "OCR识别文字结果"


@pytest.mark.asyncio
async def test_report_ocr_file_missing(client: AsyncClient, auth_headers, db_session):
    """report_ocr returns 404 when file cannot be read."""
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)

    report = await _create_report(
        db_session, user_id,
        status="pending",
        file_url="https://cos.example.com/reports/gone.jpg",
        ocr_result=None,
        ai_analysis=None,
        ai_analysis_json=None,
    )

    with patch("app.api.report.read_file_content", new_callable=AsyncMock) as mock_read:
        mock_read.return_value = None
        resp = await client.post(
            "/api/report/ocr",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 404
    assert "重新上传" in resp.json()["detail"]
