import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User
from app.utils.cos_helper import try_cos_upload

router = APIRouter(prefix="/api/upload", tags=["文件上传"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
ALLOWED_FILE_TYPES = ALLOWED_IMAGE_TYPES | {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_FILE_SIZE = 50 * 1024 * 1024


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的图片格式，请上传 JPG/PNG/GIF/WEBP 格式")

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="图片大小不能超过10MB")

    cos_url = await try_cos_upload(db, content, file.filename or "image.jpg", file.content_type, "images/")
    if cos_url:
        return {"url": cos_url, "filename": os.path.basename(cos_url), "size": len(content)}

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "image.jpg")[1]
    filename = f"img_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/{filename}", "filename": filename, "size": len(content)}


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过50MB")

    cos_url = await try_cos_upload(db, content, file.filename or "file", file.content_type, "files/")
    if cos_url:
        return {"url": cos_url, "filename": os.path.basename(cos_url), "size": len(content)}

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "file")[1]
    filename = f"file_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/{filename}", "filename": filename, "size": len(content)}
