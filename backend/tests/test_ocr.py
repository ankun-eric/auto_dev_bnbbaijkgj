"""Tests for OCR multi-provider configuration management APIs."""

from datetime import date, datetime

import pytest
from httpx import AsyncClient

from app.models.models import (
    OcrCallRecord,
    OcrCallStatistics,
    OcrProviderConfig,
    OcrSceneTemplate,
    OcrUploadConfig,
)

from .conftest import test_session


# ──────────────── helpers ────────────────


async def _seed_providers(count: int = 3):
    """Insert default OCR provider rows and return their names."""
    providers = [
        OcrProviderConfig(
            provider_name="baidu", display_name="百度云",
            config_json={"api_key": "", "secret_key": ""}, is_enabled=False, is_preferred=False,
        ),
        OcrProviderConfig(
            provider_name="tencent", display_name="腾讯云",
            config_json={"secret_id": "", "secret_key": ""}, is_enabled=False, is_preferred=False,
        ),
        OcrProviderConfig(
            provider_name="aliyun", display_name="阿里云",
            config_json={"access_key_id": "", "access_key_secret": ""}, is_enabled=False, is_preferred=False,
        ),
    ]
    async with test_session() as s:
        for p in providers[:count]:
            s.add(p)
        await s.commit()


async def _seed_scene(scene_name: str, is_preset: bool = False, **kwargs) -> int:
    async with test_session() as s:
        scene = OcrSceneTemplate(scene_name=scene_name, is_preset=is_preset, **kwargs)
        s.add(scene)
        await s.commit()
        await s.refresh(scene)
        return scene.id


async def _seed_upload_config(max_batch: int = 5, max_size: int = 5) -> int:
    async with test_session() as s:
        cfg = OcrUploadConfig(max_batch_count=max_batch, max_file_size_mb=max_size)
        s.add(cfg)
        await s.commit()
        await s.refresh(cfg)
        return cfg.id


async def _seed_records(n: int = 3) -> list[int]:
    ids = []
    async with test_session() as s:
        for i in range(n):
            rec = OcrCallRecord(
                provider_name="baidu", status="success",
                scene_name="测试场景", ocr_raw_text=f"text-{i}",
            )
            s.add(rec)
            await s.flush()
            ids.append(rec.id)
        await s.commit()
    return ids


async def _seed_statistics():
    async with test_session() as s:
        s.add(OcrCallStatistics(
            provider_name="baidu", call_date=date.today(),
            total_calls=100, success_calls=95,
        ))
        s.add(OcrCallStatistics(
            provider_name="tencent", call_date=date.today(),
            total_calls=50, success_calls=48,
        ))
        await s.commit()


# ══════════════════════════════════════════════
#  1. GET /api/admin/ocr/providers
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_providers_success(client: AsyncClient, admin_headers):
    await _seed_providers()
    resp = await client.get("/api/admin/ocr/providers", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 3
    names = {p["provider_name"] for p in data}
    assert names == {"baidu", "tencent", "aliyun"}
    for p in data:
        assert "status_label" in p
        assert p["status_label"] == "未启用"


@pytest.mark.asyncio
async def test_get_providers_no_auth(client: AsyncClient):
    resp = await client.get("/api/admin/ocr/providers")
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  2. PUT /api/admin/ocr/providers/{provider}
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_update_provider_success(client: AsyncClient, admin_headers):
    await _seed_providers()
    resp = await client.put(
        "/api/admin/ocr/providers/baidu",
        headers=admin_headers,
        json={"config_json": {"api_key": "new_key", "secret_key": "new_sec"}, "is_enabled": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_enabled"] is True
    assert data["status_label"] == "已启用"


@pytest.mark.asyncio
async def test_update_provider_not_found(client: AsyncClient, admin_headers):
    await _seed_providers()
    resp = await client.put(
        "/api/admin/ocr/providers/non_existent",
        headers=admin_headers,
        json={"is_enabled": True},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_provider_no_auth(client: AsyncClient):
    resp = await client.put("/api/admin/ocr/providers/baidu", json={"is_enabled": True})
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  3. POST /api/admin/ocr/providers/{provider}/preferred
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_set_preferred_success(client: AsyncClient, admin_headers):
    await _seed_providers()
    await client.put(
        "/api/admin/ocr/providers/tencent", headers=admin_headers,
        json={"is_enabled": True},
    )
    resp = await client.post("/api/admin/ocr/providers/tencent/preferred", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_preferred"] is True
    assert data["status_label"] == "首选"

    all_resp = await client.get("/api/admin/ocr/providers", headers=admin_headers)
    for p in all_resp.json():
        if p["provider_name"] == "tencent":
            assert p["is_preferred"] is True
        else:
            assert p["is_preferred"] is False


@pytest.mark.asyncio
async def test_set_preferred_not_found(client: AsyncClient, admin_headers):
    await _seed_providers()
    resp = await client.post("/api/admin/ocr/providers/fake/preferred", headers=admin_headers)
    assert resp.status_code == 404


# ══════════════════════════════════════════════
#  4. POST /api/admin/ocr/providers/{provider}/disable
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_disable_provider_success(client: AsyncClient, admin_headers):
    await _seed_providers()
    await client.put(
        "/api/admin/ocr/providers/baidu", headers=admin_headers,
        json={"is_enabled": True},
    )
    resp = await client.post("/api/admin/ocr/providers/baidu/disable", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_enabled"] is False
    assert data["is_preferred"] is False
    assert data["status_label"] == "未启用"


@pytest.mark.asyncio
async def test_disable_provider_not_found(client: AsyncClient, admin_headers):
    resp = await client.post("/api/admin/ocr/providers/nope/disable", headers=admin_headers)
    assert resp.status_code == 404


# ══════════════════════════════════════════════
#  5. GET /api/admin/ocr/statistics
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_statistics_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/ocr/statistics?period=today", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["period"] == "today"
    assert data["total_calls"] == 0


@pytest.mark.asyncio
async def test_statistics_with_data(client: AsyncClient, admin_headers):
    await _seed_statistics()
    resp = await client.get("/api/admin/ocr/statistics?period=today", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_calls"] == 150
    assert data["total_success"] == 143
    assert len(data["providers"]) == 2


@pytest.mark.asyncio
async def test_statistics_period_all(client: AsyncClient, admin_headers):
    await _seed_statistics()
    resp = await client.get("/api/admin/ocr/statistics?period=all", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total_calls"] == 150


@pytest.mark.asyncio
async def test_statistics_invalid_period(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/ocr/statistics?period=invalid", headers=admin_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_statistics_no_auth(client: AsyncClient):
    resp = await client.get("/api/admin/ocr/statistics?period=today")
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  6. GET /api/admin/ocr/scenes
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_scenes_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/ocr/scenes", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_scenes_with_data(client: AsyncClient, admin_headers):
    await _seed_scene("体检报告识别", is_preset=True)
    await _seed_scene("拍照识药", is_preset=True)
    resp = await client.get("/api/admin/ocr/scenes", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


# ══════════════════════════════════════════════
#  7. POST /api/admin/ocr/scenes
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_scene_success(client: AsyncClient, admin_headers):
    resp = await client.post(
        "/api/admin/ocr/scenes", headers=admin_headers,
        json={"scene_name": "新场景", "prompt_content": "请整理以下文字"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scene_name"] == "新场景"
    assert data["is_preset"] is False


@pytest.mark.asyncio
async def test_create_scene_duplicate_name(client: AsyncClient, admin_headers):
    await _seed_scene("已有场景")
    resp = await client.post(
        "/api/admin/ocr/scenes", headers=admin_headers,
        json={"scene_name": "已有场景"},
    )
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_scene_missing_name(client: AsyncClient, admin_headers):
    resp = await client.post(
        "/api/admin/ocr/scenes", headers=admin_headers,
        json={"prompt_content": "test"},
    )
    assert resp.status_code == 422


# ══════════════════════════════════════════════
#  8. PUT /api/admin/ocr/scenes/{id}
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_update_scene_success(client: AsyncClient, admin_headers):
    sid = await _seed_scene("编辑场景")
    resp = await client.put(
        f"/api/admin/ocr/scenes/{sid}", headers=admin_headers,
        json={"scene_name": "编辑场景v2", "prompt_content": "更新后的提示词"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scene_name"] == "编辑场景v2"
    assert data["prompt_content"] == "更新后的提示词"


@pytest.mark.asyncio
async def test_update_scene_not_found(client: AsyncClient, admin_headers):
    resp = await client.put(
        "/api/admin/ocr/scenes/99999", headers=admin_headers,
        json={"scene_name": "x"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_scene_duplicate_name(client: AsyncClient, admin_headers):
    await _seed_scene("场景A")
    sid_b = await _seed_scene("场景B")
    resp = await client.put(
        f"/api/admin/ocr/scenes/{sid_b}", headers=admin_headers,
        json={"scene_name": "场景A"},
    )
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


# ══════════════════════════════════════════════
#  9. DELETE /api/admin/ocr/scenes/{id}
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_delete_scene_success(client: AsyncClient, admin_headers):
    sid = await _seed_scene("可删除场景", is_preset=False)
    resp = await client.delete(f"/api/admin/ocr/scenes/{sid}", headers=admin_headers)
    assert resp.status_code == 200
    assert "删除成功" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_preset_scene_forbidden(client: AsyncClient, admin_headers):
    sid = await _seed_scene("预设场景", is_preset=True)
    resp = await client.delete(f"/api/admin/ocr/scenes/{sid}", headers=admin_headers)
    assert resp.status_code == 400
    assert "预设" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_scene_not_found(client: AsyncClient, admin_headers):
    resp = await client.delete("/api/admin/ocr/scenes/99999", headers=admin_headers)
    assert resp.status_code == 404


# ══════════════════════════════════════════════
#  10. GET /api/admin/ocr/upload-limits
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_upload_limits_default(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/ocr/upload-limits", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_batch_count"] == 5
    assert data["max_file_size_mb"] == 5


@pytest.mark.asyncio
async def test_get_upload_limits_existing(client: AsyncClient, admin_headers):
    await _seed_upload_config(10, 20)
    resp = await client.get("/api/admin/ocr/upload-limits", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_batch_count"] == 10
    assert data["max_file_size_mb"] == 20


# ══════════════════════════════════════════════
#  11. PUT /api/admin/ocr/upload-limits
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_update_upload_limits_success(client: AsyncClient, admin_headers):
    resp = await client.put(
        "/api/admin/ocr/upload-limits", headers=admin_headers,
        json={"max_batch_count": 10, "max_file_size_mb": 20},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_batch_count"] == 10
    assert data["max_file_size_mb"] == 20


@pytest.mark.asyncio
async def test_update_upload_limits_partial(client: AsyncClient, admin_headers):
    await _seed_upload_config(5, 5)
    resp = await client.put(
        "/api/admin/ocr/upload-limits", headers=admin_headers,
        json={"max_batch_count": 8},
    )
    assert resp.status_code == 200
    assert resp.json()["max_batch_count"] == 8
    assert resp.json()["max_file_size_mb"] == 5


@pytest.mark.asyncio
async def test_update_upload_limits_no_auth(client: AsyncClient):
    resp = await client.put("/api/admin/ocr/upload-limits", json={"max_batch_count": 10})
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  12. GET /api/admin/ocr/records
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_records_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/ocr/records", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_records_with_data(client: AsyncClient, admin_headers):
    await _seed_records(5)
    resp = await client.get("/api/admin/ocr/records?page=1&page_size=3", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 3
    assert data["page"] == 1
    assert data["page_size"] == 3


@pytest.mark.asyncio
async def test_list_records_filter_provider(client: AsyncClient, admin_headers):
    await _seed_records(3)
    resp = await client.get(
        "/api/admin/ocr/records?provider_name=baidu", headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 3

    resp2 = await client.get(
        "/api/admin/ocr/records?provider_name=aliyun", headers=admin_headers,
    )
    assert resp2.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_records_no_auth(client: AsyncClient):
    resp = await client.get("/api/admin/ocr/records")
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  13. POST /api/admin/ocr/records/batch-delete
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_batch_delete_records_success(client: AsyncClient, admin_headers):
    ids = await _seed_records(3)
    resp = await client.post(
        "/api/admin/ocr/records/batch-delete", headers=admin_headers,
        json=ids[:2],
    )
    assert resp.status_code == 200
    assert "2" in resp.json()["detail"]

    remaining = await client.get("/api/admin/ocr/records", headers=admin_headers)
    assert remaining.json()["total"] == 1


@pytest.mark.asyncio
async def test_batch_delete_empty_ids(client: AsyncClient, admin_headers):
    resp = await client.post(
        "/api/admin/ocr/records/batch-delete", headers=admin_headers,
        json=[],
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_batch_delete_no_auth(client: AsyncClient):
    resp = await client.post("/api/admin/ocr/records/batch-delete", json=[1])
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  Cross-cutting: status_label logic
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_status_label_transitions(client: AsyncClient, admin_headers):
    await _seed_providers()

    resp = await client.put(
        "/api/admin/ocr/providers/baidu", headers=admin_headers,
        json={"is_enabled": True},
    )
    assert resp.json()["status_label"] == "已启用"

    resp = await client.post("/api/admin/ocr/providers/baidu/preferred", headers=admin_headers)
    assert resp.json()["status_label"] == "首选"

    resp = await client.post("/api/admin/ocr/providers/baidu/disable", headers=admin_headers)
    assert resp.json()["status_label"] == "未启用"
