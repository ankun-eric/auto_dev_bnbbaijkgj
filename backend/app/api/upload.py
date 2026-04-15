import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import CosFile, CosUploadLimit, User
from app.utils.cos_helper import try_cos_upload

router = APIRouter(prefix="/api/upload", tags=["文件上传"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
ALLOWED_FILE_TYPES = (
    ALLOWED_IMAGE_TYPES
    | ALLOWED_VIDEO_TYPES
    | {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
)

DEFAULT_IMAGE_MAX_MB = 10
DEFAULT_VIDEO_MAX_MB = 100
DEFAULT_FILE_MAX_MB = 50


async def _get_max_size_mb(db: AsyncSession, module: str, default: int) -> int:
    result = await db.execute(
        select(CosUploadLimit.max_size_mb).where(CosUploadLimit.module == module)
    )
    row = result.scalar_one_or_none()
    return row if row is not None else default


async def _save_local(filename: str, content: bytes) -> str:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return f"/uploads/{filename}"


async def _do_upload(
    db: AsyncSession,
    file: UploadFile,
    content: bytes,
    module: str,
) -> dict:
    ext = os.path.splitext(file.filename or "file")[1]
    flat_name = f"{uuid.uuid4().hex}{ext}"

    cos_url = await try_cos_upload(db, content, file.filename or flat_name, file.content_type or "application/octet-stream")
    if cos_url:
        file_key = cos_url.rsplit("/", 1)[-1] if "/" in cos_url else flat_name
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
        return {"url": cos_url, "filename": os.path.basename(cos_url), "size": len(content), "storage": "cos"}

    local_url = await _save_local(flat_name, content)
    cos_file = CosFile(
        file_key=flat_name,
        file_url=local_url,
        file_type=file.content_type,
        file_size=len(content),
        original_name=file.filename,
        module=module,
    )
    db.add(cos_file)
    await db.flush()
    return {"url": local_url, "filename": flat_name, "size": len(content), "storage": "local"}


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的图片格式，请上传 JPG/PNG/GIF/WEBP 格式")

    max_mb = await _get_max_size_mb(db, "image", DEFAULT_IMAGE_MAX_MB)
    content = await file.read()
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"图片大小不能超过{max_mb}MB")

    return await _do_upload(db, file, content, "image")


@router.post("/video")
async def upload_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="不支持的视频格式，请上传 MP4/MOV/AVI/WEBM 格式")

    max_mb = await _get_max_size_mb(db, "video", DEFAULT_VIDEO_MAX_MB)
    content = await file.read()
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"视频大小不能超过{max_mb}MB")

    return await _do_upload(db, file, content, "video")


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    max_mb = await _get_max_size_mb(db, "file", DEFAULT_FILE_MAX_MB)
    content = await file.read()
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"文件大小不能超过{max_mb}MB")

    return await _do_upload(db, file, content, "file")
