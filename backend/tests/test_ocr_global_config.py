"""Tests for OCR global config split — scene templates & upload limits.

Validates that scenes no longer carry ai_model_id / ocr_provider fields,
and that CRUD + upload-limit endpoints behave correctly after the split.
"""

import pytest
from httpx import AsyncClient

from app.models.models import OcrSceneTemplate, OcrUploadConfig

from .conftest import test_session


# ──────────────── helpers ────────────────


async def _seed_scene(scene_name: str, *, is_preset: bool = False, prompt_content: str | None = None) -> int:
    async with test_session() as s:
        scene = OcrSceneTemplate(scene_name=scene_name, is_preset=is_preset, prompt_content=prompt_content)
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


# ══════════════════════════════════════════════
#  TC-001: 获取场景列表成功，返回字段不含 ai_model_id / ocr_provider
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc001_scene_list_no_legacy_fields(client: AsyncClient, admin_headers):
    """Scene response must NOT contain ai_model_id or ocr_provider."""
    await _seed_scene("体检报告识别", is_preset=True, prompt_content="提示词A")
    await _seed_scene("拍照识药", is_preset=True, prompt_content="提示词B")

    resp = await client.get("/api/admin/ocr/scenes", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2

    for item in data:
        assert "ai_model_id" not in item
        assert "ocr_provider" not in item
        for key in ("id", "scene_name", "prompt_content", "is_preset", "created_at", "updated_at"):
            assert key in item


# ══════════════════════════════════════════════
#  TC-002: 创建场景成功（含 prompt_content）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc002_create_scene_with_prompt(client: AsyncClient, admin_headers):
    resp = await client.post(
        "/api/admin/ocr/scenes", headers=admin_headers,
        json={"scene_name": "新建场景", "prompt_content": "请整理以下文字"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scene_name"] == "新建场景"
    assert data["prompt_content"] == "请整理以下文字"
    assert data["is_preset"] is False


# ══════════════════════════════════════════════
#  TC-003: 创建场景 - 名称重复返回 400
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc003_create_scene_duplicate_name(client: AsyncClient, admin_headers):
    await _seed_scene("重复场景")
    resp = await client.post(
        "/api/admin/ocr/scenes", headers=admin_headers,
        json={"scene_name": "重复场景"},
    )
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


# ══════════════════════════════════════════════
#  TC-004: 更新场景 - 修改 prompt_content
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc004_update_scene_prompt(client: AsyncClient, admin_headers):
    sid = await _seed_scene("待更新场景", prompt_content="旧提示词")
    resp = await client.put(
        f"/api/admin/ocr/scenes/{sid}", headers=admin_headers,
        json={"prompt_content": "新提示词内容"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["prompt_content"] == "新提示词内容"
    assert data["scene_name"] == "待更新场景"


# ══════════════════════════════════════════════
#  TC-005: 更新场景 - 不存在的场景返回 404
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc005_update_scene_not_found(client: AsyncClient, admin_headers):
    resp = await client.put(
        "/api/admin/ocr/scenes/99999", headers=admin_headers,
        json={"scene_name": "不存在"},
    )
    assert resp.status_code == 404


# ══════════════════════════════════════════════
#  TC-006: 删除自定义场景成功
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc006_delete_custom_scene(client: AsyncClient, admin_headers):
    sid = await _seed_scene("可删除场景", is_preset=False)
    resp = await client.delete(f"/api/admin/ocr/scenes/{sid}", headers=admin_headers)
    assert resp.status_code == 200
    assert "删除成功" in resp.json()["detail"]

    verify = await client.get("/api/admin/ocr/scenes", headers=admin_headers)
    names = [s["scene_name"] for s in verify.json()]
    assert "可删除场景" not in names


# ══════════════════════════════════════════════
#  TC-007: 删除预设场景返回 400
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc007_delete_preset_scene_forbidden(client: AsyncClient, admin_headers):
    sid = await _seed_scene("预设场景", is_preset=True)
    resp = await client.delete(f"/api/admin/ocr/scenes/{sid}", headers=admin_headers)
    assert resp.status_code == 400
    assert "预设" in resp.json()["detail"]


# ══════════════════════════════════════════════
#  TC-008: 删除不存在场景返回 404
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc008_delete_scene_not_found(client: AsyncClient, admin_headers):
    resp = await client.delete("/api/admin/ocr/scenes/99999", headers=admin_headers)
    assert resp.status_code == 404


# ══════════════════════════════════════════════
#  TC-009: 获取上传限制成功
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc009_get_upload_limits(client: AsyncClient, admin_headers):
    await _seed_upload_config(10, 20)
    resp = await client.get("/api/admin/ocr/upload-limits", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_batch_count"] == 10
    assert data["max_file_size_mb"] == 20
    assert "id" in data
    assert "updated_at" in data


# ══════════════════════════════════════════════
#  TC-010: 更新上传限制成功
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc010_update_upload_limits(client: AsyncClient, admin_headers):
    resp = await client.put(
        "/api/admin/ocr/upload-limits", headers=admin_headers,
        json={"max_batch_count": 15, "max_file_size_mb": 30},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_batch_count"] == 15
    assert data["max_file_size_mb"] == 30

    verify = await client.get("/api/admin/ocr/upload-limits", headers=admin_headers)
    assert verify.json()["max_batch_count"] == 15
    assert verify.json()["max_file_size_mb"] == 30


# ══════════════════════════════════════════════
#  TC-011: 未认证访问场景接口返回 401
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc011_scenes_no_auth(client: AsyncClient):
    resp = await client.get("/api/admin/ocr/scenes")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc011_create_scene_no_auth(client: AsyncClient):
    resp = await client.post("/api/admin/ocr/scenes", json={"scene_name": "x"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc011_update_scene_no_auth(client: AsyncClient):
    resp = await client.put("/api/admin/ocr/scenes/1", json={"scene_name": "x"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc011_delete_scene_no_auth(client: AsyncClient):
    resp = await client.delete("/api/admin/ocr/scenes/1")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc011_upload_limits_no_auth(client: AsyncClient):
    resp = await client.get("/api/admin/ocr/upload-limits")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_tc011_update_upload_limits_no_auth(client: AsyncClient):
    resp = await client.put("/api/admin/ocr/upload-limits", json={"max_batch_count": 1})
    assert resp.status_code in (401, 403)


# ══════════════════════════════════════════════
#  TC-012: 场景列表中 prompt_content 字段存在
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc012_scene_has_prompt_content(client: AsyncClient, admin_headers):
    await _seed_scene("带提示词场景", prompt_content="这是提示词内容")
    await _seed_scene("无提示词场景", prompt_content=None)

    resp = await client.get("/api/admin/ocr/scenes", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    by_name = {s["scene_name"]: s for s in data}
    assert by_name["带提示词场景"]["prompt_content"] == "这是提示词内容"
    assert "prompt_content" in by_name["无提示词场景"]
