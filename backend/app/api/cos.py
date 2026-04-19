import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_db
from app.core.security import require_role
from app.models.models import (
    CosConfig,
    CosFile,
    CosMigrationDetail,
    CosMigrationTask,
    CosUploadLimit,
)
from app.schemas.cos import (
    CosConfigResponse,
    CosConfigUpdate,
    CosFileResponse,
    CosMigrationFailedItem,
    CosMigrationGroupItem,
    CosMigrationScanResponse,
    CosMigrationStartRequest,
    CosMigrationStartResponse,
    CosMigrationTaskResponse,
    CosUploadLimitBatchUpdate,
    CosUploadLimitResponse,
    CosUsageResponse,
)
from app.utils.cos_helper import get_cos_config_cached, try_cos_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["COS存储管理"])

admin_dep = require_role("admin")

_migration_state: Dict[int, dict] = {}


def _mask_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "****"
    return key[:4] + "****" + key[-4:]


async def _get_cos_config(db: AsyncSession) -> CosConfig | None:
    result = await db.execute(select(CosConfig).order_by(CosConfig.id.desc()).limit(1))
    return result.scalar_one_or_none()


# ──────────────── Config CRUD ────────────────


@router.get("/admin/cos/config")
async def get_cos_config(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_cos_config(db)
    if not cfg:
        return {
            "id": 0,
            "secret_id": "",
            "secret_key_masked": "",
            "bucket": "",
            "region": "",
            "image_prefix": "images/",
            "video_prefix": "videos/",
            "file_prefix": "files/",
            "is_active": False,
            "cdn_domain": None,
            "cdn_protocol": "https",
            "test_passed": False,
            "created_at": None,
            "updated_at": None,
        }
    return {
        "id": cfg.id,
        "secret_id": cfg.secret_id or "",
        "secret_key_masked": _mask_key(cfg.secret_key_encrypted),
        "bucket": cfg.bucket or "",
        "region": cfg.region or "",
        "image_prefix": cfg.image_prefix or "images/",
        "video_prefix": cfg.video_prefix or "videos/",
        "file_prefix": cfg.file_prefix or "files/",
        "is_active": cfg.is_active,
        "cdn_domain": cfg.cdn_domain,
        "cdn_protocol": cfg.cdn_protocol or "https",
        "test_passed": bool(cfg.test_passed),
        "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.put("/admin/cos/config")
async def update_cos_config(
    data: CosConfigUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_cos_config(db)
    if not cfg:
        cfg = CosConfig()
        db.add(cfg)

    if data.secret_id is not None:
        cfg.secret_id = data.secret_id
    if data.secret_key is not None:
        cfg.secret_key_encrypted = data.secret_key
    if data.bucket is not None:
        cfg.bucket = data.bucket
    if data.region is not None:
        cfg.region = data.region
    if data.image_prefix is not None:
        cfg.image_prefix = data.image_prefix
    if data.video_prefix is not None:
        cfg.video_prefix = data.video_prefix
    if data.file_prefix is not None:
        cfg.file_prefix = data.file_prefix
    if data.is_active is not None:
        cfg.is_active = data.is_active
    if data.cdn_domain is not None:
        cfg.cdn_domain = data.cdn_domain
    if data.cdn_protocol is not None:
        cfg.cdn_protocol = data.cdn_protocol
    cfg.updated_at = datetime.utcnow()

    try:
        await db.flush()
    except Exception as e:
        await db.rollback()
        logger.error("COS配置更新失败: %s", e)
        raise HTTPException(status_code=500, detail=f"数据库操作失败: {str(e)}")
    return {"message": "COS配置更新成功"}


@router.post("/admin/cos/test-connection")
async def test_cos_connection_upload(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    """通过实际上传 1KB 测试文件验证 COS 配置可用性（仅超级管理员可用）。"""
    cfg = await _get_cos_config(db)
    if not cfg or not cfg.secret_id or not cfg.secret_key_encrypted or not cfg.bucket:
        return {
            "success": False,
            "message": "COS配置不完整，请先完善 SecretId/SecretKey/Bucket",
            "detail": None,
        }

    test_content = b"x" * 1024
    test_filename = f"cos-conn-test-{uuid.uuid4().hex}.txt"
    try:
        cos_url = await try_cos_upload(db, test_content, test_filename, "text/plain")
    except Exception as e:
        cfg.test_passed = False
        try:
            await db.flush()
        except Exception:
            await db.rollback()
        logger.error("COS test-connection 上传异常: %s", e)
        return {
            "success": False,
            "message": f"上传测试失败: {str(e)}",
            "detail": {"filename": test_filename, "size": len(test_content)},
        }

    if cos_url:
        cfg.test_passed = True
        cfg.updated_at = datetime.utcnow()
        try:
            await db.flush()
        except Exception:
            await db.rollback()
        return {
            "success": True,
            "message": "COS连接测试成功，1KB 测试文件已上传",
            "detail": {
                "filename": test_filename,
                "size": len(test_content),
                "url": cos_url,
            },
        }

    cfg.test_passed = False
    try:
        await db.flush()
    except Exception:
        await db.rollback()
    return {
        "success": False,
        "message": "上传返回为空，请检查 SecretKey/Bucket/Region 是否正确",
        "detail": {"filename": test_filename, "size": len(test_content)},
    }


@router.post("/admin/cos/test")
async def test_cos_connection(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_cos_config(db)
    if not cfg or not cfg.secret_id or not cfg.secret_key_encrypted or not cfg.bucket:
        return {"success": False, "message": "COS配置不完整，请先完善配置"}

    try:
        import httpx

        region = cfg.region or "ap-guangzhou"
        url = f"https://{cfg.bucket}.cos.{region}.myqcloud.com/"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.head(url)
            if resp.status_code in (200, 403):
                cfg.test_passed = True
                cfg.updated_at = datetime.utcnow()
                try:
                    await db.flush()
                except Exception as db_err:
                    await db.rollback()
                    logger.error("COS测试结果保存失败: %s", db_err)
                return {"success": True, "message": "COS连接测试成功（Bucket可达）"}
            cfg.test_passed = False
            try:
                await db.flush()
            except Exception as db_err:
                await db.rollback()
                logger.error("COS测试结果保存失败: %s", db_err)
            return {"success": False, "message": f"COS返回状态码 {resp.status_code}"}
    except Exception as e:
        cfg.test_passed = False
        try:
            await db.flush()
        except Exception as db_err:
            await db.rollback()
            logger.error("COS测试结果保存失败: %s", db_err)
        return {"success": False, "message": f"连接失败: {str(e)}"}


# ──────────────── Files ────────────────


@router.get("/admin/cos/files")
async def list_cos_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    module: Optional[str] = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(CosFile)
    count_query = select(func.count(CosFile.id))

    if module:
        query = query.where(CosFile.module == module)
        count_query = count_query.where(CosFile.module == module)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(CosFile.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [CosFileResponse.model_validate(f) for f in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.delete("/admin/cos/files")
async def delete_cos_file_endpoint(
    file_key: str = Query(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CosFile).where(CosFile.file_key == file_key))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")

    from app.utils.cos_helper import delete_cos_file

    if f.file_url and f.file_url.startswith("http"):
        await delete_cos_file(db, file_key)

    await db.delete(f)
    return {"message": "文件记录已删除"}


@router.get("/admin/cos/usage")
async def get_cos_usage(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    total_files = (await db.execute(select(func.count(CosFile.id)))).scalar() or 0
    return {"total_files": total_files}


# ──────────────── Unified Upload ────────────────


@router.post("/admin/upload")
async def unified_upload(
    file: UploadFile = File(...),
    module: Optional[str] = None,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过50MB")

    cfg = await _get_cos_config(db)
    if cfg and cfg.is_active and cfg.secret_id and cfg.secret_key_encrypted and cfg.bucket:
        return await _upload_to_cos(cfg, file, content, module, db)

    return await _upload_local(file, content, module, db)


async def _upload_local(
    file: UploadFile, content: bytes, module: Optional[str], db: AsyncSession
) -> dict:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "file")[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(content)

    cos_file = CosFile(
        file_key=filename,
        file_url=f"/uploads/{filename}",
        file_type=file.content_type,
        file_size=len(content),
        original_name=file.filename,
        module=module,
    )
    db.add(cos_file)
    await db.flush()

    return {
        "url": f"/uploads/{filename}",
        "file_key": filename,
        "filename": file.filename,
        "size": len(content),
        "storage": "local",
    }


async def _upload_to_cos(
    cfg: CosConfig,
    file: UploadFile,
    content: bytes,
    module: Optional[str],
    db: AsyncSession,
) -> dict:
    ext = os.path.splitext(file.filename or "file")[1]
    if file.content_type and file.content_type.startswith("image/"):
        effective_prefix = cfg.image_prefix or "images/"
    elif file.content_type and file.content_type.startswith("video/"):
        effective_prefix = cfg.video_prefix or "videos/"
    else:
        effective_prefix = cfg.file_prefix or "files/"

    file_key = f"{effective_prefix}{uuid.uuid4().hex}{ext}"
    region = cfg.region or "ap-guangzhou"
    host = f"{cfg.bucket}.cos.{region}.myqcloud.com"
    cos_url_raw = f"https://{host}/{file_key}"

    from app.utils.cos_helper import _build_cos_authorization, _build_file_url

    try:
        authorization = _build_cos_authorization(
            cfg.secret_id, cfg.secret_key_encrypted, host, file_key, "put"
        )

        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.put(
                cos_url_raw,
                content=content,
                headers={
                    "Host": host,
                    "Authorization": authorization,
                    "Content-Type": file.content_type or "application/octet-stream",
                },
            )
            if resp.status_code in (200, 204):
                final_url = _build_file_url(cfg, file_key)
                cos_file = CosFile(
                    file_key=file_key,
                    file_url=final_url,
                    file_type=file.content_type,
                    file_size=len(content),
                    original_name=file.filename,
                    module=module,
                )
                db.add(cos_file)
                await db.flush()
                return {
                    "url": final_url,
                    "file_key": file_key,
                    "filename": file.filename,
                    "size": len(content),
                    "storage": "cos",
                }
    except Exception:
        pass

    return await _upload_local(file, content, module, db)


# ──────────────── Upload Limits ────────────────


@router.get("/admin/cos/upload-limits")
async def get_upload_limits(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CosUploadLimit).order_by(CosUploadLimit.id))
    items = [CosUploadLimitResponse.model_validate(row) for row in result.scalars().all()]
    return {"items": items}


@router.put("/admin/cos/upload-limits")
async def batch_update_upload_limits(
    data: CosUploadLimitBatchUpdate,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    try:
        for item in data.items:
            result = await db.execute(
                select(CosUploadLimit).where(CosUploadLimit.module == item.module)
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.max_size_mb = item.max_size_mb
            else:
                db.add(CosUploadLimit(module=item.module, max_size_mb=item.max_size_mb))
        await db.flush()
    except Exception as e:
        await db.rollback()
        logger.error("上传限制更新失败: %s", e)
        raise HTTPException(status_code=500, detail=f"数据库操作失败: {str(e)}")
    return {"message": "上传限制配置已更新"}


@router.get("/cos/upload-limits")
async def get_public_upload_limits(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CosUploadLimit).order_by(CosUploadLimit.id))
    items = [CosUploadLimitResponse.model_validate(row) for row in result.scalars().all()]
    return {"items": items}


# ──────────────── Migration ────────────────

MODULE_TABLE_FIELDS = {
    "avatar": ("users", "avatar"),
    "article_cover": ("articles", "cover_image"),
    "banner": ("home_banners", "image_url"),
    "checkup_report": ("checkup_reports", "file_url"),
    "checkup_thumbnail": ("checkup_reports", "thumbnail_url"),
    "digital_human_silent": ("digital_humans", "silent_video_url"),
    "digital_human_speaking": ("digital_humans", "speaking_video_url"),
    "menu_icon": ("home_menu_items", "icon_content"),
}

MODULE_NAMES = {
    "avatar": "用户头像",
    "article_cover": "文章封面",
    "banner": "首页Banner",
    "checkup_report": "体检报告",
    "checkup_thumbnail": "体检缩略图",
    "digital_human_silent": "数字人静默视频",
    "digital_human_speaking": "数字人说话视频",
    "menu_icon": "菜单图标",
    "local_files": "本地上传文件",
}


@router.post("/admin/cos/migration/scan")
async def migration_scan(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import text

    groups = []
    total_files = 0
    total_size = 0

    for module, (table, column) in MODULE_TABLE_FIELDS.items():
        try:
            sql = text(
                f"SELECT COUNT(*), COALESCE(SUM(0), 0) FROM {table} "
                f"WHERE {column} IS NOT NULL AND {column} != '' "
                f"AND ({column} LIKE '/uploads/%' OR ({column} NOT LIKE 'https://%cos%' AND {column} NOT LIKE 'http://%cos%'))"
            )
            result = await db.execute(sql)
            row = result.one()
            count = row[0] or 0
            if count > 0:
                groups.append(CosMigrationGroupItem(
                    module=module,
                    module_name=MODULE_NAMES.get(module, module),
                    file_count=count,
                    total_size=0,
                    total_size_display="未知",
                ))
                total_files += count
        except Exception as e:
            logger.warning("Migration scan error for %s: %s", module, e)

    local_file_count = 0
    local_file_size = 0
    uploads_dir = settings.UPLOAD_DIR
    if os.path.isdir(uploads_dir):
        for fname in os.listdir(uploads_dir):
            fpath = os.path.join(uploads_dir, fname)
            if os.path.isfile(fpath):
                local_file_count += 1
                local_file_size += os.path.getsize(fpath)

    if local_file_count > 0:
        size_display = f"{local_file_size / 1024 / 1024:.2f} MB" if local_file_size > 0 else "0 MB"
        groups.append(CosMigrationGroupItem(
            module="local_files",
            module_name="本地上传文件",
            file_count=local_file_count,
            total_size=local_file_size,
            total_size_display=size_display,
        ))
        total_files += local_file_count
        total_size += local_file_size

    total_display = f"{total_size / 1024 / 1024:.2f} MB" if total_size > 0 else "未知"
    return CosMigrationScanResponse(
        groups=groups,
        total_files=total_files,
        total_size=total_size,
        total_size_display=total_display,
    )


@router.post("/admin/cos/migration/start")
async def migration_start(
    data: CosMigrationStartRequest,
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_cos_config(db)
    if not cfg or not cfg.is_active or not cfg.secret_id or not cfg.secret_key_encrypted:
        raise HTTPException(status_code=400, detail="COS未启用或配置不完整")

    task = CosMigrationTask(
        status="scanning",
        created_by=current_user.id,
    )
    db.add(task)
    await db.flush()
    task_id = task.id

    _migration_state[task_id] = {
        "status": "scanning",
        "total_files": 0,
        "migrated_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "current_file": None,
        "started_at": None,
    }

    asyncio.create_task(_run_migration(task_id, data.modules))

    return CosMigrationStartResponse(
        task_id=task_id,
        status="scanning",
        total_files=0,
        message="迁移任务已启动，正在扫描文件...",
    )


async def _run_migration(task_id: int, modules: list):
    """Background migration task."""
    from sqlalchemy import text

    state = _migration_state.get(task_id, {})
    try:
        async with async_session() as db:
            cfg = await get_cos_config_cached(db)
            if not cfg:
                state["status"] = "failed"
                return

            files_to_migrate = []

            for module in modules:
                if module == "local_files":
                    uploads_dir = settings.UPLOAD_DIR
                    if os.path.isdir(uploads_dir):
                        for fname in os.listdir(uploads_dir):
                            fpath = os.path.join(uploads_dir, fname)
                            if os.path.isfile(fpath):
                                files_to_migrate.append({
                                    "module": "local_files",
                                    "original_url": f"/uploads/{fname}",
                                    "local_path": fpath,
                                    "file_size": os.path.getsize(fpath),
                                })
                elif module in MODULE_TABLE_FIELDS:
                    table, column = MODULE_TABLE_FIELDS[module]
                    sql = text(
                        f"SELECT id, {column} FROM {table} "
                        f"WHERE {column} IS NOT NULL AND {column} != '' "
                        f"AND ({column} LIKE '/uploads/%' OR ({column} NOT LIKE 'https://%cos%' AND {column} NOT LIKE 'http://%cos%'))"
                    )
                    result = await db.execute(sql)
                    for row in result.all():
                        files_to_migrate.append({
                            "module": module,
                            "original_url": row[1],
                            "record_id": row[0],
                            "table": table,
                            "column": column,
                            "file_size": 0,
                        })

            state["total_files"] = len(files_to_migrate)
            state["status"] = "migrating"
            state["started_at"] = datetime.utcnow().isoformat()

            await db.execute(
                update(CosMigrationTask)
                .where(CosMigrationTask.id == task_id)
                .values(
                    total_files=len(files_to_migrate),
                    status="migrating",
                    started_at=datetime.utcnow(),
                )
            )
            await db.commit()

            for item in files_to_migrate:
                state["current_file"] = item["original_url"]
                try:
                    file_content = None
                    original_url = item["original_url"]

                    if original_url.startswith("/uploads/"):
                        local_path = item.get("local_path") or os.path.join(
                            settings.UPLOAD_DIR, original_url.replace("/uploads/", "")
                        )
                        if os.path.isfile(local_path):
                            with open(local_path, "rb") as f:
                                file_content = f.read()
                        else:
                            state["skipped_count"] = state.get("skipped_count", 0) + 1
                            continue
                    else:
                        state["skipped_count"] = state.get("skipped_count", 0) + 1
                        continue

                    filename = os.path.basename(original_url)
                    import mimetypes

                    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

                    cos_url = await try_cos_upload(db, file_content, filename, content_type)
                    if not cos_url:
                        state["failed_count"] = state.get("failed_count", 0) + 1
                        detail = CosMigrationDetail(
                            task_id=task_id,
                            module=item["module"],
                            original_url=original_url,
                            file_size=len(file_content),
                            status="failed",
                            error_message="COS上传返回None",
                        )
                        db.add(detail)
                        await db.commit()
                        continue

                    if item["module"] != "local_files" and "table" in item:
                        await db.execute(
                            text(
                                f"UPDATE {item['table']} SET {item['column']} = :new_url WHERE id = :record_id"
                            ),
                            {"new_url": cos_url, "record_id": item["record_id"]},
                        )

                    detail = CosMigrationDetail(
                        task_id=task_id,
                        module=item["module"],
                        original_url=original_url,
                        cos_url=cos_url,
                        file_size=len(file_content),
                        status="success",
                        migrated_at=datetime.utcnow(),
                    )
                    db.add(detail)
                    await db.commit()

                    state["migrated_count"] = state.get("migrated_count", 0) + 1

                except Exception as e:
                    state["failed_count"] = state.get("failed_count", 0) + 1
                    logger.error("Migration error for %s: %s", item.get("original_url"), e)
                    try:
                        detail = CosMigrationDetail(
                            task_id=task_id,
                            module=item["module"],
                            original_url=item["original_url"],
                            status="failed",
                            error_message=str(e)[:500],
                        )
                        db.add(detail)
                        await db.commit()
                    except Exception:
                        pass

            state["status"] = "completed"
            state["current_file"] = None

            await db.execute(
                update(CosMigrationTask)
                .where(CosMigrationTask.id == task_id)
                .values(
                    status="completed",
                    migrated_count=state.get("migrated_count", 0),
                    failed_count=state.get("failed_count", 0),
                    skipped_count=state.get("skipped_count", 0),
                    completed_at=datetime.utcnow(),
                )
            )
            await db.commit()

    except Exception as e:
        logger.error("Migration task %d failed: %s", task_id, e)
        state["status"] = "failed"
        try:
            async with async_session() as db:
                await db.execute(
                    update(CosMigrationTask)
                    .where(CosMigrationTask.id == task_id)
                    .values(status="failed", completed_at=datetime.utcnow())
                )
                await db.commit()
        except Exception:
            pass


@router.get("/admin/cos/migration/progress")
async def migration_progress(
    task_id: int = Query(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    state = _migration_state.get(task_id)
    if not state:
        result = await db.execute(
            select(CosMigrationTask).where(CosMigrationTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="迁移任务不存在")
        total = task.total_files or 1
        progress = round((task.migrated_count + task.failed_count + task.skipped_count) / total * 100, 1) if total > 0 else 0

        failed_items = []
        if task.failed_count and task.failed_count > 0:
            detail_result = await db.execute(
                select(CosMigrationDetail)
                .where(CosMigrationDetail.task_id == task_id, CosMigrationDetail.status == "failed")
                .limit(50)
            )
            failed_items = [
                CosMigrationFailedItem(original_url=d.original_url, error_message=d.error_message)
                for d in detail_result.scalars().all()
            ]

        return CosMigrationTaskResponse(
            task_id=task.id,
            status=task.status,
            total_files=task.total_files,
            migrated_count=task.migrated_count,
            failed_count=task.failed_count,
            skipped_count=task.skipped_count,
            progress_percent=progress,
            current_file=None,
            started_at=task.started_at,
            failed_items=failed_items,
        )

    total = state.get("total_files", 0) or 1
    done = state.get("migrated_count", 0) + state.get("failed_count", 0) + state.get("skipped_count", 0)
    progress = round(done / total * 100, 1)

    remaining = None
    if state.get("started_at") and done > 0:
        from datetime import datetime as dt

        try:
            started = dt.fromisoformat(state["started_at"])
            elapsed = (dt.utcnow() - started).total_seconds()
            remaining = int(elapsed / done * (total - done)) if done > 0 else None
        except Exception:
            pass

    failed_items = []
    if state.get("failed_count", 0) > 0:
        detail_result = await db.execute(
            select(CosMigrationDetail)
            .where(CosMigrationDetail.task_id == task_id, CosMigrationDetail.status == "failed")
            .limit(50)
        )
        failed_items = [
            CosMigrationFailedItem(original_url=d.original_url, error_message=d.error_message)
            for d in detail_result.scalars().all()
        ]

    return CosMigrationTaskResponse(
        task_id=task_id,
        status=state.get("status", "unknown"),
        total_files=state.get("total_files", 0),
        migrated_count=state.get("migrated_count", 0),
        failed_count=state.get("failed_count", 0),
        skipped_count=state.get("skipped_count", 0),
        progress_percent=progress,
        current_file=state.get("current_file"),
        estimated_remaining_seconds=remaining,
        started_at=None,
        failed_items=failed_items,
    )


@router.post("/admin/cos/migration/retry")
async def migration_retry(
    task_id: int = Query(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CosMigrationDetail)
        .where(CosMigrationDetail.task_id == task_id, CosMigrationDetail.status == "failed")
    )
    failed_details = result.scalars().all()
    if not failed_details:
        return {"message": "没有失败的文件需要重试", "retried": 0}

    cfg = await _get_cos_config(db)
    if not cfg or not cfg.is_active:
        raise HTTPException(status_code=400, detail="COS未启用")

    retried = 0
    for detail in failed_details:
        try:
            original_url = detail.original_url
            if not original_url or not original_url.startswith("/uploads/"):
                continue

            local_path = os.path.join(settings.UPLOAD_DIR, original_url.replace("/uploads/", ""))
            if not os.path.isfile(local_path):
                continue

            with open(local_path, "rb") as f:
                file_content = f.read()

            import mimetypes

            filename = os.path.basename(original_url)
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

            cos_url = await try_cos_upload(db, file_content, filename, content_type)
            if cos_url:
                detail.cos_url = cos_url
                detail.status = "success"
                detail.migrated_at = datetime.utcnow()
                detail.error_message = None

                if detail.module in MODULE_TABLE_FIELDS:
                    from sqlalchemy import text

                    table, column = MODULE_TABLE_FIELDS[detail.module]
                    await db.execute(
                        text(f"UPDATE {table} SET {column} = :url WHERE {column} = :old_url"),
                        {"url": cos_url, "old_url": original_url},
                    )
                retried += 1
        except Exception as e:
            detail.error_message = str(e)[:500]

    await db.flush()

    task_result = await db.execute(
        select(CosMigrationTask).where(CosMigrationTask.id == task_id)
    )
    task = task_result.scalar_one_or_none()
    if task:
        task.migrated_count = (task.migrated_count or 0) + retried
        task.failed_count = max((task.failed_count or 0) - retried, 0)
        await db.flush()

    return {"message": f"重试完成，成功 {retried} 个", "retried": retried}
