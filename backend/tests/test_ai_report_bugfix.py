"""Tests for AI report bugfix: retry mechanism, exception raising, and error handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import CheckupReport, OcrConfig, User, UserRole
from app.services.ai_service import call_ai_model


# ── helpers ──


AI_SERVICE_MODULE = "app.services.ai_service"
REPORT_MODULE = "app.api.report"

FAKE_SUCCESS_RESPONSE = {
    "choices": [{"message": {"content": "AI分析结果"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
}

SAMPLE_MESSAGES = [{"role": "user", "content": "hello"}]


def _mock_response(status_code: int = 200, json_data: dict | None = None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or FAKE_SUCCESS_RESPONSE
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        request = MagicMock(spec=httpx.Request)
        request.url = "http://fake/chat/completions"
        resp.request = request
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=request, response=resp,
        )
    return resp


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
        status="pending",
        ocr_result={"text": "血红蛋白 150 g/L 参考范围 120-160"},
        ai_analysis=None,
        ai_analysis_json=None,
        abnormal_count=0,
    )
    defaults.update(overrides)
    report = CheckupReport(**defaults)
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report


async def _get_user_id(client: AsyncClient, headers: dict) -> int:
    me = await client.get("/api/auth/me", headers=headers)
    return me.json()["id"]


# ═══════════════════════════════════════════════════════════════════════
# a) call_ai_model retry mechanism tests
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_retry_timeout_then_success():
    """First call times out, second succeeds — result returned."""
    mock_post = AsyncMock(side_effect=[
        httpx.TimeoutException("read timed out"),
        _mock_response(200),
    ])

    with patch(f"{AI_SERVICE_MODULE}._get_active_model_config", new_callable=AsyncMock) as mock_cfg, \
         patch(f"{AI_SERVICE_MODULE}.asyncio.sleep", new_callable=AsyncMock):
        mock_cfg.return_value = {
            "base_url": "http://fake", "model": "test-model",
            "api_key": "key", "max_tokens": 100, "temperature": 0.7,
        }
        with patch("httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = mock_post
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await call_ai_model(SAMPLE_MESSAGES)

    assert result == "AI分析结果"
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_retry_3_timeouts_raises_exception():
    """All 3 attempts time out — raises Exception."""
    mock_post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with patch(f"{AI_SERVICE_MODULE}._get_active_model_config", new_callable=AsyncMock) as mock_cfg, \
         patch(f"{AI_SERVICE_MODULE}.asyncio.sleep", new_callable=AsyncMock):
        mock_cfg.return_value = {
            "base_url": "http://fake", "model": "test-model",
            "api_key": "key", "max_tokens": 100, "temperature": 0.7,
        }
        with patch("httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = mock_post
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(Exception, match="AI服务调用失败"):
                await call_ai_model(SAMPLE_MESSAGES)

    assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_retry_on_http_5xx():
    """HTTP 500 triggers retry; second attempt succeeds."""
    mock_post = AsyncMock(side_effect=[
        _mock_response(500),
        _mock_response(200),
    ])

    with patch(f"{AI_SERVICE_MODULE}._get_active_model_config", new_callable=AsyncMock) as mock_cfg, \
         patch(f"{AI_SERVICE_MODULE}.asyncio.sleep", new_callable=AsyncMock):
        mock_cfg.return_value = {
            "base_url": "http://fake", "model": "test-model",
            "api_key": "key", "max_tokens": 100, "temperature": 0.7,
        }
        with patch("httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = mock_post
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await call_ai_model(SAMPLE_MESSAGES)

    assert result == "AI分析结果"
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_no_retry_on_http_4xx():
    """HTTP 4xx does not retry — fails immediately."""
    mock_post = AsyncMock(return_value=_mock_response(400))

    with patch(f"{AI_SERVICE_MODULE}._get_active_model_config", new_callable=AsyncMock) as mock_cfg, \
         patch(f"{AI_SERVICE_MODULE}.asyncio.sleep", new_callable=AsyncMock):
        mock_cfg.return_value = {
            "base_url": "http://fake", "model": "test-model",
            "api_key": "key", "max_tokens": 100, "temperature": 0.7,
        }
        with patch("httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = mock_post
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(Exception, match="AI服务调用失败"):
                await call_ai_model(SAMPLE_MESSAGES)

    assert mock_post.call_count == 1


# ═══════════════════════════════════════════════════════════════════════
# b) call_ai_model exception vs return_usage behaviour
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_all_retries_exhausted_raises_when_return_usage_false():
    """return_usage=False (default): raises Exception after all retries."""
    mock_post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with patch(f"{AI_SERVICE_MODULE}._get_active_model_config", new_callable=AsyncMock) as mock_cfg, \
         patch(f"{AI_SERVICE_MODULE}.asyncio.sleep", new_callable=AsyncMock):
        mock_cfg.return_value = {
            "base_url": "http://fake", "model": "test-model",
            "api_key": "key", "max_tokens": 100, "temperature": 0.7,
        }
        with patch("httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = mock_post
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(Exception, match="AI服务调用失败"):
                await call_ai_model(SAMPLE_MESSAGES, return_usage=False)


@pytest.mark.asyncio
async def test_all_retries_exhausted_returns_dict_when_return_usage_true():
    """return_usage=True: returns error dict instead of raising."""
    mock_post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with patch(f"{AI_SERVICE_MODULE}._get_active_model_config", new_callable=AsyncMock) as mock_cfg, \
         patch(f"{AI_SERVICE_MODULE}.asyncio.sleep", new_callable=AsyncMock):
        mock_cfg.return_value = {
            "base_url": "http://fake", "model": "test-model",
            "api_key": "key", "max_tokens": 100, "temperature": 0.7,
        }
        with patch("httpx.AsyncClient") as MockClient:
            ctx = AsyncMock()
            ctx.post = mock_post
            MockClient.return_value.__aenter__ = AsyncMock(return_value=ctx)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await call_ai_model(SAMPLE_MESSAGES, return_usage=True)

    assert isinstance(result, dict)
    assert "content" in result
    assert "AI服务调用失败" in result["content"]
    assert result["model"] == "test-model"
    assert result["usage"] is None


# ═══════════════════════════════════════════════════════════════════════
# c) analyze_report endpoint error handling
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_analyze_report_ai_failure_returns_500(client: AsyncClient, auth_headers, db_session):
    """When AI call raises a generic Exception, endpoint returns HTTP 500."""
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)

    with patch(f"{REPORT_MODULE}.analyze_report_structured", new_callable=AsyncMock) as mock_ai:
        mock_ai.side_effect = Exception("AI服务调用失败: something went wrong")
        resp = await client.post(
            "/api/report/analyze",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 500
    assert "AI解读失败" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_report_timeout_error_message(client: AsyncClient, auth_headers, db_session):
    """When AI call raises a timeout-related Exception, endpoint returns '超时' hint."""
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)

    with patch(f"{REPORT_MODULE}.analyze_report_structured", new_callable=AsyncMock) as mock_ai:
        mock_ai.side_effect = Exception("AI服务调用失败: timed out after 120s")
        resp = await client.post(
            "/api/report/analyze",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 500
    assert "超时" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_report_connect_error_message(client: AsyncClient, auth_headers, db_session):
    """When AI call raises a connect-related Exception, endpoint returns '连接失败' hint."""
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)

    with patch(f"{REPORT_MODULE}.analyze_report_structured", new_callable=AsyncMock) as mock_ai:
        mock_ai.side_effect = Exception("AI服务调用失败: connect error to host")
        resp = await client.post(
            "/api/report/analyze",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 500
    assert "连接失败" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_report_generic_error_includes_detail(client: AsyncClient, auth_headers, db_session):
    """Generic AI failure returns 500 with the error detail in the response body."""
    await _create_ocr_config(db_session)
    user_id = await _get_user_id(client, auth_headers)
    report = await _create_report(db_session, user_id)

    with patch(f"{REPORT_MODULE}.analyze_report_structured", new_callable=AsyncMock) as mock_ai:
        mock_ai.side_effect = Exception("AI服务调用失败: model overloaded")
        resp = await client.post(
            "/api/report/analyze",
            json={"report_id": report.id},
            headers=auth_headers,
        )

    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "AI解读失败" in detail
    assert "model overloaded" in detail
