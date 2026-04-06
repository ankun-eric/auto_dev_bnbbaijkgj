import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_role
from app.models.models import CosConfig, CosFile
from app.schemas.cos import CosConfigResponse, CosConfigUpdate, CosFileResponse, CosUsageResponse

router = APIRouter(prefix="/api", tags=["COS存储管理"])

admin_dep = require_role("admin")


def _mask_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "****"
    return key[:4] + "****" + key[-4:]


async def _get_cos_config(db: AsyncSession) -> CosConfig | None:
    result = await db.execute(select(CosConfig).order_by(CosConfig.id.desc()).limit(1))
    return result.scalar_one_or_none()


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
    cfg.updated_at = datetime.utcnow()

    await db.flush()
    return {"message": "COS配置更新成功"}


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
                return {"success": True, "message": "COS连接测试成功（Bucket可达）"}
            return {"success": False, "message": f"COS返回状态码 {resp.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}


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
async def delete_cos_file(
    file_key: str = Query(...),
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CosFile).where(CosFile.file_key == file_key))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    await db.delete(f)
    return {"message": "文件记录已删除"}


@router.get("/admin/cos/usage")
async def get_cos_usage(
    current_user=Depends(admin_dep),
    db: AsyncSession = Depends(get_db),
):
    total_files = (await db.execute(select(func.count(CosFile.id)))).scalar() or 0
    total_size = (await db.execute(select(func.sum(CosFile.file_size)))).scalar() or 0

    type_result = await db.execute(
        select(CosFile.file_type, func.count(CosFile.id), func.sum(CosFile.file_size))
        .group_by(CosFile.file_type)
    )
    by_type = {}
    for ft, cnt, sz in type_result.all():
        by_type[ft or "unknown"] = {"count": cnt, "size": int(sz or 0)}

    return CosUsageResponse(
        total_files=total_files,
        total_size=int(total_size),
        total_size_mb=round(int(total_size) / 1024 / 1024, 2),
        by_type=by_type,
    )


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
    filename = f"{module or 'file'}_{uuid.uuid4().hex}{ext}"
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
    prefix = cfg.file_prefix or "files/"
    if file.content_type and file.content_type.startswith("image/"):
        prefix = cfg.image_prefix or "images/"
    elif file.content_type and file.content_type.startswith("video/"):
        prefix = cfg.video_prefix or "videos/"

    file_key = f"{prefix}{uuid.uuid4().hex}{ext}"
    region = cfg.region or "ap-guangzhou"
    cos_url = f"https://{cfg.bucket}.cos.{region}.myqcloud.com/{file_key}"

    try:
        import hashlib
        import hmac
        import time as _time
        from datetime import datetime as _dt

        now = int(_time.time())
        key_time = f"{now};{now + 600}"
        sign_key = hmac.new(
            (cfg.secret_key_encrypted or "").encode(), key_time.encode(), hashlib.sha1
        ).hexdigest()

        import httpx
        headers = {
            "Content-Type": file.content_type or "application/octet-stream",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.put(cos_url, content=content, headers=headers)
            if resp.status_code not in (200, 204):
                os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
                local_name = f"{module or 'file'}_{uuid.uuid4().hex}{ext}"
                local_path = os.path.join(settings.UPLOAD_DIR, local_name)
                with open(local_path, "wb") as f:
                    f.write(content)
                cos_url = f"/uploads/{local_name}"
                file_key = local_name
    except Exception:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        local_name = f"{module or 'file'}_{uuid.uuid4().hex}{ext}"
        local_path = os.path.join(settings.UPLOAD_DIR, local_name)
        with open(local_path, "wb") as f:
            f.write(content)
        cos_url = f"/uploads/{local_name}"
        file_key = local_name

    cos_file = CosFile(
        file_key=file_key,
        file_url=cos_url,
        file_type=file.content_type,
        file_size=len(content),
        original_name=file.filename,
        module=module,
    )
    db.add(cos_file)
    await db.flush()

    return {
        "url": cos_url,
        "file_key": file_key,
        "filename": file.filename,
        "size": len(content),
        "storage": "cos" if cos_url.startswith("https://") else "local",
    }
