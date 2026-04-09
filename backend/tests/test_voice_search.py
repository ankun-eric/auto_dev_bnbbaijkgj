"""语音搜索相关 API 非 UI 自动化测试（ASR token / recognize、统一搜索 source 参数等）。"""

import io

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import search as search_api
from app.models.models import SearchLog


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """健康检查"""
    r = await client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"


@pytest.mark.asyncio
async def test_asr_token(client: AsyncClient):
    """ASR token 接口：未启用配置时返回 400"""
    r = await client.post("/api/search/asr/token")
    assert r.status_code in (200, 400)
    if r.status_code == 400:
        data = r.json()
        assert "语音识别服务未启用" in data.get("detail", "")


@pytest.mark.asyncio
async def test_asr_recognize_no_file(client: AsyncClient):
    """ASR 识别 - 无文件应返回 422"""
    r = await client.post("/api/search/asr/recognize")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_asr_recognize_empty_file(client: AsyncClient):
    """ASR 识别 - 空文件：ASR 未启用时为 ASR_DISABLED；启用且读到空字节时为 AUDIO_EMPTY"""
    files = {"audio_file": ("test.wav", io.BytesIO(b""), "audio/wav")}
    data = {"format": "wav", "sample_rate": "16000"}
    r = await client.post("/api/search/asr/recognize", files=files, data=data)
    result = r.json()
    assert r.status_code == 200
    assert result.get("success") is False
    assert result.get("error_code") in ("ASR_DISABLED", "AUDIO_EMPTY")


@pytest.mark.asyncio
async def test_asr_recognize_with_audio(client: AsyncClient):
    """ASR 识别 - 带音频数据（ASR 未启用时返回 ASR_DISABLED）"""
    fake_audio = b"\x00" * 1000
    files = {"audio_file": ("test.webm", io.BytesIO(fake_audio), "audio/webm")}
    data = {"format": "webm", "sample_rate": "16000"}
    r = await client.post("/api/search/asr/recognize", files=files, data=data)
    result = r.json()
    assert r.status_code == 200
    if result.get("error_code") == "ASR_DISABLED":
        assert result["success"] is False
    elif result.get("success"):
        assert "text" in result.get("data", {})


@pytest.mark.asyncio
async def test_search_hot(client: AsyncClient):
    """热门搜索"""
    r = await client.get("/api/search/hot")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_search_suggest(client: AsyncClient):
    """搜索联想"""
    r = await client.get("/api/search/suggest", params={"q": "感冒"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_query(client: AsyncClient):
    """统一搜索"""
    r = await client.get(
        "/api/search",
        params={"q": "健康", "type": "all", "page": 1, "page_size": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_search_drug_keywords(client: AsyncClient):
    """药品搜索关键词"""
    r = await client.get("/api/search/drug-keywords")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_search_history_no_auth(client: AsyncClient):
    """搜索历史 - 未登录应返回 401"""
    r = await client.get("/api/search/history")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_asr_recognize_rate_limit(client: AsyncClient):
    """ASR 识别频率限制（同 IP 窗口内超过阈值返回 RATE_LIMITED）"""
    search_api._asr_rate_limit.clear()
    for _ in range(12):
        files = {"audio_file": ("test.wav", io.BytesIO(b"\x00" * 100), "audio/wav")}
        data = {"format": "wav", "sample_rate": "16000"}
        r = await client.post("/api/search/asr/recognize", files=files, data=data)
        result = r.json()
        if result.get("error_code") == "RATE_LIMITED":
            assert result["success"] is False
            break
    else:
        pytest.fail("expected RATE_LIMITED within 12 requests after clearing rate window")


# ════════════════════════════════════════════
#  source 参数相关测试
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_search_source_voice_logged(client: AsyncClient, db_session: AsyncSession):
    """统一搜索传 source=voice 时 SearchLog.source 应为 'voice'"""
    r = await client.get("/api/search", params={"q": "语音测试词", "type": "all", "source": "voice"})
    assert r.status_code == 200

    result = await db_session.execute(
        select(SearchLog).where(SearchLog.keyword == "语音测试词").order_by(SearchLog.id.desc()).limit(1)
    )
    log = result.scalar_one_or_none()
    assert log is not None, "SearchLog should be recorded"
    assert log.source == "voice"


@pytest.mark.asyncio
async def test_search_source_text_default(client: AsyncClient, db_session: AsyncSession):
    """统一搜索不传 source 时 SearchLog.source 应默认为 'text'"""
    r = await client.get("/api/search", params={"q": "文本默认测试词", "type": "all"})
    assert r.status_code == 200

    result = await db_session.execute(
        select(SearchLog).where(SearchLog.keyword == "文本默认测试词").order_by(SearchLog.id.desc()).limit(1)
    )
    log = result.scalar_one_or_none()
    assert log is not None, "SearchLog should be recorded"
    assert log.source == "text"


@pytest.mark.asyncio
async def test_search_source_text_explicit(client: AsyncClient, db_session: AsyncSession):
    """统一搜索显式传 source=text 时 SearchLog.source 应为 'text'"""
    r = await client.get("/api/search", params={"q": "显式文本测试词", "type": "all", "source": "text"})
    assert r.status_code == 200

    result = await db_session.execute(
        select(SearchLog).where(SearchLog.keyword == "显式文本测试词").order_by(SearchLog.id.desc()).limit(1)
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.source == "text"


@pytest.mark.asyncio
async def test_search_source_invalid_normalizes_to_text(client: AsyncClient, db_session: AsyncSession):
    """统一搜索传非法 source 值时应规范化为 'text'"""
    r = await client.get("/api/search", params={"q": "非法来源测试词", "type": "all", "source": "invalid_xyz"})
    assert r.status_code == 200

    result = await db_session.execute(
        select(SearchLog).where(SearchLog.keyword == "非法来源测试词").order_by(SearchLog.id.desc()).limit(1)
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.source == "text"


@pytest.mark.asyncio
async def test_search_source_voice_with_block_word(client: AsyncClient, admin_headers: dict, db_session: AsyncSession):
    """被屏蔽词搜索 + source=voice 时 SearchLog.source 仍为 'voice'"""
    block_kw = "语音屏蔽测试词"
    await client.post(
        "/api/admin/search/block-words",
        json={"keyword": block_kw, "block_mode": "full", "is_active": True},
        headers=admin_headers,
    )

    r = await client.get("/api/search", params={"q": block_kw, "type": "all", "source": "voice"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0

    result = await db_session.execute(
        select(SearchLog).where(SearchLog.keyword == block_kw).order_by(SearchLog.id.desc()).limit(1)
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.source == "voice"


@pytest.mark.asyncio
async def test_search_response_does_not_expose_source(client: AsyncClient):
    """统一搜索响应不应泄漏 source 字段（只记录在日志中）"""
    r = await client.get("/api/search", params={"q": "响应字段测试词", "type": "all", "source": "voice"})
    assert r.status_code == 200
    data = r.json()
    assert "source" not in data
