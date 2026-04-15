"""COS 存储管理、上传限制、迁移与公开上传接口的 API 自动化测试."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.api import cos as cos_api
from app.models.models import CosConfig, CosFile, CosMigrationTask, CosUploadLimit, User
from tests.conftest import test_session


# ──────────────── helpers ────────────────


async def _seed_cos_config(
    *,
    secret_id: str = "test-ak",
    secret_key: str = "test-secret-key-16bytes",
    bucket: str = "test-bucket",
    region: str = "ap-guangzhou",
    is_active: bool = True,
    cdn_domain: str | None = None,
    path_prefix: str = "",
) -> int:
    async with test_session() as s:
        cfg = CosConfig(
            secret_id=secret_id,
            secret_key_encrypted=secret_key,
            bucket=bucket,
            region=region,
            is_active=is_active,
            cdn_domain=cdn_domain,
            path_prefix=path_prefix,
        )
        s.add(cfg)
        await s.commit()
        await s.refresh(cfg)
        return cfg.id


async def _count_cos_files() -> int:
    async with test_session() as s:
        r = await s.execute(select(func.count(CosFile.id)))
        return r.scalar() or 0


async def _get_cos_config_secret() -> str | None:
    async with test_session() as s:
        r = await s.execute(select(CosConfig).order_by(CosConfig.id.desc()).limit(1))
        row = r.scalar_one_or_none()
        return row.secret_key_encrypted if row else None


async def _admin_user_id() -> int:
    async with test_session() as s:
        r = await s.execute(select(User).where(User.phone == "13800000001"))
        u = r.scalar_one()
        return u.id


# ══════════════════════════════════════════════
#  COS 配置管理
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc001_get_cos_config_success_new_fields(client: AsyncClient, admin_headers: dict):
    """TC-001: 获取 COS 配置（成功，返回含 CDN、路径前缀等新字段）."""
    resp = await client.get("/api/admin/cos/config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    for key in (
        "id",
        "secret_id",
        "secret_key_masked",
        "bucket",
        "region",
        "image_prefix",
        "video_prefix",
        "file_prefix",
        "is_active",
        "cdn_domain",
        "cdn_protocol",
        "path_prefix",
        "test_passed",
        "created_at",
        "updated_at",
    ):
        assert key in data
    assert data["cdn_protocol"] in ("https", "http")
    assert isinstance(data["path_prefix"], str)


@pytest.mark.asyncio
async def test_tc002_update_cos_config_cdn_and_prefix(client: AsyncClient, admin_headers: dict):
    """TC-002: 更新 COS 配置（含 CDN 域名、路径前缀）."""
    resp = await client.put(
        "/api/admin/cos/config",
        headers=admin_headers,
        json={
            "secret_id": "ak-demo",
            "secret_key": "sk-demo-value",
            "bucket": "demo-bucket",
            "region": "ap-shanghai",
            "cdn_domain": "cdn.example.com",
            "cdn_protocol": "https",
            "path_prefix": "app/uploads/",
        },
    )
    assert resp.status_code == 200
    assert "成功" in resp.json().get("message", "")

    get_r = await client.get("/api/admin/cos/config", headers=admin_headers)
    assert get_r.status_code == 200
    body = get_r.json()
    assert body["cdn_domain"] == "cdn.example.com"
    assert body["path_prefix"] == "app/uploads/"
    assert body["region"] == "ap-shanghai"


@pytest.mark.asyncio
async def test_tc003_update_cos_config_omit_secret_key_keeps_existing(client: AsyncClient, admin_headers: dict):
    """TC-003: 更新配置不传 SecretKey（保留原密钥）."""
    await _seed_cos_config(secret_key="ORIGINAL_SECRET_VALUE")

    await client.put(
        "/api/admin/cos/config",
        headers=admin_headers,
        json={
            "cdn_domain": "keep-secret.example.com",
        },
    )

    assert await _get_cos_config_secret() == "ORIGINAL_SECRET_VALUE"


@pytest.mark.asyncio
async def test_tc004_test_cos_connection_mock_success(client: AsyncClient, admin_headers: dict, monkeypatch):
    """TC-004: 测试连接（模拟成功场景）."""
    await _seed_cos_config()

    class _FakeResp:
        status_code = 200

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def head(self, url: str):
            return _FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: _FakeClient())

    resp = await client.post("/api/admin/cos/test", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "成功" in data.get("message", "")


@pytest.mark.asyncio
async def test_tc005_non_admin_cos_config_forbidden(client: AsyncClient, auth_headers: dict):
    """TC-005: 非管理员访问配置接口（403）."""
    r = await client.get("/api/admin/cos/config", headers=auth_headers)
    assert r.status_code == 403


# ══════════════════════════════════════════════
#  上传限制
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc006_get_upload_limits_list(client: AsyncClient, admin_headers: dict):
    """TC-006: 获取上传限制配置列表."""
    async with test_session() as s:
        s.add(CosUploadLimit(module="image", module_name="图片", max_size_mb=10))
        s.add(CosUploadLimit(module="video", module_name="视频", max_size_mb=100))
        await s.commit()

    resp = await client.get("/api/admin/cos/upload-limits", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 2
    modules = {x["module"] for x in data["items"]}
    assert "image" in modules and "video" in modules


@pytest.mark.asyncio
async def test_tc007_batch_update_upload_limits(client: AsyncClient, admin_headers: dict):
    """TC-007: 批量更新上传限制."""
    resp = await client.put(
        "/api/admin/cos/upload-limits",
        headers=admin_headers,
        json={
            "items": [
                {"module": "image", "max_size_mb": 8},
                {"module": "video", "max_size_mb": 120},
            ]
        },
    )
    assert resp.status_code == 200

    async with test_session() as s:
        r = await s.execute(select(CosUploadLimit).where(CosUploadLimit.module == "image"))
        img = r.scalar_one()
        assert img.max_size_mb == 8
        r2 = await s.execute(select(CosUploadLimit).where(CosUploadLimit.module == "video"))
        vid = r2.scalar_one()
        assert vid.max_size_mb == 120


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_mb,expect_status",
    [
        (0, 422),
        (-1, 422),
        (1025, 422),
        (2000, 422),
    ],
)
async def test_tc008_upload_limits_out_of_range(client: AsyncClient, admin_headers: dict, bad_mb, expect_status):
    """TC-008: 更新限制超出范围（>1024 或 <=0）."""
    resp = await client.put(
        "/api/admin/cos/upload-limits",
        headers=admin_headers,
        json={"items": [{"module": "image", "max_size_mb": bad_mb}]},
    )
    assert resp.status_code == expect_status


@pytest.mark.asyncio
async def test_tc009_public_upload_limits_no_auth(client: AsyncClient):
    """TC-009: 公开接口获取上传限制（无需认证）."""
    resp = await client.get("/api/cos/upload-limits")
    assert resp.status_code == 200
    assert "items" in resp.json()


# ══════════════════════════════════════════════
#  文件统计
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc010_cos_usage_total_files(client: AsyncClient, admin_headers: dict):
    """TC-010: 获取文件统计（返回 total_files）."""
    async with test_session() as s:
        s.add(
            CosFile(
                file_key="k1",
                file_url="/uploads/k1",
                file_type="image/png",
                file_size=100,
                module="image",
            )
        )
        s.add(
            CosFile(
                file_key="k2",
                file_url="/uploads/k2",
                file_type="image/png",
                file_size=200,
                module="image",
            )
        )
        await s.commit()

    resp = await client.get("/api/admin/cos/usage", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json().get("total_files") == 2


# ══════════════════════════════════════════════
#  数据迁移
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc011_migration_scan(client: AsyncClient, admin_headers: dict):
    """TC-011: 扫描待迁移文件."""
    resp = await client.post("/api/admin/cos/migration/scan", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    assert "total_files" in data
    assert "total_size_display" in data


@pytest.mark.asyncio
async def test_tc012_migration_start(client: AsyncClient, admin_headers: dict, monkeypatch):
    """TC-012: 开始迁移任务（不执行后台真实迁移，避免连接生产库）."""

    async def _noop_run_migration(task_id: int, modules: list):
        return None

    monkeypatch.setattr(cos_api, "_run_migration", _noop_run_migration)

    await _seed_cos_config()

    resp = await client.post(
        "/api/admin/cos/migration/start",
        headers=admin_headers,
        json={"modules": ["local_files"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert data.get("status") == "scanning"


@pytest.mark.asyncio
async def test_tc013_migration_progress(client: AsyncClient, admin_headers: dict):
    """TC-013: 查询迁移进度（基于数据库中的任务记录）."""
    cos_api._migration_state.clear()
    uid = await _admin_user_id()
    async with test_session() as s:
        task = CosMigrationTask(
            status="completed",
            total_files=10,
            migrated_count=7,
            failed_count=1,
            skipped_count=2,
            created_by=uid,
        )
        s.add(task)
        await s.commit()
        await s.refresh(task)
        tid = task.id

    resp = await client.get(
        f"/api/admin/cos/migration/progress?task_id={tid}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"] == tid
    assert body["status"] == "completed"
    assert body["total_files"] == 10
    assert body["migrated_count"] == 7
    assert "progress_percent" in body


# ══════════════════════════════════════════════
#  文件上传（用户端 /api/upload/*）
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc014_upload_image_creates_cos_file_record(
    client: AsyncClient, auth_headers: dict, monkeypatch
):
    """TC-014: 上传图片（含 cos_files 记录写入）；不连接 COS，走本地存储."""
    async def _no_cos(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.upload.try_cos_upload", _no_cos)

    before = await _count_cos_files()
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    files = {"file": ("tiny.png", png_header, "image/png")}
    resp = await client.post("/api/upload/image", headers=auth_headers, files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("storage") == "local"
    assert "url" in data
    assert await _count_cos_files() == before + 1


@pytest.mark.asyncio
async def test_tc015_upload_video_creates_record(client: AsyncClient, auth_headers: dict, monkeypatch):
    """TC-015: 上传视频."""
    async def _no_cos(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.upload.try_cos_upload", _no_cos)

    before = await _count_cos_files()
    body = b"\x00\x00\x00\x20ftypmp41" + b"\x00" * 64
    files = {"file": ("clip.mp4", body, "video/mp4")}
    resp = await client.post("/api/upload/video", headers=auth_headers, files=files)
    assert resp.status_code == 200
    assert resp.json().get("storage") == "local"
    assert await _count_cos_files() == before + 1


@pytest.mark.asyncio
async def test_tc016_upload_image_exceeds_size_limit(client: AsyncClient, admin_headers: dict, auth_headers: dict):
    """TC-016: 上传超过大小限制的图片."""
    await client.put(
        "/api/admin/cos/upload-limits",
        headers=admin_headers,
        json={"items": [{"module": "image", "max_size_mb": 1}]},
    )

    big = b"\xff\xd8\xff\xe0" + b"\x00" * (2 * 1024 * 1024)
    files = {"file": ("big.jpg", big, "image/jpeg")}
    resp = await client.post("/api/upload/image", headers=auth_headers, files=files)
    assert resp.status_code == 400
    assert "MB" in resp.json().get("detail", "")
